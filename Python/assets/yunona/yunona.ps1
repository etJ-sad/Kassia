# Define Log File
$scriptName = $MyInvocation.MyCommand.Name
$logFile = "C:\Windows\Temp\initializationComplete.log"

# Ensure Temp Directory Exists
if (!(Test-Path "C:\Windows\Temp")) {
    New-Item -ItemType Directory -Path "C:\Windows\Temp" | Out-Null
}

# Function to Write Logs
Function Write-Log {
    param (
        [string]$message
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp $message" | Out-File -Append -FilePath $logFile
}

Write-Log "[INFO] Script '$scriptName' started."

# Execute custom script if exists
$customScript = "C:\Users\Public\customActionInRuntime.cmd"
if (Test-Path $customScript) {
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c $customScript" -NoNewWindow -Wait
    Write-Log "[INFO] Executed customActionInRuntime.cmd"
}

# Remove registry key from Run
$regPath = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run"
$regEntry = Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue | Where-Object { $_.PSObject.Properties.Name -match "Unattend" }
if ($regEntry) {
    $keyName = $regEntry.PSObject.Properties.Name
    Remove-ItemProperty -Path $regPath -Name $keyName -Force -ErrorAction SilentlyContinue
    Write-Log "[INFO] Removed registry entry: $keyName"
}

# Process ToRun folder
$toRunPath = "C:\ToRun"
if (Test-Path $toRunPath) {
    Get-ChildItem -Path "$toRunPath\*.reg" -Recurse | ForEach-Object {
        Start-Process -FilePath "regedit.exe" -ArgumentList "/s `"$_`"" -NoNewWindow -Wait
        Write-Log "[APPLYING] Imported registry file: $_"
    }
    Get-ChildItem -Path "$toRunPath\*.cmd" -Recurse | ForEach-Object {
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c $_" -NoNewWindow -Wait
        Write-Log "[APPLYING] Executed batch script: $_"
    }
	powershell -ep Bypass Start-Process -FilePath C:\Windows\Panther\Siemens\Config\SIMATIC.theme
	REG ADD "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Policies\System" /v WallpaperStyle /t REG_SZ /d 4 /f
	
    Remove-Item -Path $toRunPath -Recurse -Force -ErrorAction SilentlyContinue
    Write-Log "[INFO] Deleted ToRun directory."
	Write-Log "[APPLYING] Executed batch script: $_"
}

#SIMATIC THEME
$themeName = "SIMATIC"
$themeFile = "$env:LocalAppData\Microsoft\Windows\Themes\SIMATIC.theme"
$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\SavedThemes\$themeName"

Write-Log  "[INFO] Creating registry key: $regPath"

New-Item -Path $regPath -Force | Out-Null
Set-ItemProperty -Path $regPath -Name "(default)" -Value $themeName
Set-ItemProperty -Path $regPath -Name "DisplayName" -Value $themeName
Set-ItemProperty -Path $regPath -Name "ThemeFile" -Value $themeFile

Write-Log  "[SUCCESS] Theme '$themeName' registered under SavedThemes!"

# Install Visual C++ Redistributables if available
$vcredist64 = "C:\Users\Public\vcredist_x64_2010.exe"
$vcredist86 = "C:\Users\Public\vcredist_x86_2010.exe"
if (Test-Path $vcredist64) {
    Start-Process -FilePath $vcredist64 -ArgumentList "/q /r" -NoNewWindow -Wait
    Write-Log "[INFO] Installed vcredist_x64_2010.exe"
}
if (Test-Path $vcredist86) {
    Start-Process -FilePath $vcredist86 -ArgumentList "/q /r" -NoNewWindow -Wait
    Write-Log "[INFO] Installed vcredist_x86_2010.exe"
}

# Run Config PowerShell scripts if they exist
$ConfigPath = "C:\Windows\Panther\Siemens\Config"
$Scripts = @("SET_WALLPAPER_TO_FILL.ps1", "SET_WINDOWS_NOTEPAD_TO_DEFAULT.ps1", "SET_WINDOWS_EXPLORER_TO_DEFAULT.ps1", "PX-39A.ps1", "RESET_LOCKSCREEN_SETTINGS.ps1", "SET_PORTS_CLOSED.ps1")
foreach ($script in $Scripts) {
    $scriptPath = "$ConfigPath\$script"
    if (Test-Path $scriptPath) {
        Start-Process -FilePath "powershell.exe" -ArgumentList "-ExecutionPolicy Bypass -File $scriptPath" -NoNewWindow -Wait
        Write-Log "[INFO] Executed $script"
    }
}

# Check Windows Build Version and run additional script
$buildVersion = [System.Environment]::OSVersion.Version.Build
if ($buildVersion -eq 26100) {
    $siemensScript = "$ConfigPath\SET_SIEMENS_UI_LOOK.ps1"
    if (Test-Path $siemensScript) {
        Start-Process -FilePath "powershell.exe" -ArgumentList "-ExecutionPolicy Bypass -File $siemensScript" -NoNewWindow -Wait
        Write-Log "[INFO] Executed SET_SIEMENS_UI_LOOK.ps1"
    }
}

# Reassign UWP apps permissions
Get-AppxPackage -AllUsers | Foreach {Add-AppxPackage -DisableDevelopmentMode -Register "$($_.InstallLocation)\AppXManifest.xml"}

$jsonPath = 'C:\Version.json'

# Reading the JSON file
$jsonContent = Get-Content -Path $jsonPath | ConvertFrom-Json

# Setting a new value for 'FirstBooted'
# Get the current date and time
$currentDate = Get-Date

# Convert the date to the desired format
$formattedDate = $currentDate.ToString("yyyy-MM-ddTHH:mm:sszzz")

# Output the formatted date
Write-Host $formattedDate
Write-Log "[INFO] formatted date: $formattedDate"

$jsonContent.FirstBooted = $formattedDate

# Converting the object back to a JSON string
$jsonString = $jsonContent | ConvertTo-Json -Depth 2

# Saving the updated JSON string to the file
Set-Content -Path $jsonPath -Value $jsonString

# Clean up folders
$cleanupPaths = @("C:\Windows\Setup\Scripts", "C:\Windows\Setup\State", "C:\Windows\Setup", "$ConfigPath")
foreach ($path in $cleanupPaths) {
    if (Test-Path $path) {
        Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
        Write-Log "[INFO] Deleted $path"
    }
}

# Delete leftover files
$filesToDelete = @(
    "C:\Users\Public\vcredist_x64_2010.exe",
    "C:\Users\Public\vcredist_x86_2010.exe",
    "C:\Users\Public\customActionInRuntime.cmd",
	"C:\Users\Public\initializationComplete.ps1"

)
foreach ($file in $filesToDelete) {
    if (Test-Path $file) {
        Remove-Item -Path $file -Force -ErrorAction SilentlyContinue
        Write-Log "[INFO] Deleted file: $file"
    }
}

#$logs = wevtutil el
#foreach ($log in $logs) {
#    Write-Log "[INFO] Clearing event log: $log"
#    try {
#        wevtutil cl "$log"
#        Write-Log "[SUCCESS] Cleared: $log"
#    } catch {}
#}

Write-Log "[INFO] Script '$scriptName' execution completed."
powershell -ep Bypass -Command "Get-Process | Where-Object { $_.MainWindowTitle -match '"Themes"' -or $_.ProcessName -eq '"SystemSettings"' } | Stop-Process -Force"

Clear-History
Remove-Item (Get-PSReadLineOption).HistorySavePath
Clear-Host