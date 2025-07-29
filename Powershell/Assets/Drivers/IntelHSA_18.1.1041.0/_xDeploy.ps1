# Change to the directory where the script is located
Set-Location -Path (Split-Path -Path $MyInvocation.MyCommand.Definition -Parent)

# Directory where the packages are stored
$PackageDir = Get-Location

# Initialize variables
$PackagePath = $null
$LicensePath = $null
$DependencyPaths = @()

# Find the main package (.appxbundle or .appx)
$PackagePath = Get-ChildItem -Path $PackageDir -Filter *.appxbundle -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $PackagePath) {
    $PackagePath = Get-ChildItem -Path $PackageDir -Filter *.appx -ErrorAction SilentlyContinue | Select-Object -First 1
}

if (-not $PackagePath) {
    $PackagePath = Get-ChildItem -Path $PackageDir -Filter *.msixbundle -ErrorAction SilentlyContinue | Select-Object -First 1
}

# Find dependencies (if present) and add to array
$DependencyPaths += (Get-ChildItem -Path $PackageDir -Filter 'Microsoft.NET.Native.Framework*.appx' -ErrorAction SilentlyContinue)
$DependencyPaths += (Get-ChildItem -Path $PackageDir -Filter 'Microsoft.NET.Native.Runtime*.appx' -ErrorAction SilentlyContinue)
$DependencyPaths += (Get-ChildItem -Path $PackageDir -Filter 'Microsoft.VCLibs.140.00*.appx' -ErrorAction SilentlyContinue)

# Find license file
$LicensePath = Get-ChildItem -Path $PackageDir -Filter '*_License1.xml' | Select-Object -First 1

# Check if the main package is found
if (-not $PackagePath) {
    Write-Host "Main package (*.appxbundle or *.appx) not found!" -ForegroundColor Red
    exit 1
}

# Construct the DISM command
$DISMCommand = "DISM /Online /Add-ProvisionedAppxPackage /PackagePath:`"$($PackagePath.FullName)`""

# Add dependency packages if they exist
foreach ($Dependency in $DependencyPaths) {
    $DISMCommand += " /DependencyPackagePath:`"$($Dependency.FullName)`""
}

# Add the license file if it exists
if ($LicensePath) {
    $DISMCommand += " /LicensePath:`"$($LicensePath.FullName)`""
}

$DISMCommand += " /Region:all"

# Display and execute the DISM command
Write-Host "Executing command: $DISMCommand"
Invoke-Expression $DISMCommand
