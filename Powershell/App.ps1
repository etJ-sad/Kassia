<#
.SYNOPSIS
    Kassia Windows Image Preparation System - Main Entry Point

.DESCRIPTION
    This script serves as the main entry point for the Kassia Windows image customization system.
    It handles parameter validation, logging initialization, and orchestrates the execution of 
    the core engine with proper error handling.

.PARAMETER Device
    The device profile name (without .json extension). If omitted, an interactive selection will be presented.
    
.PARAMETER OsId
    The operating system ID that determines which WIM file and configurations to use.

.PARAMETER EnableDebug
    Enable debug-level logging for detailed troubleshooting information.

.PARAMETER Validate
    Only validate configuration and parameters without executing the build process.

.EXAMPLE
    .\App.ps1 -Device "RW-528A" -OsId 10
    
    Prepares a WIM image for device RW-528A using OS ID 10.

.EXAMPLE
    .\App.ps1 -OsId 11 -EnableDebug
    
    Starts with interactive device selection, uses OS ID 11, with debug logging enabled.

.EXAMPLE
    .\App.ps1 -Device "RW-528A" -OsId 10 -Validate
    
    Validates the configuration for RW-528A with OS ID 10 without executing the build.

.NOTES
    Author      : Alexander Soloninov
    Version     : 1.1.0
    Module      : Kassia Build Engine
    Requires    : PowerShell 5.1+, DISM, Administrator privileges
    LastUpdated : 2025-06-30
#>

param (
    [string]$Device,
    [int]$OsId,
    [switch]$EnableDebug,  # Renamed to avoid conflict with built-in Debug parameter
    [switch]$Validate      # New: Validate configuration only
)

# Script constants
$script:ScriptVersion = "1.1.0"
$script:StartTime = Get-Date
$ErrorActionPreference = "Stop"

# Helper function to validate prerequisites
function Test-Prerequisites {
    $issues = @()
    
    # Check PowerShell version
    if ($PSVersionTable.PSVersion.Major -lt 5) {
        $issues += "PowerShell 5.1 or later required. Current: $($PSVersionTable.PSVersion)"
    }
    
    # Check administrator privileges
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        $issues += "Administrator privileges required for DISM operations"
    }
    
    # Check DISM availability
    try {
        $null = & dism /? 2>$null
        if ($LASTEXITCODE -ne 0) {
            $issues += "DISM tool is not available or not working properly"
        }
    } catch {
        $issues += "DISM tool verification failed: $($_.Exception.Message)"
    }
    
    # Check disk space (minimum 10GB)
    $systemDrive = $env:SystemDrive
    try {
        $disk = Get-WmiObject -Class Win32_LogicalDisk -Filter "DeviceID='$systemDrive'"
        $freeSpaceGB = [math]::Round($disk.FreeSpace / 1GB, 2)
        if ($freeSpaceGB -lt 10) {
            $issues += "Insufficient disk space. Required: 10GB, Available: ${freeSpaceGB}GB"
        }
    } catch {
        $issues += "Could not check disk space: $($_.Exception.Message)"
    }
    
    return $issues
}

# Helper function to validate parameters
function Test-Parameters {
    # Validate OsId parameter
    if ($OsId -le 0) {
        throw "OsId must be a positive integer. Provided: $OsId"
    }
    
    # Check if config.json exists and validate OsId
    $configFile = Join-Path $PSScriptRoot "config.json"
    if (Test-Path $configFile) {
        try {
            $config = Get-Content $configFile -Raw | ConvertFrom-Json
            $availableOsIds = @()
            $config.osWimMap.PSObject.Properties | ForEach-Object { $availableOsIds += [int]$_.Name }
            
            if ($OsId -notin $availableOsIds) {
                throw "Invalid OsId '$OsId'. Available: $($availableOsIds -join ', ')"
            }
        } catch {
            if ($_.Exception.Message -like "*Invalid OsId*") {
                throw
            }
            Write-Warning "Could not validate OsId: $($_.Exception.Message)"
        }
    }
    
    # Validate Device if provided
    if ($Device) {
        $deviceConfigPath = Join-Path $PSScriptRoot "DeviceConfig\$Device.json"
        if (-not (Test-Path $deviceConfigPath)) {
            throw "Device configuration not found: $deviceConfigPath"
        }
        
        # Check if device supports the OS
        try {
            $deviceConfig = Get-Content $deviceConfigPath -Raw | ConvertFrom-Json
            if ($deviceConfig.supportedOS -and $OsId -notin $deviceConfig.supportedOS) {
                throw "Device '$Device' does not support OS ID '$OsId'. Supported: $($deviceConfig.supportedOS -join ', ')"
            }
        } catch {
            if ($_.Exception.Message -like "*does not support OS ID*") {
                throw
            }
            Write-Warning "Could not validate device OS support: $($_.Exception.Message)"
        }
    }
}

