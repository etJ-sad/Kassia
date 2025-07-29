<#
.SYNOPSIS
    Kassia Update Integration Module - Integrates Windows updates into mounted WIM images.

.DESCRIPTION
    This module handles the integration of Windows updates (MSU, CAB, EXE, MSI) into mounted Windows images.
    It validates update compatibility, provides comprehensive error handling, and supports both DISM integration
    and Yunona staging for post-deployment updates.
    
    Enhanced with better validation, error handling, and progress tracking.

.PARAMETER ProfileConfig
    Device profile configuration object containing OS support information.

.PARAMETER BuildConfig
    Build configuration object containing paths and OS information.

.PARAMETER SkipValidation
    Skip update validation checks (for testing or special cases).

.PARAMETER DryRun
    Simulate update integration without making actual changes.

.PARAMETER MaxRetries
    Maximum number of retry attempts for failed DISM operations (default: 2).

.EXAMPLE
    .\UpdateModule.ps1 -ProfileConfig $deviceProfile -BuildConfig $buildConfig
    
    Integrates updates for the specified configuration.

.EXAMPLE
    .\UpdateModule.ps1 -ProfileConfig $deviceProfile -BuildConfig $buildConfig -DryRun
    
    Simulates update integration to show what would be processed.

.NOTES
    Author   : Alexander Soloninov
    Version  : 1.1.0
    Module   : Kassia Build Engine
    Requires : DISM, PowerShell 5.1+, Logging.psm1
    Tags     : Updates, DISM, Windows Updates, Validation

#>

param (
    [Parameter(Mandatory)]
    [ValidateNotNull()]
    [pscustomobject]$ProfileConfig,

    [Parameter(Mandatory)]
    [ValidateNotNull()]
    [pscustomobject]$BuildConfig,

    [switch]$SkipValidation,
    
    [switch]$DryRun,

    [ValidateRange(1, 5)]
    [int]$MaxRetries = 2
)

# Module constants and state
$script:ModuleVersion = "1.1.0"
$script:ProcessedUpdates = @()
$script:FailedUpdates = @()
$script:UpdateStats = @{
    Total = 0
    Processed = 0
    Skipped = 0
    Failed = 0
    MSU = 0
    CAB = 0
    EXE = 0
    MSI = 0
}

#region Configuration and Initialization

function Initialize-UpdateModule {
    <#
    .SYNOPSIS
        Initializes the update module and validates prerequisites
    #>
    
    Write-Log -Message "Update Integration Module v$script:ModuleVersion starting..." -Level "INIT"
    
    # Validate required paths
    $requiredPaths = @{
        'Update Root' = $BuildConfig.updateRoot
        'Mount Point' = $BuildConfig.mountPoint
        'Yunona Source' = $BuildConfig.yunonaPath
    }
    
    foreach ($pathDesc in $requiredPaths.GetEnumerator()) {
        if (-not $pathDesc.Value) {
            throw "$($pathDesc.Key) path not specified in BuildConfig"
        }
        
        if ($pathDesc.Key -ne 'Mount Point' -and -not (Test-Path $pathDesc.Value)) {
            Write-Log -Message "$($pathDesc.Key) path does not exist: $($pathDesc.Value)" -Level "WARNING"
        } else {
            Write-Log -Message "$($pathDesc.Key): $($pathDesc.Value)" -Level "DEBUG"
        }
    }
}

