<#
.SYNOPSIS
    Prepares a customized Windows image (WIM) for deployment using a device-specific configuration.

.DESCRIPTION
    This script performs the following steps for a given device and OS ID:
    - Interactively selects a device profile if none is provided
    - Loads the combined build and device configuration from JSON files
    - Copies the original WIM image to a temporary path with integrity checking
    - Mounts the WIM image and integrates necessary drivers and updates
    - Unmounts and commits the modified WIM with rollback support
    - Exports the final WIM to an export directory
    - Cleans up all temporary files

    Enhanced with progress tracking, rollback mechanisms, and comprehensive error handling.

.PARAMETER Device
    The device profile name (without `.json`). If omitted, an interactive selection prompt is shown.

.PARAMETER OsId
    The operating system ID used to determine the configuration subset within the device profile.

.PARAMETER NoCleanup
    Skip cleanup of temporary files (useful for debugging failed operations).

.PARAMETER SkipDrivers
    Skip driver integration (for testing or when drivers are not needed).

.PARAMETER SkipUpdates
    Skip update integration (for testing or when updates are not needed).

.EXAMPLE
    .\kassia.ps1 -Device "RW-528A" -OsId 10
    Prepares a WIM image for device RW-528A using OS ID 10.

.EXAMPLE
    .\kassia.ps1 -OsId 11 -NoCleanup
    Starts with interactive device selection, uses OS ID 11, preserves temp files.

.NOTES
    Author   : Alexander Soloninov
    Version  : 1.1.0
    Module   : Kassia Build Engine
    Requires : Logging.psm1, ReadConfig.ps1, DISM, PowerShell 5.1+
    Tags     : WIM, Deployment, Driver Integration, Logging, Rollback

#>

param (
    [string]$Device,
    [int]$OsId,
    [switch]$NoCleanup,
    [switch]$SkipDrivers,
    [switch]$SkipUpdates
)

# Script variables for state tracking
$script:ExecutionState = @{
    OriginalWim = $null
    TempWim = $null
    MountPoint = $null
    IsMounted = $false
    TempFiles = @()
    StartTime = Get-Date
    CurrentStep = "INIT"
    TotalSteps = 9
    StepNumber = 0
}

#region Progress and State Management

function Write-Progress-Step {
    param(
        [string]$Activity,
        [string]$Status = "Processing...",
        [int]$PercentComplete = -1
    )
    
    $script:ExecutionState.StepNumber++
    $script:ExecutionState.CurrentStep = $Activity
    
    if ($PercentComplete -eq -1) {
        $PercentComplete = [math]::Round(($script:ExecutionState.StepNumber / $script:ExecutionState.TotalSteps) * 100)
    }
    
    Write-Progress -Activity "Kassia Image Preparation" -Status "$Activity - $Status" -PercentComplete $PercentComplete
    Write-Log -Message "Step $($script:ExecutionState.StepNumber)/$($script:ExecutionState.TotalSteps): $Activity" -Level "EXECUTING"
}

function Add-TempFile {
    param([string]$FilePath)
    if ($FilePath -and -not ($script:ExecutionState.TempFiles -contains $FilePath)) {
        $script:ExecutionState.TempFiles += $FilePath
    }
}

function Test-WimIntegrity {
    param(
        [string]$WimPath,
        [string]$Description = "WIM file"
    )
    
    Write-Log -Message "Validating $Description integrity: $WimPath" -Level "INFO"
    
    if (-not (Test-Path $WimPath)) {
        throw "$Description not found: $WimPath"
    }
    
    # Get WIM info to validate structure
    try {
        $dismOutput = & dism /Get-WimInfo /WimFile:$WimPath 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "DISM failed to read $Description (Exit code: $LASTEXITCODE)"
        }
        
        # Check for Index 1
        if (-not ($dismOutput -match "Index : 1")) {
            throw "$Description does not contain required Index 1"
        }
        
        Write-Log -Message "$Description integrity validation passed" -Level "OK"
        return $true
    } catch {
        throw "WIM integrity check failed for $Description`: $($_.Exception.Message)"
    }
}

