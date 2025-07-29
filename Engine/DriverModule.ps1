<#
.SYNOPSIS
    Kassia Driver Integration Module - Installs and manages device drivers for Windows images.

.DESCRIPTION
    This module handles the integration of device-specific drivers into mounted Windows images.
    It supports multiple driver types (INF, APPX, EXE), validates compatibility, and provides
    comprehensive error handling with rollback capabilities.
    
    Enhanced with parallel processing, dynamic device encoding, and improved validation.

.PARAMETER ProfileConfig
    Device profile configuration object containing device ID and driver family IDs.

.PARAMETER BuildConfig
    Build configuration object containing paths and OS information.

.PARAMETER MaxParallelJobs
    Maximum number of parallel driver installation jobs (default: 3).

.PARAMETER SkipValidation
    Skip driver validation checks (for testing or special cases).

.PARAMETER DryRun
    Simulate driver installation without making actual changes.

.EXAMPLE
    .\DriverModule.ps1 -ProfileConfig $deviceProfile -BuildConfig $buildConfig
    
    Installs drivers for the specified device profile.

.EXAMPLE
    .\DriverModule.ps1 -ProfileConfig $deviceProfile -BuildConfig $buildConfig -DryRun
    
    Simulates driver installation to show what would be processed.

.NOTES
    Author   : Alexander Soloninov
    Version  : 1.1.0
    Module   : Kassia Build Engine
    Requires : DISM, PowerShell 5.1+, Logging.psm1
    Tags     : Drivers, DISM, Parallel Processing, Validation

#>

param (
    [Parameter(Mandatory)]
    [ValidateNotNull()]
    [pscustomobject]$ProfileConfig,

    [Parameter(Mandatory)]
    [ValidateNotNull()]
    [pscustomobject]$BuildConfig,

    [ValidateRange(1, 10)]
    [int]$MaxParallelJobs = 3,

    [switch]$SkipValidation,
    
    [switch]$DryRun
)

# Module constants and state
$script:ModuleVersion = "1.1.0"
$script:ProcessedDrivers = @()
$script:FailedDrivers = @()
$script:DriverStats = @{
    Total = 0
    Processed = 0
    Skipped = 0
    Failed = 0
    INF = 0
    APPX = 0
    EXE = 0
}

#region Configuration and Initialization