function Get-OSInformation {
    <#
    .SYNOPSIS
        Retrieves OS information and friendly name with validation
    #>
    
    # Determine OS ID from multiple sources
    $osId = $ProfileConfig.selectedOSId
    if (-not $osId) { $osId = $BuildConfig.selectedOSId }
    if (-not $osId -and $ProfileConfig.supportedOS) { 
        $osId = $ProfileConfig.supportedOS[0] 
    }
    
    if (-not $osId) {
        throw "Could not determine OS ID from ProfileConfig or BuildConfig"
    }
    
    # Update ProfileConfig with resolved OS ID
    $ProfileConfig | Add-Member -NotePropertyName selectedOSId -NotePropertyValue $osId -Force
    
    # Load OS friendly names
    $supportedOS = @{}
    $supportedOSPath = Join-Path $global:rootPath "Engine\IDs\supportedOperatingSystems.json"
    
    if (Test-Path $supportedOSPath) {
        try {
            $osList = Get-Content $supportedOSPath -Raw | ConvertFrom-Json
            foreach ($os in $osList) {
                if ($os.id -and $os.text) {
                    $supportedOS[$os.id] = $os.text
                }
            }
        } catch {
            Write-Log -Message "Failed to parse supportedOperatingSystems.json: $($_.Exception.Message)" -Level "WARNING"
        }
    } else {
        Write-Log -Message "supportedOperatingSystems.json not found at $supportedOSPath" -Level "WARNING"
    }
    
    $osName = if ($supportedOS.ContainsKey($osId)) { $supportedOS[$osId] } else { "Unknown OS ID $osId" }
    
    return @{
        Id = $osId
        Name = $osName
    }
}

#endregion

#region Yunona Management

function Ensure-YunonaCore {
    <#
    .SYNOPSIS
        Ensures Yunona core files are present and up to date with improved error handling
    #>
    
    # Thread-safe check
    if ($script:YunonaInitialized) { 
        return 
    }
    $script:YunonaInitialized = $true
    
    $yunonaTarget = Join-Path $BuildConfig.mountPoint "Users\Public\Yunona"
    $yunonaSource = $BuildConfig.yunonaPath

    function Get-YunonaVersion {
        param([string]$ConfigPath)
        if (Test-Path $ConfigPath) {
            try {
                $json = Get-Content $ConfigPath -Raw | ConvertFrom-Json
                return [version]$json.version
            } catch {
                Write-Log -Message "Invalid Yunona config.json at $ConfigPath" -Level "WARNING"
                return $null
            }
        }
        return $null
    }

    $targetConfig = Join-Path $yunonaTarget "config.json"
    $sourceConfig = Join-Path $yunonaSource "config.json"
    $targetVersion = Get-YunonaVersion -ConfigPath $targetConfig
    $sourceVersion = Get-YunonaVersion -ConfigPath $sourceConfig

    Write-Log -Message "Yunona versions - Source: $sourceVersion, Target: $targetVersion" -Level "DEBUG"

    $shouldUpdate = $true
    if ($targetVersion -and $sourceVersion -and $targetVersion -ge $sourceVersion) {
        Write-Log -Message "Yunona is up to date (version $targetVersion)" -Level "INFO"
        $shouldUpdate = $false
    }

    if ($shouldUpdate) {
        try {
            Write-Log -Message "Updating Yunona core: $yunonaTarget" -Level "EXECUTING"
            
            # Create target directory
            if (-not (Test-Path $yunonaTarget)) {
                New-Item -Path $yunonaTarget -ItemType Directory -Force | Out-Null
            }
            
            # Copy Yunona files
            if (Test-Path $yunonaSource) {
                Copy-Item "$yunonaSource\*" -Destination $yunonaTarget -Recurse -Force
                Write-Log -Message "Yunona core updated successfully" -Level "OK"
            } else {
                Write-Log -Message "Yunona source path missing: $yunonaSource" -Level "ERROR"
            }
        } catch {
            Write-Log -Message "Failed to update Yunona core: $($_.Exception.Message)" -Level "ERROR"
            throw
        }
    }
}

#endregion

#region Update Discovery and Validation