function Invoke-Rollback {
    param([string]$Reason)
    
    Write-Log -Message "ROLLBACK INITIATED: $Reason" -Level "WARNING"
    
    try {
        # Unmount WIM if mounted
        if ($script:ExecutionState.IsMounted -and $script:ExecutionState.MountPoint) {
            Write-Log -Message "Unmounting WIM (discarding changes)..." -Level "WARNING"
            & dism /Unmount-Wim /MountDir:$script:ExecutionState.MountPoint /Discard 2>$null
            $script:ExecutionState.IsMounted = $false
        }
        
        # Clean up temporary files unless NoCleanup is specified
        if (-not $NoCleanup -and $script:ExecutionState.TempFiles.Count -gt 0) {
            Write-Log -Message "Cleaning up temporary files..." -Level "WARNING"
            foreach ($tempFile in $script:ExecutionState.TempFiles) {
                if (Test-Path $tempFile) {
                    Remove-Item $tempFile -Force -Recurse -ErrorAction SilentlyContinue
                    Write-Log -Message "Removed: $tempFile" -Level "DEBUG"
                }
            }
        }
        
        Write-Log -Message "Rollback completed" -Level "WARNING"
    } catch {
        Write-Log -Message "Error during rollback: $($_.Exception.Message)" -Level "ERROR"
    }
}

#endregion

#region Main Functions

function Select-DeviceProfile {
    if ($Device) {
        return $Device
    }
    
    Write-Progress-Step -Activity "Device Selection" -Status "Loading available profiles"
    
    $deviceConfigPath = Join-Path $PSScriptRoot "..\DeviceConfig"
    $jsonFiles = Get-ChildItem -Path $deviceConfigPath -Filter *.json -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name

    if (-not $jsonFiles) {
        throw "No device profiles found in $deviceConfigPath"
    }

    Write-Log -Message "No device specified. Available profiles:" -Level "INFO"
    for ($i = 0; $i -lt $jsonFiles.Count; $i++) {
        Write-Host "[$i] $($jsonFiles[$i])" -ForegroundColor Cyan
    }

    do {
        $selection = Read-Host "Please select a profile (0-$($jsonFiles.Count - 1))"
    } while (-not ($selection -match '^\d+$') -or [int]$selection -lt 0 -or [int]$selection -ge $jsonFiles.Count)

    $selectedDevice = [System.IO.Path]::GetFileNameWithoutExtension($jsonFiles[[int]$selection])
    Write-Log -Message "Selected device: $selectedDevice" -Level "OK"
    
    return $selectedDevice
}

function Get-Configuration {
    param([string]$DeviceName)
    
    Write-Progress-Step -Activity "Configuration Loading" -Status "Loading device and build configuration"
    
    $deviceFileName = "$DeviceName.json"
    try {
        $readConfigScript = Join-Path $PSScriptRoot "ReadConfig.ps1"
        Write-Log -Message "Loading configuration from: $readConfigScript" -Level "DEBUG"
        
        $config = & $readConfigScript -DeviceProfileFile $deviceFileName -OsId $OsId
        
        if (-not $config -or -not $config.DeviceProfile -or -not $config.BuildConfig) {
            throw "Invalid configuration structure returned"
        }
        
        Write-Log -Message "Loaded device: $($config.DeviceProfile.deviceId)" -Level "INFO"
        Write-Log -Message "Source WIM: $($config.BuildConfig.sourceWim)" -Level "DEBUG"
        
        return $config
    } catch {
        throw "Failed to load configuration for $deviceFileName`: $($_.Exception.Message)"
    }
}

