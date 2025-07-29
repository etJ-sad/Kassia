# Logging.psm1 - Enhanced Logging Module
<#
.SYNOPSIS
    Enhanced logging module for Kassia Build Engine with improved formatting and performance.

.DESCRIPTION
    This module provides comprehensive logging functionality including:
    - Color-coded console output with multiple log levels
    - File logging with timestamps and proper formatting
    - Performance optimizations with buffering
    - Thread-safe operations
    - Configurable log levels and formatting

.NOTES
    Author   : Alexander Soloninov
    Version  : 1.1.0
    Module   : Kassia Build Engine
    Tags     : Logging, Console, File, Performance
#>

# Module version for tracking
$script:LoggingVersion = "1.1.0"

# Global configuration variables
$global:EnableDebugLogging = $false
$global:LogBufferSize = 10
$global:UseUTF8Encoding = $true

# Determine the root directory dynamically
$global:rootPath = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

# Set the global log file path with timestamp
$global:logFile = "$global:rootPath\Logs\LOG_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

# Log buffer for performance optimization
$script:logBuffer = @()
$script:lastFlush = Get-Date

# Define console colors for each log level
$global:colorMap = @{
    "INIT"      = "DarkYellow"  # System initialization
    "INFO"      = "DarkCyan"    # General information
    "OK"        = "Green"       # Success operations
    "SUCCESS"   = "Green"       # Alternative success
    "WARNING"   = "Yellow"      # Warnings
    "WARN"      = "Yellow"      # Alternative warning
    "ERROR"     = "Red"         # Critical errors
    "EXECUTING" = "Cyan"        # Running processes
    "APPLYING"  = "Magenta"     # Applying configurations
    "DEBUG"     = "Blue"        # Debug information
}

# Define text prefixes for file logging
$global:prefixMap = @{
    "INIT"      = "[INIT]     "  
    "INFO"      = "[INFO]     "  
    "OK"        = "[OK]       "  
    "SUCCESS"   = "[SUCCESS]  "  
    "WARNING"   = "[WARNING]  "  
    "WARN"      = "[WARN]     "  
    "ERROR"     = "[ERROR]    "  
    "EXECUTING" = "[EXEC]     "  
    "APPLYING"  = "[APPLY]    "  
    "DEBUG"     = "[DEBUG]    "  
}

#region Helper Functions

function Initialize-LogFile {
    <#
    .SYNOPSIS
        Initializes the log file with proper encoding and headers
    #>
    
    $logDir = Split-Path $global:logFile -Parent
    
    # Create logs directory if it doesn't exist
    if (-not (Test-Path $logDir)) {
        try {
            New-Item -Path $logDir -ItemType Directory -Force | Out-Null
        } catch {
            Write-Warning "Failed to create log directory: $logDir"
            return $false
        }
    }
    
    # Create log file with header
    if (-not (Test-Path $global:logFile)) {
        try {
            $header = @"
================================================================================
KASSIA BUILD ENGINE LOG
================================================================================
Session Started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
PowerShell Version: $($PSVersionTable.PSVersion)
Host: $($Host.Name)
User: $($env:USERNAME)
Computer: $($env:COMPUTERNAME)
Log File: $global:logFile
================================================================================

"@
            
            if ($global:UseUTF8Encoding) {
                [System.IO.File]::WriteAllText($global:logFile, $header, [System.Text.Encoding]::UTF8)
            } else {
                Set-Content -Path $global:logFile -Value $header -Encoding ASCII
            }
            
            return $true
        } catch {
            Write-Warning "Failed to initialize log file: $($_.Exception.Message)"
            return $false
        }
    }
    
    return $true
}

function Get-SafeDivider {
    <#
    .SYNOPSIS
        Creates a safe divider line that works across different console encodings
    #>
    param(
        [int]$Width = 80,
        [char]$Character = '-'
    )
    
    try {
        # Try to get console width, fallback to default if it fails
        $consoleWidth = $Host.UI.RawUI.WindowSize.Width
        if ($consoleWidth -gt 10 -and $consoleWidth -lt 200) {
            $Width = $consoleWidth
        }
    } catch {
        # Fallback to default width if console width detection fails
        $Width = 80
    }
    
    return $Character.ToString() * $Width
}

function Format-LogMessage {
    <#
    .SYNOPSIS
        Formats a log message with proper structure and encoding safety
    #>
    param(
        [string]$Message,
        [string]$Level,
        [datetime]$Timestamp
    )
    
    # Clean the message of any problematic characters
    $cleanMessage = $Message -replace '[^\x20-\x7E\t\n\r]', '?'
    
    # Get the prefix
    $prefix = $global:prefixMap[$Level]
    if (-not $prefix) {
        $prefix = "[$Level]".PadRight(10)
    }
    
    # Format timestamp
    $timestampStr = $Timestamp.ToString("yyyy-MM-dd HH:mm:ss")
    
    # Construct the message
    $formattedMessage = "[$timestampStr] $prefix $cleanMessage"
    
    return $formattedMessage
}

function Flush-LogBuffer {
    <#
    .SYNOPSIS
        Flushes the log buffer to disk
    #>
    
    if ($script:logBuffer.Count -eq 0) {
        return
    }
    
    try {
        $content = $script:logBuffer -join "`r`n"
        
        if ($global:UseUTF8Encoding) {
            [System.IO.File]::AppendAllText($global:logFile, "$content`r`n", [System.Text.Encoding]::UTF8)
        } else {
            Add-Content -Path $global:logFile -Value $content -Encoding ASCII
        }
        
        $script:logBuffer = @()
        $script:lastFlush = Get-Date
    } catch {
        Write-Warning "Failed to flush log buffer: $($_.Exception.Message)"
    }
}