# Helper function to create required directories
function Initialize-Directories {
    $directories = @(
        "Logs",
        "Runtime\Temp", 
        "Runtime\Mount",
        "Runtime\Export"
    )
    
    foreach ($dir in $directories) {
        $fullPath = Join-Path $PSScriptRoot $dir
        if (-not (Test-Path $fullPath)) {
            try {
                New-Item -Path $fullPath -ItemType Directory -Force | Out-Null
            } catch {
                throw "Failed to create directory '$fullPath': $($_.Exception.Message)"
            }
        }
    }
}

# Main execution
try {
    # Display startup banner
    Write-Host @"

+===============================================================+
|                    KASSIA v$script:ScriptVersion         		+
|              Windows Image Preparation System                	+
|                                                              	+
|  Starting: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')         	+
+===============================================================+

"@ -ForegroundColor Cyan

    # Validate prerequisites
    Write-Host "[INIT] Checking prerequisites..." -ForegroundColor DarkYellow
    $prerequisiteIssues = Test-Prerequisites
    if ($prerequisiteIssues.Count -gt 0) {
        Write-Host "[FATAL] Prerequisites not met:" -ForegroundColor Red
        foreach ($issue in $prerequisiteIssues) {
            Write-Host "  - $issue" -ForegroundColor Red
        }
        throw "Prerequisites validation failed"
    }
    
    # Initialize directories
    Write-Host "[INIT] Creating required directories..." -ForegroundColor DarkYellow
    Initialize-Directories
    
    # Verify engine script exists
    $engineScript = Join-Path $PSScriptRoot "Engine\kassia.ps1"
    if (-not (Test-Path $engineScript)) {
        throw "Engine script not found: $engineScript"
    }
    
    # Load logging module
    $loggingModule = Join-Path $PSScriptRoot "Engine\Logging.psm1"
    if (-not (Test-Path $loggingModule)) {
        throw "Logging module not found: $loggingModule"
    }
    Import-Module $loggingModule -Force
    
    # Enable debug mode if requested
    if ($EnableDebug) {
        $global:EnableDebugLogging = $true
        Write-Log -Message "Debug mode enabled" -Level "DEBUG"
    }
    
    # Start main logging
    Write-Log -Message "Kassia v$script:ScriptVersion starting..." -Level "INIT"
    Write-Log -Message "Device: $(if ($Device) { $Device } else { 'Interactive Selection' }), OsId: $OsId" -Level "INFO"
    
    # Validate parameters
    Write-Log -Message "Validating parameters..." -Level "INFO"
    Test-Parameters
    Write-Log -Message "Parameter validation completed" -Level "OK"
    
    # Validation-only mode
    if ($Validate) {
        Write-Log -Message "Validation mode - configuration check completed successfully" -Level "OK"
        $duration = (Get-Date) - $script:StartTime
        Write-Host @"

============================================================
VALIDATION COMPLETED SUCCESSFULLY
Duration: $($duration.ToString('hh\:mm\:ss'))
Device: $(if ($Device) { $Device } else { 'Interactive Selection' })
OS ID: $OsId
============================================================
"@ -ForegroundColor Green
        exit 0
    }
    
    # Execute engine script
    Write-Log -Message "Starting Kassia image preparation..." -Level "INIT"
    
    & $engineScript -Device $Device -OsId $OsId
    
    if ($LASTEXITCODE -ne 0) {
        throw "Engine script exited with code $LASTEXITCODE"
    }
    
    # Success summary
    $duration = (Get-Date) - $script:StartTime
    Write-Log -Message "Kassia execution completed successfully" -Level "OK"
    Write-Host @"

============================================================
KASSIA EXECUTION COMPLETED SUCCESSFULLY
Duration: $($duration.ToString('hh\:mm\:ss'))
Device: $(if ($Device) { $Device } else { 'Interactive Selection' })
OS ID: $OsId
============================================================
"@ -ForegroundColor Green

} catch {
    # Error handling
    $duration = (Get-Date) - $script:StartTime
    $errorMessage = $_.Exception.Message
    
    if (Get-Command Write-Log -ErrorAction SilentlyContinue) {
        Write-Log -Message "Fatal error: $errorMessage" -Level "ERROR"
        if ($EnableDebug) {
            Write-Log -Message "Stack trace: $($_.ScriptStackTrace)" -Level "DEBUG"
        }
    } else {
        Write-Host "[ERROR] $errorMessage" -ForegroundColor Red
    }
    
    Write-Host @"

============================================================
KASSIA EXECUTION FAILED
Duration: $($duration.ToString('hh\:mm\:ss'))
Error: $errorMessage
============================================================
"@ -ForegroundColor Red
    
    exit 1
}