function Get-UpdateConfigurations {
    <#
    .SYNOPSIS
        Discovers and loads all update configuration files
    #>
    
    $updateRoot = $BuildConfig.updateRoot
    
    if (-not (Test-Path $updateRoot)) {
        Write-Log -Message "Update root directory not found: $updateRoot" -Level "WARNING"
        return @()
    }
    
    $updateJsons = Get-ChildItem -Path $updateRoot -Recurse -Filter *.json -File -ErrorAction SilentlyContinue |
        Sort-Object FullName -Unique
    
    if (-not $updateJsons) {
        Write-Log -Message "No update JSON files found in $updateRoot" -Level "WARNING"
        return @()
    }
    
    # Load and parse configurations
    $updateConfigs = @()
    foreach ($jsonFile in $updateJsons) {
        try {
            $config = Get-Content $jsonFile.FullName -Raw | ConvertFrom-Json
            
            # Add file path for reference
            $config | Add-Member -NotePropertyName SourcePath -NotePropertyValue $jsonFile.FullName -Force
            $config | Add-Member -NotePropertyName SourceDirectory -NotePropertyValue $jsonFile.Directory.FullName -Force
            
            # Add order property if missing
            if (-not $config.order) {
                $config | Add-Member -NotePropertyName order -NotePropertyValue 9999 -Force
            }
            
            $updateConfigs += $config
            
        } catch {
            Write-Log -Message "Failed to parse update config: $($jsonFile.FullName) - $($_.Exception.Message)" -Level "ERROR"
        }
    }
    
    # Sort by order for proper installation sequence
    $sortedConfigs = $updateConfigs | Sort-Object order, updateName
    
    Write-Log -Message "Discovered $($sortedConfigs.Count) update configurations" -Level "INFO"
    return $sortedConfigs
}

function Test-UpdateCompatibility {
    <#
    .SYNOPSIS
        Tests if an update is compatible with the current OS
    #>
    param(
        [object]$UpdateConfig,
        [int]$OsId
    )
    
    if ($SkipValidation) {
        Write-Log -Message "Skipping compatibility validation for: $($UpdateConfig.updateName)" -Level "DEBUG"
        return $true
    }
    
    # Check OS compatibility
    if ($UpdateConfig.supportedOperatingSystems -and $UpdateConfig.supportedOperatingSystems -contains $OsId) {
        return $true
    }
    
    return $false
}

function Test-UpdateFileExists {
    <#
    .SYNOPSIS
        Validates that the update file exists and is accessible
    #>
    param(
        [object]$UpdateConfig
    )
    
    $updateDir = $UpdateConfig.SourceDirectory
    $fileName = $UpdateConfig.downloadFileName
    
    if (-not $fileName) {
        Write-Log -Message "No download file name specified for update: $($UpdateConfig.updateName)" -Level "ERROR"
        return $null
    }
    
    $filePath = Join-Path $updateDir $fileName
    
    if (-not (Test-Path $filePath)) {
        Write-Log -Message "Update file not found: $filePath" -Level "ERROR"
        return $null
    }
    
    # Additional validation for file size
    try {
        $fileSize = (Get-Item $filePath).Length
        if ($fileSize -eq 0) {
            Write-Log -Message "Update file is empty: $filePath" -Level "ERROR"
            return $null
        }
        
        Write-Log -Message "Update file validated: $filePath ($([math]::Round($fileSize / 1MB, 2)) MB)" -Level "DEBUG"
        return $filePath
    } catch {
        Write-Log -Message "Failed to validate update file $filePath`: $($_.Exception.Message)" -Level "ERROR"
        return $null
    }
}

function Get-CompatibleUpdates {
    <#
    .SYNOPSIS
        Filters update configurations for OS compatibility and file existence
    #>
    param(
        [array]$UpdateConfigs,
        [int]$OsId,
        [string]$OsName
    )
    
    $compatibleUpdates = @()
    $script:UpdateStats.Total = $UpdateConfigs.Count
    
    foreach ($updateConfig in $UpdateConfigs) {
        $isCompatible = Test-UpdateCompatibility -UpdateConfig $updateConfig -OsId $OsId
        
        Write-Log -Message "Checking update: $($updateConfig.updateName) [$($updateConfig.updateVersion)] ($($updateConfig.updateType))" -Level "DEBUG"
        Write-Log -Message "  - OS compatibility: $isCompatible" -Level "DEBUG"
        
        if (-not $isCompatible) {
            Write-Log -Message "Skipping update: $($updateConfig.updateName) (not compatible with $OsName)" -Level "DEBUG"
            $script:UpdateStats.Skipped++
            continue
        }
        
        # Validate file exists
        $filePath = Test-UpdateFileExists -UpdateConfig $updateConfig
        if (-not $filePath) {
            Write-Log -Message "Skipping update: $($updateConfig.updateName) (file not found or invalid)" -Level "WARNING"
            $script:UpdateStats.Skipped++
            continue
        }
        
        # Add file path to config
        $updateConfig | Add-Member -NotePropertyName ValidatedFilePath -NotePropertyValue $filePath -Force
        
        $compatibleUpdates += $updateConfig
    }
    
    Write-Log -Message "Found $($compatibleUpdates.Count) compatible updates out of $($UpdateConfigs.Count) total" -Level "INFO"
    return $compatibleUpdates
}