function Copy-WimToTemp {
    param($Config)
    
    Write-Progress-Step -Activity "WIM Preparation" -Status "Copying source WIM to temporary location"
    
    $originalWim = $Config.BuildConfig.sourceWim
    $tempDir = $Config.BuildConfig.tempPath
    $tempWim = Join-Path $tempDir ([System.IO.Path]::GetFileName($originalWim))
    
    # Store paths for rollback
    $script:ExecutionState.OriginalWim = $originalWim
    $script:ExecutionState.TempWim = $tempWim
    
    # Validate source WIM
    Test-WimIntegrity -WimPath $originalWim -Description "Source WIM"
    
    # Create temp directory
    if (-not (Test-Path $tempDir)) {
        New-Item -Path $tempDir -ItemType Directory -Force | Out-Null
    }
    
    # Calculate file size for progress estimation
    $sourceSize = (Get-Item $originalWim).Length
    $sourceSizeMB = [math]::Round($sourceSize / 1MB, 2)
    
    Write-Log -Message "Copying WIM ($sourceSizeMB MB) to temporary location: $tempWim" -Level "EXECUTING"
    
    try {
        # Copy with progress monitoring
        $startTime = Get-Date
        Copy-Item -Path $originalWim -Destination $tempWim -Force
        $copyDuration = (Get-Date) - $startTime
        
        Write-Log -Message "WIM copy completed in $($copyDuration.TotalSeconds.ToString('0.0')) seconds" -Level "OK"
        
        # Validate copied WIM
        Test-WimIntegrity -WimPath $tempWim -Description "Temporary WIM copy"
        
        # Add to cleanup list
        Add-TempFile -FilePath $tempWim
        
        # Update config to point to temp WIM
        $Config.BuildConfig.sourceWim = $tempWim
        
        return $tempWim
    } catch {
        throw "WIM copy operation failed: $($_.Exception.Message)"
    }
}

function Mount-WimImage {
    param($Config)
    
    Write-Progress-Step -Activity "WIM Mounting" -Status "Mounting WIM image for modification"
    
    $mountPoint = $Config.BuildConfig.mountPoint
    $wimPath = $Config.BuildConfig.sourceWim
    
    # Store mount point for rollback
    $script:ExecutionState.MountPoint = $mountPoint
    
    Write-Log -Message "Mounting WIM image: $wimPath" -Level "EXECUTING"
    
    # Create mount directory
    if (-not (Test-Path $mountPoint)) {
        New-Item -Path $mountPoint -ItemType Directory -Force | Out-Null
    }
    
    # Add mount point to cleanup (in case of partial mount)
    Add-TempFile -FilePath $mountPoint
    
    try {
        # Mount WIM
        $mountOutput = & dism /Mount-Wim /WimFile:$wimPath /Index:1 /MountDir:$mountPoint 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            throw "DISM mount failed (Exit code: $LASTEXITCODE). Output: $($mountOutput -join '; ')"
        }
        
        $script:ExecutionState.IsMounted = $true
        Write-Log -Message "WIM mounted successfully at: $mountPoint" -Level "OK"
        
        # Verify mount by checking for Windows directory
        $windowsDir = Join-Path $mountPoint "Windows"
        if (-not (Test-Path $windowsDir)) {
            throw "Mount verification failed: Windows directory not found in mounted image"
        }
        
        Write-Log -Message "Mount verification passed" -Level "OK"
        
    } catch {
        $script:ExecutionState.IsMounted = $false
        throw "WIM mounting failed: $($_.Exception.Message)"
    }
}

function Invoke-UpdateIntegration {
    param($Config)
    
    if ($SkipUpdates) {
        Write-Log -Message "Skipping update integration (SkipUpdates flag set)" -Level "INFO"
        return
    }
    
    Write-Progress-Step -Activity "Update Integration" -Status "Applying Windows updates"
    
    $updateScript = Join-Path $PSScriptRoot "..\Engine\UpdateModule.ps1"
    
    if (-not (Test-Path $updateScript)) {
        Write-Log -Message "Update script not found: $updateScript" -Level "WARNING"
        return
    }
    
    try {
        Write-Log -Message "Starting update integration..." -Level "EXECUTING"
        & $updateScript -ProfileConfig $Config.DeviceProfile -BuildConfig $Config.BuildConfig
        
        if ($LASTEXITCODE -ne 0) {
            throw "Update integration failed with exit code: $LASTEXITCODE"
        }
        
        Write-Log -Message "Update integration completed successfully" -Level "OK"
    } catch {
        throw "Update integration failed: $($_.Exception.Message)"
    }
}