function Initialize-DriverModule {
    <#
    .SYNOPSIS
        Initializes the driver module and validates prerequisites
    #>
    
    Write-Log -Message "Driver Integration Module v$script:ModuleVersion starting..." -Level "INIT"
    
    # Validate required paths
    $requiredPaths = @{
        'Driver Root' = $BuildConfig.driverRoot
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
    
    # Validate profile configuration
    if (-not $ProfileConfig.deviceId) {
        throw "Device ID not found in ProfileConfig"
    }
    
    if (-not $ProfileConfig.driverFamilyIds) {
        Write-Log -Message "No driver family IDs specified for device $($ProfileConfig.deviceId)" -Level "WARNING"
        $ProfileConfig | Add-Member -NotePropertyName driverFamilyIds -NotePropertyValue @() -Force
    }
}

function Get-DeviceEncoding {
    <#
    .SYNOPSIS
        Retrieves device encoding using device family mapping
    #>
    param([string]$DeviceId)
    
    $idsPath = Join-Path $global:rootPath "Engine\IDs"
    
    # Load device family mapping
    $familyMappingPath = Join-Path $idsPath "deviceFamilyMapping.json"
    
    if (-not (Test-Path $familyMappingPath)) {
        throw "Device family mapping file not found: $familyMappingPath"
    }
    
    try {
        $familyMapping = Get-Content $familyMappingPath -Raw | ConvertFrom-Json
        
        if (-not $familyMapping.familyMapping.$DeviceId) {
            $availableFamilies = ($familyMapping.familyMapping | Get-Member -MemberType NoteProperty).Name -join ', '
            throw "Device family '$DeviceId' not found in familyMapping. Available families: $availableFamilies"
        }
        
        $familyInfo = $familyMapping.familyMapping.$DeviceId
        $deviceIds = $familyInfo.deviceIds
        
        Write-Log -Message "Device family '$DeviceId' maps to device IDs: $($deviceIds -join ', ')" -Level "DEBUG"
        Write-Log -Message "Supported models: $($familyInfo.models -join ', ')" -Level "DEBUG"
        
        return @{
            Id = $deviceIds[0]  # Use first device ID as primary
            Name = $familyInfo.description
            DeviceFamily = $DeviceId
            AllDeviceIds = $deviceIds
            SupportedModels = $familyInfo.models
            Source = "FamilyMapping"
        }
        
    } catch {
        throw "Failed to load device family mapping: $($_.Exception.Message)"
    }
}

function Get-OSInformation {
    <#
    .SYNOPSIS
        Retrieves OS information and friendly name
    #>
    param([int]$OsId)
    
    # Determine OS ID from multiple sources
    $resolvedOsId = $OsId
    if (-not $resolvedOsId) { $resolvedOsId = $ProfileConfig.selectedOSId }
    if (-not $resolvedOsId) { $resolvedOsId = $BuildConfig.selectedOSId }
    if (-not $resolvedOsId -and $ProfileConfig.supportedOS) { 
        $resolvedOsId = $ProfileConfig.supportedOS[0] 
    }
    
    if (-not $resolvedOsId) {
        throw "Could not determine OS ID from ProfileConfig or BuildConfig"
    }
    
    # Update ProfileConfig with resolved OS ID
    $ProfileConfig | Add-Member -NotePropertyName selectedOSId -NotePropertyValue $resolvedOsId -Force
    
    # Load friendly name
    $osName = "Unknown OS"
    $idsPath = Join-Path $global:rootPath "Engine\IDs"
    $osJsonPath = Join-Path $idsPath "supportedOperatingSystems.json"
    
    if (Test-Path $osJsonPath) {
        try {
            $osData = Get-Content $osJsonPath -Raw | ConvertFrom-Json
            $match = $osData | Where-Object { $_.id -eq $resolvedOsId }
            if ($match) { $osName = $match.text }
        } catch {
            Write-Log -Message "Failed to parse supportedOperatingSystems.json: $($_.Exception.Message)" -Level "WARNING"
        }
    }
    
    return @{
        Id = $resolvedOsId
        Name = $osName
    }
}

#endregion

#region Yunona Management

function Ensure-YunonaCore {
    <#
    .SYNOPSIS
        Ensures Yunona core files are present and up to date with thread safety
    #>
    
    # Thread-safe check using a script-scoped variable
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

#region Driver Discovery and Validation

function Get-DriverConfigurations {
    <#
    .SYNOPSIS
        Discovers and loads all driver configuration files
    #>
    
    $driverRoot = $BuildConfig.driverRoot
    
    if (-not (Test-Path $driverRoot)) {
        Write-Log -Message "Driver root directory not found: $driverRoot" -Level "WARNING"
        return @()
    }
    
    $driverJsons = Get-ChildItem -Path $driverRoot -Recurse -Filter *.json -File -ErrorAction SilentlyContinue |
        Sort-Object FullName -Unique
    
    if (-not $driverJsons) {
        Write-Log -Message "No driver JSON files found in $driverRoot" -Level "WARNING"
        return @()
    }
    
    # Load and parse configurations
    $driverConfigs = @()
    foreach ($jsonFile in $driverJsons) {
        try {
            $config = Get-Content $jsonFile.FullName -Raw | ConvertFrom-Json
            
            # Add file path for reference
            $config | Add-Member -NotePropertyName SourcePath -NotePropertyValue $jsonFile.FullName -Force
            $config | Add-Member -NotePropertyName SourceDirectory -NotePropertyValue $jsonFile.Directory.FullName -Force
            
            # Add order property if missing
            if (-not $config.order) {
                $config | Add-Member -NotePropertyName order -NotePropertyValue 9999 -Force
            }
            
            $driverConfigs += $config
            
        } catch {
            Write-Log -Message "Failed to parse driver config: $($jsonFile.FullName) - $($_.Exception.Message)" -Level "ERROR"
        }
    }
    
    # Sort by order
    $sortedConfigs = $driverConfigs | Sort-Object order, SourcePath
    
    Write-Log -Message "Discovered $($sortedConfigs.Count) driver configurations" -Level "INFO"
    return $sortedConfigs
}

function Test-DriverCompatibility {
    <#
    .SYNOPSIS
        Tests if a driver is compatible with the current device family and OS
    #>
    param(
        [object]$DriverConfig,
        [object]$DeviceEncoding,
        [int]$OsId,
        [array]$RequiredFamilyIds
    )
    
    if ($SkipValidation) {
        Write-Log -Message "Skipping compatibility validation for: $($DriverConfig.driverName)" -Level "DEBUG"
        return $true
    }
    
    $compatibility = @{
        DeviceMatch = $false
        OSMatch = $false
        FamilyMatch = $false
        Overall = $false
    }
    
    # Check device compatibility using all device IDs from the family
    if ($DriverConfig.supportedDevices) {
        # Check if any of the device family's IDs are supported by this driver
        foreach ($deviceId in $DeviceEncoding.AllDeviceIds) {
            if ($DriverConfig.supportedDevices -contains $deviceId) {
                $compatibility.DeviceMatch = $true
                Write-Log -Message "Device match found: Driver supports device ID $deviceId from family $($DeviceEncoding.DeviceFamily)" -Level "DEBUG"
                break
            }
        }
    }
    
    # Check OS compatibility
    if ($DriverConfig.supportedOperatingSystems -and $DriverConfig.supportedOperatingSystems -contains $OsId) {
        $compatibility.OSMatch = $true
    }
    
    # Check family compatibility
    if ($DriverConfig.driverFamilyId -and $RequiredFamilyIds -contains $DriverConfig.driverFamilyId) {
        $compatibility.FamilyMatch = $true
    }
    
    $compatibility.Overall = $compatibility.DeviceMatch -and $compatibility.OSMatch -and $compatibility.FamilyMatch
    
    Write-Log -Message "Compatibility check for $($DriverConfig.driverName): Device=$($compatibility.DeviceMatch), OS=$($compatibility.OSMatch), Family=$($compatibility.FamilyMatch)" -Level "DEBUG"
    
    return $compatibility
}

function Get-CompatibleDrivers {
    <#
    .SYNOPSIS
        Filters driver configurations for compatibility
    #>
    param(
        [array]$DriverConfigs,
        [object]$DeviceEncoding,
        [int]$OsId,
        [array]$RequiredFamilyIds
    )
    
    $compatibleDrivers = @()
    $script:DriverStats.Total = $DriverConfigs.Count
    
    foreach ($driverConfig in $DriverConfigs) {
        $compatibility = Test-DriverCompatibility -DriverConfig $driverConfig -DeviceEncoding $DeviceEncoding -OsId $OsId -RequiredFamilyIds $RequiredFamilyIds
        
        if ($compatibility.Overall) {
            $compatibleDrivers += @{
                Config = $driverConfig
                Compatibility = $compatibility
            }
        } else {
            $script:DriverStats.Skipped++
            Write-Log -Message "Skipping incompatible driver: $($driverConfig.driverName)" -Level "DEBUG"
        }
    }
    
    Write-Log -Message "Found $($compatibleDrivers.Count) compatible drivers out of $($DriverConfigs.Count) total" -Level "INFO"
    return $compatibleDrivers
}

#endregion

#region Driver Installation

function Install-INFDriver {
    <#
    .SYNOPSIS
        Installs INF-based drivers using DISM
    #>
    param(
        [object]$DriverConfig,
        [string]$SourceDirectory,
        [string]$MountPoint
    )
    
    if ($DryRun) {
        Write-Log -Message "[DRY RUN] Would install INF drivers from: $SourceDirectory" -Level "INFO"
        return $true
    }
    
    try {
        Write-Log -Message "Installing INF drivers from: $SourceDirectory" -Level "EXECUTING"
        
        $dismArgs = @(
            "/Image:$MountPoint"
            "/Add-Driver"
            "/Driver:$SourceDirectory"
            "/Recurse"
        )
        
        $startTime = Get-Date
        $proc = Start-Process -FilePath "dism.exe" -ArgumentList $dismArgs -Wait -NoNewWindow -PassThru -RedirectStandardOutput "$env:TEMP\dism_output.txt" -RedirectStandardError "$env:TEMP\dism_error.txt"
        $duration = (Get-Date) - $startTime
        
        if ($proc.ExitCode -eq 0) {
            Write-Log -Message "INF drivers installed successfully in $($duration.TotalSeconds.ToString('0.0'))s" -Level "OK"
            $script:DriverStats.INF++
            return $true
        } else {
            $errorOutput = ""
            if (Test-Path "$env:TEMP\dism_error.txt") {
                $errorOutput = Get-Content "$env:TEMP\dism_error.txt" -Raw
            }
            throw "DISM failed with exit code $($proc.ExitCode): $errorOutput"
        }
    } catch {
        Write-Log -Message "Failed to install INF drivers: $($_.Exception.Message)" -Level "ERROR"
        return $false
    } finally {
        # Cleanup temp files
        Remove-Item "$env:TEMP\dism_output.txt", "$env:TEMP\dism_error.txt" -Force -ErrorAction SilentlyContinue
    }
}

function Install-APPXDriver {
    <#
    .SYNOPSIS
        Installs APPX-based drivers by copying to Yunona
    #>
    param(
        [object]$DriverConfig,
        [string]$SourceDirectory,
        [string]$YunonaTarget
    )
    
    $appxFiles = Get-ChildItem -Path $SourceDirectory -Filter *.appx -Recurse -ErrorAction SilentlyContinue
    
    if (-not $appxFiles) {
        Write-Log -Message "No APPX files found in: $SourceDirectory" -Level "WARNING"
        return $false
    }
    
    $installed = 0
    foreach ($appxFile in $appxFiles) {
        $destFolder = Join-Path $YunonaTarget $appxFile.Directory.Name
        
        if ($DryRun) {
            Write-Log -Message "[DRY RUN] Would copy APPX folder: $($appxFile.Directory.Name) -> $destFolder" -Level "INFO"
            $installed++
        } else {
            try {
                Copy-Item $appxFile.Directory.FullName -Destination $destFolder -Recurse -Force
                Write-Log -Message "Copied APPX folder: $($appxFile.Directory.Name) -> $destFolder" -Level "OK"
                $installed++
            } catch {
                Write-Log -Message "Failed to copy APPX folder $($appxFile.Directory.Name): $($_.Exception.Message)" -Level "ERROR"
            }
        }
    }
    
    if ($installed -gt 0) {
        $script:DriverStats.APPX += $installed
        return $true
    }
    
    return $false
}

function Install-EXEDriver {
    <#
    .SYNOPSIS
        Installs EXE-based drivers by copying to Yunona
    #>
    param(
        [object]$DriverConfig,
        [string]$SourceDirectory,
        [string]$YunonaTarget
    )
    
    $exeFiles = Get-ChildItem -Path $SourceDirectory -Filter *.exe -Recurse -ErrorAction SilentlyContinue
    
    if (-not $exeFiles) {
        Write-Log -Message "No EXE files found in: $SourceDirectory" -Level "WARNING"
        return $false
    }
    
    $installed = 0
    foreach ($exeFile in $exeFiles) {
        $destFolder = Join-Path $YunonaTarget $exeFile.Directory.Name
        
        if ($DryRun) {
            Write-Log -Message "[DRY RUN] Would copy EXE folder: $($exeFile.Directory.Name) -> $destFolder" -Level "INFO"
            $installed++
        } else {
            try {
                Copy-Item $exeFile.Directory.FullName -Destination $destFolder -Recurse -Force
                Write-Log -Message "Copied EXE folder: $($exeFile.Directory.Name) -> $destFolder" -Level "OK"
                $installed++
            } catch {
                Write-Log -Message "Failed to copy EXE folder $($exeFile.Directory.Name): $($_.Exception.Message)" -Level "ERROR"
            }
        }
    }
    
    if ($installed -gt 0) {
        $script:DriverStats.EXE += $installed
        return $true
    }
    
    return $false
}

function Install-Driver {
    <#
    .SYNOPSIS
        Installs a driver based on its type
    #>
    param([object]$DriverInfo)
    
    $driverConfig = $DriverInfo.Config
    $driverType = $driverConfig.driverType.ToLower()
    $sourceDir = $driverConfig.SourceDirectory
    $mountPoint = $BuildConfig.mountPoint
    $yunonaTarget = Join-Path $mountPoint "Users\Public\Yunona"
    
    Write-Log -Message "Processing driver: $($driverConfig.driverName) [Type: $driverType]" -Level "INFO"
    
    # Ensure Yunona is available for APPX/EXE drivers
    if ($driverType -in @('appx', 'exe')) {
        Ensure-YunonaCore
    }
    
    $success = $false
    switch ($driverType) {
        'inf' {
            $success = Install-INFDriver -DriverConfig $driverConfig -SourceDirectory $sourceDir -MountPoint $mountPoint
        }
        'appx' {
            $success = Install-APPXDriver -DriverConfig $driverConfig -SourceDirectory $sourceDir -YunonaTarget $yunonaTarget
        }
        'exe' {
            $success = Install-EXEDriver -DriverConfig $driverConfig -SourceDirectory $sourceDir -YunonaTarget $yunonaTarget
        }
        default {
            Write-Log -Message "Unknown driver type '$driverType' for driver: $($driverConfig.driverName)" -Level "ERROR"
            $success = $false
        }
    }
    
    if ($success) {
        $script:DriverStats.Processed++
        $script:ProcessedDrivers += $driverConfig
    } else {
        $script:DriverStats.Failed++
        $script:FailedDrivers += $driverConfig
    }
    
    return $success
}

function Install-DriversSequential {
    <#
    .SYNOPSIS
        Installs drivers sequentially (PowerShell 5 compatible)
    #>
    param([array]$CompatibleDrivers)
    
    if ($CompatibleDrivers.Count -eq 0) {
        Write-Log -Message "No compatible drivers to install" -Level "INFO"
        return
    }
    
    Write-Log -Message "Installing $($CompatibleDrivers.Count) compatible drivers sequentially" -Level "INFO"
    
    foreach ($driverInfo in $CompatibleDrivers) {
        Install-Driver -DriverInfo $driverInfo
    }
}

#endregion

#region Validation and Reporting

function Test-DriverFamilyCoverage {
    <#
    .SYNOPSIS
        Validates that all expected driver families were processed
    #>
    param(
        [array]$RequiredFamilyIds,
        [array]$ProcessedDrivers
    )
    
    if (-not $RequiredFamilyIds -or $RequiredFamilyIds.Count -eq 0) {
        Write-Log -Message "No driver family validation required" -Level "DEBUG"
        return
    }
    
    # Load known families for friendly names
    $knownFamilies = @{}
    $knownFamiliesPath = Join-Path $global:rootPath "Engine\IDs\driverFamilyId.json"
    
    if (Test-Path $knownFamiliesPath) {
        try {
            $knownFamiliesRaw = Get-Content $knownFamiliesPath -Raw | ConvertFrom-Json
            foreach ($entry in $knownFamiliesRaw) {
                if ($entry.id) {
                    $label = if ($entry.friendlyName) { $entry.friendlyName } elseif ($entry.systemName) { $entry.systemName } elseif ($entry.name) { $entry.name } else { "Unknown" }
                    $knownFamilies[$entry.id] = $label
                }
            }
        } catch {
            Write-Log -Message "Failed to parse driverFamilyId.json: $($_.Exception.Message)" -Level "WARNING"
        }
    }
    
    # Check coverage
    $processedFamilyIds = $ProcessedDrivers | Where-Object { $_.driverFamilyId } | ForEach-Object { $_.driverFamilyId } | Sort-Object -Unique
    $missingFamilies = $RequiredFamilyIds | Where-Object { $_ -notin $processedFamilyIds }
    
    if ($missingFamilies.Count -gt 0) {
        Write-Log -Message "WARNING: The following expected driver families were not processed:" -Level "WARNING"
        foreach ($familyId in $missingFamilies) {
            $familyName = if ($knownFamilies[$familyId]) { $knownFamilies[$familyId] } else { "Unknown" }
            Write-Log -Message "  - Missing driver family: $familyId ($familyName)" -Level "WARNING"
        }
    } else {
        Write-Log -Message "All expected driver families were successfully processed" -Level "OK"
    }
}

function Write-DriverSummary {
    <#
    .SYNOPSIS
        Writes comprehensive driver installation summary with safe formatting
    #>
    
    # Use simple text formatting to avoid encoding issues
    Write-LogSeparator -Title "DRIVER INTEGRATION SUMMARY" -Character "="
    
    Write-Log -Message "Total Drivers Found:    $($script:DriverStats.Total)" -Level "INFO"
    Write-Log -Message "Compatible Drivers:     $($script:DriverStats.Processed + $script:DriverStats.Failed)" -Level "INFO"
    Write-Log -Message "Successfully Processed: $($script:DriverStats.Processed)" -Level "INFO"
    Write-Log -Message "Failed:                 $($script:DriverStats.Failed)" -Level "INFO"
    Write-Log -Message "Skipped (Incompatible): $($script:DriverStats.Skipped)" -Level "INFO"
    Write-Log -Message " " -Level "INFO"
    Write-Log -Message "By Type:" -Level "INFO"
    Write-Log -Message "  INF Drivers:          $($script:DriverStats.INF)" -Level "INFO"
    Write-Log -Message "  APPX Packages:        $($script:DriverStats.APPX)" -Level "INFO"
    Write-Log -Message "  EXE Installers:       $($script:DriverStats.EXE)" -Level "INFO"
    
    Write-LogSeparator -Character "="
    
    if ($script:FailedDrivers.Count -gt 0) {
        Write-Log -Message "Failed drivers:" -Level "ERROR"
        foreach ($failed in $script:FailedDrivers) {
            Write-Log -Message "  - $($failed.driverName) [$($failed.driverType)]" -Level "ERROR"
        }
    }
}

#endregion

#region Main Execution

try {
    # Initialize module
    Initialize-DriverModule
    
    # Get device encoding
    $deviceEncoding = Get-DeviceEncoding -DeviceId $ProfileConfig.deviceId
    Write-Log -Message "Device: $($ProfileConfig.deviceId) -> Family: $($deviceEncoding.DeviceFamily) -> Primary ID: $($deviceEncoding.Id)" -Level "INFO"
    Write-Log -Message "All Device IDs: $($deviceEncoding.AllDeviceIds -join ', ')" -Level "DEBUG"
    Write-Log -Message "Supported Models: $($deviceEncoding.SupportedModels -join ', ')" -Level "DEBUG"
    
    # Get OS information
    $osInfo = Get-OSInformation -OsId $ProfileConfig.selectedOSId
    Write-Log -Message "Operating System: $($osInfo.Id) ($($osInfo.Name))" -Level "INFO"
    
    # Get required driver families
    $driverFamilyIds = $ProfileConfig.driverFamilyIds | Sort-Object -Unique
    Write-Log -Message "Required driver families: $($driverFamilyIds -join ', ')" -Level "DEBUG"
    
    # Discover driver configurations
    $allDriverConfigs = Get-DriverConfigurations
    
    if ($allDriverConfigs.Count -eq 0) {
        Write-Log -Message "No driver configurations found - driver integration completed" -Level "WARNING"
        return
    }
    
    # Filter for compatible drivers
    $compatibleDrivers = Get-CompatibleDrivers -DriverConfigs $allDriverConfigs -DeviceEncoding $deviceEncoding -OsId $osInfo.Id -RequiredFamilyIds $driverFamilyIds
    
    if ($compatibleDrivers.Count -eq 0) {
        Write-Log -Message "No compatible drivers found for this configuration" -Level "WARNING"
        return
    }
    
    # Install drivers
    if ($DryRun) {
        Write-Log -Message "DRY RUN MODE - No actual changes will be made" -Level "INFO"
    }
    
    Install-DriversSequential -CompatibleDrivers $compatibleDrivers
    
    # Validate driver family coverage
    Test-DriverFamilyCoverage -RequiredFamilyIds $driverFamilyIds -ProcessedDrivers $script:ProcessedDrivers
    
    # Write summary
    Write-DriverSummary
    
    Write-Log -Message "Driver integration module completed successfully" -Level "OK"
    
} catch {
    Write-Log -Message "Driver integration failed: $($_.Exception.Message)" -Level "ERROR"
    
    # Write failure summary
    Write-DriverSummary
    
    throw "Driver integration module failed: $($_.Exception.Message)"
    
} finally {
    # Cleanup any temporary resources
    if (Test-Path "$env:TEMP\dism_output.txt") {
        Remove-Item "$env:TEMP\dism_output.txt" -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path "$env:TEMP\dism_error.txt") {
        Remove-Item "$env:TEMP\dism_error.txt" -Force -ErrorAction SilentlyContinue
    }
}

#endregion