#endregion

#region Update Installation

function Install-DISMUpdate {
    <#
    .SYNOPSIS
        Installs MSU/CAB updates using DISM with retry logic
    #>
    param(
        [object]$UpdateConfig,
        [string]$FilePath,
        [string]$MountPoint,
        [string]$UpdateType
    )
    
    if ($DryRun) {
        Write-Log -Message "[DRY RUN] Would install $UpdateType update: $($UpdateConfig.updateName)" -Level "INFO"
        return $true
    }
    
    $retryCount = 0
    $maxRetries = $MaxRetries
    
    while ($retryCount -le $maxRetries) {
        try {
            Write-Log -Message "Installing $UpdateType update: $($UpdateConfig.updateName) (Attempt $($retryCount + 1)/$($maxRetries + 1))" -Level "EXECUTING"
            
            $dismArgs = @(
                "/Image:$MountPoint"
                "/Add-Package"
                "/PackagePath:`"$FilePath`""
            )
            
            $startTime = Get-Date
            $proc = Start-Process -FilePath "dism.exe" -ArgumentList $dismArgs -Wait -NoNewWindow -PassThru -RedirectStandardOutput "$env:TEMP\dism_update_output.txt" -RedirectStandardError "$env:TEMP\dism_update_error.txt"
            $duration = (Get-Date) - $startTime
            
            if ($proc.ExitCode -eq 0) {
                Write-Log -Message "$UpdateType update installed successfully in $($duration.TotalSeconds.ToString('0.0'))s: $($UpdateConfig.updateVersion)" -Level "OK"
                
                if ($UpdateType -eq "MSU") {
                    $script:UpdateStats.MSU++
                } else {
                    $script:UpdateStats.CAB++
                }
                
                return $true
            } else {
                $errorOutput = ""
                if (Test-Path "$env:TEMP\dism_update_error.txt") {
                    $errorOutput = Get-Content "$env:TEMP\dism_update_error.txt" -Raw
                }
                
                $retryCount++
                if ($retryCount -le $maxRetries) {
                    Write-Log -Message "DISM failed (attempt $retryCount), retrying... Exit code: $($proc.ExitCode)" -Level "WARNING"
                    Start-Sleep -Seconds 2
                } else {
                    throw "DISM failed after $($maxRetries + 1) attempts. Exit code: $($proc.ExitCode). Error: $errorOutput"
                }
            }
        } catch {
            if ($retryCount -ge $maxRetries) {
                Write-Log -Message "Failed to install $UpdateType update after $($maxRetries + 1) attempts: $($_.Exception.Message)" -Level "ERROR"
                return $false
            } else {
                $retryCount++
                Write-Log -Message "Exception occurred (attempt $retryCount), retrying... Error: $($_.Exception.Message)" -Level "WARNING"
                Start-Sleep -Seconds 2
            }
        } finally {
            # Cleanup temp files
            Remove-Item "$env:TEMP\dism_update_output.txt", "$env:TEMP\dism_update_error.txt" -Force -ErrorAction SilentlyContinue
        }
    }
    
    return $false
}

function Install-YunonaUpdate {
    <#
    .SYNOPSIS
        Stages EXE/MSI updates in Yunona for post-deployment installation
    #>
    param(
        [object]$UpdateConfig,
        [string]$UpdateType,
        [string]$YunonaTarget
    )
    
    $updateDir = $UpdateConfig.SourceDirectory
    $fileName = $UpdateConfig.downloadFileName
    $destFolder = Join-Path $YunonaTarget ([System.IO.Path]::GetFileNameWithoutExtension($fileName))
    
    if ($DryRun) {
        Write-Log -Message "[DRY RUN] Would stage $UpdateType update folder to Yunona: $destFolder" -Level "INFO"
        return $true
    }
    
    try {
        # Ensure Yunona is ready
        Ensure-YunonaCore
        
        # Copy entire update directory to preserve any supporting files
        Copy-Item $updateDir -Destination $destFolder -Recurse -Force
        
        Write-Log -Message "Staged $UpdateType update folder to Yunona: $destFolder" -Level "OK"
        
        if ($UpdateType -eq "EXE") {
            $script:UpdateStats.EXE++
        } else {
            $script:UpdateStats.MSI++
        }
        
        return $true
        
    } catch {
        Write-Log -Message "Failed to stage $UpdateType update to Yunona: $($_.Exception.Message)" -Level "ERROR"
        return $false
    }
}

function Install-Update {
    <#
    .SYNOPSIS
        Installs an update based on its type
    #>
    param([object]$UpdateConfig)
    
    $updateType = $UpdateConfig.updateType.ToLower()
    $mountPoint = $BuildConfig.mountPoint
    $yunonaTarget = Join-Path $mountPoint "Users\Public\Yunona"
    $filePath = $UpdateConfig.ValidatedFilePath
    
    Write-Log -Message "Processing update: $($UpdateConfig.updateName) [$($UpdateConfig.updateVersion)] [Type: $updateType]" -Level "INFO"
    
    $success = $false
    switch ($updateType) {
        'msu' {
            $success = Install-DISMUpdate -UpdateConfig $UpdateConfig -FilePath $filePath -MountPoint $mountPoint -UpdateType "MSU"
        }
        'cab' {
            $success = Install-DISMUpdate -UpdateConfig $UpdateConfig -FilePath $filePath -MountPoint $mountPoint -UpdateType "CAB"
        }
        'exe' {
            $success = Install-YunonaUpdate -UpdateConfig $UpdateConfig -UpdateType "EXE" -YunonaTarget $yunonaTarget
        }
        'msi' {
            $success = Install-YunonaUpdate -UpdateConfig $UpdateConfig -UpdateType "MSI" -YunonaTarget $yunonaTarget
        }
        default {
            Write-Log -Message "Unknown update type '$updateType' for update: $($UpdateConfig.updateName)" -Level "ERROR"
            $success = $false
        }
    }
    
    if ($success) {
        $script:UpdateStats.Processed++
        $script:ProcessedUpdates += $UpdateConfig
    } else {
        $script:UpdateStats.Failed++
        $script:FailedUpdates += $UpdateConfig
    }
    
    return $success
}

function Install-UpdatesSequential {
    <#
    .SYNOPSIS
        Installs updates sequentially with proper error handling
    #>
    param([array]$CompatibleUpdates)
    
    if ($CompatibleUpdates.Count -eq 0) {
        Write-Log -Message "No compatible updates to install" -Level "INFO"
        return
    }
    
    Write-Log -Message "Installing $($CompatibleUpdates.Count) compatible updates sequentially" -Level "INFO"
    
    foreach ($updateConfig in $CompatibleUpdates) {
        Install-Update -UpdateConfig $updateConfig
    }
}

#endregion

#region Validation and Reporting

function Write-UpdateSummary {
    <#
    .SYNOPSIS
        Writes comprehensive update installation summary with safe formatting
    #>
    param([string]$OsName, [int]$OsId)
    
    # Use simple text formatting to avoid encoding issues
    Write-LogSeparator -Title "UPDATE INTEGRATION SUMMARY" -Character "="
    
    Write-Log -Message "Operating System:       $OsName ($OsId)" -Level "INFO"
    Write-Log -Message "Total Updates Found:    $($script:UpdateStats.Total)" -Level "INFO"
    Write-Log -Message "Compatible Updates:     $($script:UpdateStats.Processed + $script:UpdateStats.Failed)" -Level "INFO"
    Write-Log -Message "Successfully Processed: $($script:UpdateStats.Processed)" -Level "INFO"
    Write-Log -Message "Failed:                 $($script:UpdateStats.Failed)" -Level "INFO"
    Write-Log -Message "Skipped (Incompatible): $($script:UpdateStats.Skipped)" -Level "INFO"
    Write-Log -Message " " -Level "INFO"
    Write-Log -Message "By Type:" -Level "INFO"
    Write-Log -Message "  MSU Updates:          $($script:UpdateStats.MSU)" -Level "INFO"
    Write-Log -Message "  CAB Updates:          $($script:UpdateStats.CAB)" -Level "INFO"
    Write-Log -Message "  EXE Installers:       $($script:UpdateStats.EXE)" -Level "INFO"
    Write-Log -Message "  MSI Installers:       $($script:UpdateStats.MSI)" -Level "INFO"
    
    Write-LogSeparator -Character "="
    
    if ($script:FailedUpdates.Count -gt 0) {
        Write-Log -Message "Failed updates:" -Level "ERROR"
        foreach ($failed in $script:FailedUpdates) {
            Write-Log -Message "  - $($failed.updateName) [$($failed.updateVersion)] [$($failed.updateType)]" -Level "ERROR"
        }
    }
    
    if ($script:UpdateStats.Processed -eq 0) {
        Write-Log -Message "No applicable updates were applied for OS $OsName ($OsId). Please verify the update metadata and file availability." -Level "WARNING"
    }
}

#endregion

#region Main Execution

try {
    # Initialize module
    Initialize-UpdateModule
    
    # Get OS information
    $osInfo = Get-OSInformation
    Write-Log -Message "Operating System: $($osInfo.Id) ($($osInfo.Name))" -Level "INFO"
    
    # Discover update configurations
    $allUpdateConfigs = Get-UpdateConfigurations
    
    if ($allUpdateConfigs.Count -eq 0) {
        Write-Log -Message "No update configurations found - update integration completed" -Level "WARNING"
        Write-UpdateSummary -OsName $osInfo.Name -OsId $osInfo.Id
        return
    }
    
    # Filter for compatible updates
    $compatibleUpdates = Get-CompatibleUpdates -UpdateConfigs $allUpdateConfigs -OsId $osInfo.Id -OsName $osInfo.Name
    
    if ($compatibleUpdates.Count -eq 0) {
        Write-Log -Message "No compatible updates found for this OS configuration" -Level "WARNING"
        Write-UpdateSummary -OsName $osInfo.Name -OsId $osInfo.Id
        return
    }
    
    # Install updates
    if ($DryRun) {
        Write-Log -Message "DRY RUN MODE - No actual changes will be made" -Level "INFO"
    }
    
    Install-UpdatesSequential -CompatibleUpdates $compatibleUpdates
    
    # Write summary
    Write-UpdateSummary -OsName $osInfo.Name -OsId $osInfo.Id
    
    Write-Log -Message "Update integration module completed successfully" -Level "OK"
    
} catch {
    Write-Log -Message "Update integration failed: $($_.Exception.Message)" -Level "ERROR"
    
    # Write failure summary
    Write-UpdateSummary -OsName "Unknown" -OsId 0
    
    throw "Update integration module failed: $($_.Exception.Message)"
    
} finally {
    # Cleanup any temporary resources
    if (Test-Path "$env:TEMP\dism_update_output.txt") {
        Remove-Item "$env:TEMP\dism_update_output.txt" -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path "$env:TEMP\dism_update_error.txt") {
        Remove-Item "$env:TEMP\dism_update_error.txt" -Force -ErrorAction SilentlyContinue
    }
}

#endregion