#endregion

#region Main Logging Function

function Write-Log {
    <#
    .SYNOPSIS
        Main logging function with enhanced formatting and performance
    
    .PARAMETER Message
        The message to log
        
    .PARAMETER Level
        The log level (INIT, INFO, OK, WARNING, ERROR, EXECUTING, APPLYING, DEBUG)
        
    .PARAMETER NoConsole
        Skip console output (file only)
        
    .PARAMETER NoFile
        Skip file output (console only)
        
    .PARAMETER Force
        Force immediate flush to disk
    #>
    param (
        [Parameter(Mandatory)]
        [AllowEmptyString()]
        [string]$Message,

        [string]$Level = "INFO",
        
        [switch]$NoConsole,
        
        [switch]$NoFile,
        
        [switch]$Force
    )

    # Skip DEBUG messages if not enabled
    if ($Level -eq "DEBUG" -and -not $global:EnableDebugLogging) {
        return
    }
    
    # Handle empty messages
    if ([string]::IsNullOrWhiteSpace($Message)) {
        $Message = " "  # Use a single space for empty lines
    }
    
    # Normalize level
    $Level = $Level.ToUpper()
    
    $timestamp = Get-Date
    
    # Console output
    if (-not $NoConsole) {
        try {
            $consoleMessage = Format-LogMessage -Message $Message -Level $Level -Timestamp $timestamp
            
            $color = $global:colorMap[$Level]
            if ($color) {
                Write-Host $consoleMessage -ForegroundColor $color
            } else {
                Write-Host $consoleMessage
            }
            
            # Add a simple divider for console (no special characters)
            Write-Host $(Get-SafeDivider -Width 80 -Character '-') -ForegroundColor DarkGray
            
        } catch {
            # Fallback to basic output if colored output fails
            Write-Host "[$($timestamp.ToString('HH:mm:ss'))] [$Level] $Message"
        }
    }
    
    # File output
    if (-not $NoFile) {
        # Initialize log file if needed
        if (-not (Test-Path $global:logFile)) {
            Initialize-LogFile | Out-Null
        }
        
        $fileMessage = Format-LogMessage -Message $Message -Level $Level -Timestamp $timestamp
        $script:logBuffer += $fileMessage
        
        # Auto-flush conditions
        $shouldFlush = $Force -or 
                      $script:logBuffer.Count -ge $global:LogBufferSize -or
                      ((Get-Date) - $script:lastFlush).TotalSeconds -ge 5 -or
                      $Level -in @("ERROR", "WARNING")
        
        if ($shouldFlush) {
            Flush-LogBuffer
        }
    }
}

function Write-LogSeparator {
    <#
    .SYNOPSIS
        Writes a visual separator to both console and log file
    #>
    param(
        [string]$Title = "",
        [char]$Character = '=',
        [int]$Width = 80
    )
    
    $separator = Get-SafeDivider -Width $Width -Character $Character
    
    if ($Title) {
        $titleLength = $Title.Length
        $paddingTotal = $Width - $titleLength - 2
        $paddingLeft = [math]::Floor($paddingTotal / 2)
        $paddingRight = $paddingTotal - $paddingLeft
        
        $centeredTitle = $Character.ToString() * $paddingLeft + " $Title " + $Character.ToString() * $paddingRight
        
        Write-Log -Message $centeredTitle -Level "INFO" -NoConsole
        Write-Host $centeredTitle -ForegroundColor DarkCyan
    } else {
        Write-Log -Message $separator -Level "INFO" -NoConsole  
        Write-Host $separator -ForegroundColor DarkGray
    }
}

function Write-LogBox {
    <#
    .SYNOPSIS
        Writes a boxed message for important information
    #>
    param(
        [string[]]$Messages,
        [string]$Level = "INFO"
    )
    
    $maxLength = ($Messages | Measure-Object -Property Length -Maximum).Maximum
    $width = [math]::Max($maxLength + 4, 40)
    
    $topBorder = "+" + ("-" * ($width - 2)) + "+"
    $bottomBorder = $topBorder
    
    Write-Log -Message $topBorder -Level $Level
    
    foreach ($msg in $Messages) {
        $padding = $width - $msg.Length - 4
        $paddedMessage = "| $msg" + (" " * $padding) + " |"
        Write-Log -Message $paddedMessage -Level $Level
    }
    
    Write-Log -Message $bottomBorder -Level $Level
}

#endregion

#region Module Cleanup

# Ensure buffer is flushed when module is removed
$MyInvocation.MyCommand.ScriptBlock.Module.OnRemove = {
    if ($script:logBuffer.Count -gt 0) {
        Flush-LogBuffer
    }
}

# Register for PowerShell exit to flush buffer
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    if ($script:logBuffer.Count -gt 0) {
        Flush-LogBuffer
    }
} | Out-Null

#endregion

# Export functions
Export-ModuleMember -Function Write-Log, Write-LogSeparator, Write-LogBox

# Module initialization
Write-Verbose "Kassia Logging Module v$script:LoggingVersion loaded"
if (Initialize-LogFile) {
    Write-Verbose "Log file initialized: $global:logFile"
}