function Invoke-DriverIntegration {
    param($Config)
    
    if ($SkipDrivers) {
        Write-Log -Message "Skipping driver integration (SkipDrivers flag set)" -Level "INFO"
        return
    }
    
    Write-Progress-Step -Activity "Driver Integration" -Status "Installing device drivers"
    
    $driverScript = Join-Path $PSScriptRoot "..\Engine\DriverModule.ps1"
    
    if (-not (Test-Path $driverScript)) {
        throw "Driver script not found: $driverScript"
    }
    
    try {
        Write-Log -Message "Starting driver integration..." -Level "EXECUTING"
        & $driverScript -ProfileConfig $Config.DeviceProfile -BuildConfig $Config.BuildConfig
        
        if ($LASTEXITCODE -ne 0) {
            throw "Driver integration failed with exit code: $LASTEXITCODE"
        }
        
        Write-Log -Message "Driver integration completed successfully" -Level "OK"
    } catch {
        throw "Driver integration failed: $($_.Exception.Message)"
    }
}

function Dismount-WimImage {
    param($Config)
    
    Write-Progress-Step -Activity "WIM Finalization" -Status "Unmounting and committing changes"
    
    $mountPoint = $Config.BuildConfig.mountPoint
    
    try {
        Write-Log -Message "Unmounting and committing WIM changes..." -Level "EXECUTING"
        
        $dismountOutput = & dism /Unmount-Wim /MountDir:$mountPoint /Commit 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            throw "DISM unmount failed (Exit code: $LASTEXITCODE). Output: $($dismountOutput -join '; ')"
        }
        
        $script:ExecutionState.IsMounted = $false
        Write-Log -Message "WIM unmounted and committed successfully" -Level "OK"
        
        # Validate the modified WIM
        Test-WimIntegrity -WimPath $Config.BuildConfig.sourceWim -Description "Modified WIM"
        
    } catch {
        throw "WIM unmount/commit failed: $($_.Exception.Message)"
    }
}

function Export-FinalWim {
    param($Config)
    
    Write-Progress-Step -Activity "WIM Export" -Status "Exporting final customized image"
    
    $exportDir = $Config.BuildConfig.exportPath
    $deviceName = $Config.DeviceProfile.deviceId
    $tempWim = $Config.BuildConfig.sourceWim
    
    # Generate export filename
    $timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $exportName = "${OsId}_${deviceName}_${timestamp}.wim"
    $exportPath = Join-Path $exportDir $exportName
    
    # Create export directory
    if (-not (Test-Path $exportDir)) {
        New-Item -Path $exportDir -ItemType Directory -Force | Out-Null
    }
    
    try {
        Write-Log -Message "Exporting final WIM to: $exportPath" -Level "EXECUTING"
        
        $exportOutput = & dism /Export-Image /SourceImageFile:$tempWim /SourceIndex:1 /DestinationImageFile:$exportPath /Compress:max 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            throw "DISM export failed (Exit code: $LASTEXITCODE). Output: $($exportOutput -join '; ')"
        }
        
        # Validate exported WIM
        Test-WimIntegrity -WimPath $exportPath -Description "Exported WIM"
        
        # Get file size for reporting
        $exportSize = (Get-Item $exportPath).Length
        $exportSizeMB = [math]::Round($exportSize / 1MB, 2)
        
        Write-Log -Message "WIM export completed successfully: $exportPath ($exportSizeMB MB)" -Level "OK"
        return $exportPath
        
    } catch {
        throw "WIM export failed: $($_.Exception.Message)"
    }
}

function Invoke-Cleanup {
    if ($NoCleanup) {
        Write-Log -Message "Skipping cleanup (NoCleanup flag set)" -Level "INFO"
        Write-Log -Message "Temporary files preserved for debugging:" -Level "INFO"
        foreach ($tempFile in $script:ExecutionState.TempFiles) {
            if (Test-Path $tempFile) {
                Write-Log -Message "  - $tempFile" -Level "INFO"
            }
        }
        return
    }
    
    Write-Progress-Step -Activity "Cleanup" -Status "Removing temporary files"
    
    Write-Log -Message "Cleaning up temporary files..." -Level "EXECUTING"
    
    $cleanedCount = 0
    foreach ($tempFile in $script:ExecutionState.TempFiles) {
        if (Test-Path $tempFile) {
            try {
                Remove-Item $tempFile -Force -Recurse -ErrorAction Stop
                Write-Log -Message "Removed: $tempFile" -Level "DEBUG"
                $cleanedCount++
            } catch {
                Write-Log -Message "Failed to remove $tempFile`: $($_.Exception.Message)" -Level "WARNING"
            }
        }
    }
    
    Write-Log -Message "Cleanup completed. Removed $cleanedCount temporary items." -Level "OK"
}

#endregion

#region Main Execution

try {
    Write-Log -Message "Kassia Engine v1.1.0 starting..." -Level "INIT"
    Write-Log -Message "Device: $(if ($Device) { $Device } else { 'Interactive Selection' }), OsId: $OsId" -Level "INFO"
    
    # Step 1: Device Selection
    $selectedDevice = Select-DeviceProfile
    
    # Step 2: Configuration Loading  
    $config = Get-Configuration -DeviceName $selectedDevice
    
    # Step 3: WIM Preparation
    $tempWim = Copy-WimToTemp -Config $config
    
    # Step 4: WIM Mounting
    Mount-WimImage -Config $config
    
    # Step 5: Update Integration
    Invoke-UpdateIntegration -Config $config
    
    # Step 6: Driver Integration
    Invoke-DriverIntegration -Config $config
    
    # Step 7: WIM Finalization
    Dismount-WimImage -Config $config
    
    # Step 8: WIM Export
    $exportPath = Export-FinalWim -Config $config
    
    # Step 9: Cleanup
    Invoke-Cleanup
    
    # Success summary
    $duration = (Get-Date) - $script:ExecutionState.StartTime
    Write-Progress -Activity "Kassia Image Preparation" -Status "Completed Successfully" -PercentComplete 100
    
    Write-Log -Message "=== KASSIA EXECUTION COMPLETED SUCCESSFULLY ===" -Level "OK"
    Write-Log -Message "Device: $($config.DeviceProfile.deviceId)" -Level "INFO"
    Write-Log -Message "Output: $exportPath" -Level "INFO"
    Write-Log -Message "Duration: $($duration.ToString('hh\:mm\:ss'))" -Level "INFO"
    
} catch {
    # Error handling with rollback
    $errorMessage = $_.Exception.Message
    Write-Log -Message "FATAL ERROR: $errorMessage" -Level "ERROR"
    
    # Attempt rollback
    Invoke-Rollback -Reason $errorMessage
    
    # Final error report
    $duration = (Get-Date) - $script:ExecutionState.StartTime
    Write-Log -Message "=== KASSIA EXECUTION FAILED ===" -Level "ERROR"
    Write-Log -Message "Error: $errorMessage" -Level "ERROR"
    Write-Log -Message "Duration: $($duration.ToString('hh\:mm\:ss'))" -Level "ERROR"
    
    Write-Progress -Activity "Kassia Image Preparation" -Status "Failed: $errorMessage" -PercentComplete 100
    
    exit 1
    
} finally {
    # Ensure progress is completed
    Write-Progress -Activity "Kassia Image Preparation" -Completed
}

#endregion