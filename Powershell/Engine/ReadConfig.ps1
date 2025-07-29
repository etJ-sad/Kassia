<#
.SYNOPSIS
    Loads and merges device profile and build configuration for Kassia image preparation.

.DESCRIPTION
    This script loads device-specific profiles and global build configurations, validates compatibility,
    resolves path placeholders, and returns a merged configuration object for use by the Kassia engine.
    
    Enhanced with comprehensive validation, caching, and better error handling.

.PARAMETER DeviceProfileFile
    The device profile JSON filename (with .json extension) located in DeviceConfig directory.

.PARAMETER OsId  
    The operating system ID to validate against device profile and map to WIM file.

.PARAMETER ConfigCachePath
    Optional path for configuration caching. Defaults to Runtime\Cache.

.PARAMETER SkipValidation
    Skip extended validation checks (for debugging or special cases).

.EXAMPLE
    $config = .\ReadConfig.ps1 -DeviceProfileFile "RW-528A.json" -OsId 10
    
    Loads configuration for device RW-528A with OS ID 10.

.EXAMPLE
    $config = .\ReadConfig.ps1 -DeviceProfileFile "test-device.json" -OsId 21656 -SkipValidation
    
    Loads configuration with validation checks disabled.

.NOTES
    Author   : Alexander Soloninov
    Version  : 1.1.0
    Module   : Kassia Build Engine
    Requires : Logging.psm1, PowerShell 5.1+
    Tags     : Configuration, Validation, Path Resolution, Caching

#>

param (
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$DeviceProfileFile,
    
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, [int]::MaxValue)]
    [int]$OsId,
    
    [string]$ConfigCachePath,
    
    [switch]$SkipValidation
)

# Configuration validation schema patterns
$script:DeviceProfileSchema = @{
    RequiredProperties = @('deviceId', 'supportedOS', 'driverFamilyIds')
    OptionalProperties = @('description', 'manufacturer', 'model', 'notes')
    PropertyTypes = @{
        'deviceId' = 'string'
        'supportedOS' = 'array'
        'driverFamilyIds' = 'array'
    }
}

$script:BuildConfigSchema = @{
    RequiredProperties = @('name', 'mountPoint', 'exportPath', 'tempPath', 'driverRoot', 'updateRoot', 'yunonaPath', 'osWimMap')
    OptionalProperties = @('version', 'description')
    PropertyTypes = @{
        'osWimMap' = 'object'
    }
}

#region Helper Functions

function Test-GlobalDependencies {
    <#
    .SYNOPSIS
        Validates global dependencies and environment setup
    #>
    
    if (-not $global:rootPath) {
        throw "Global rootPath is not defined. Please import Logging.psm1 first."
    }
    
    if (-not (Get-Command Write-Log -ErrorAction SilentlyContinue)) {
        throw "Write-Log function not available. Please import Logging.psm1 first."
    }
    
    Write-Log -Message "Global dependencies validated" -Level "DEBUG"
}

function Test-ConfigurationSchema {
    <#
    .SYNOPSIS
        Validates configuration object against expected schema
    #>
    param(
        [object]$Config,
        [hashtable]$Schema,
        [string]$ConfigType
    )
    
    if ($SkipValidation) {
        Write-Log -Message "Skipping $ConfigType schema validation" -Level "DEBUG"
        return
    }
    
    $errors = @()
    
    # Check required properties
    foreach ($requiredProp in $Schema.RequiredProperties) {
        if (-not $Config.PSObject.Properties.Name -contains $requiredProp) {
            $errors += "Missing required property: $requiredProp"
        }
    }
    
    # Check property types where specified
    foreach ($propType in $Schema.PropertyTypes.GetEnumerator()) {
        $propName = $propType.Key
        $expectedType = $propType.Value
        
        if ($Config.PSObject.Properties.Name -contains $propName) {
            $actualValue = $Config.$propName
            
            switch ($expectedType) {
                'string' {
                    if ($actualValue -isnot [string]) {
                        $errors += "Property '$propName' should be a string, found: $($actualValue.GetType().Name)"
                    }
                }
                'array' {
                    if ($actualValue -isnot [array] -and $actualValue -isnot [System.Object[]]) {
                        $errors += "Property '$propName' should be an array, found: $($actualValue.GetType().Name)"
                    }
                }
                'object' {
                    if ($actualValue -isnot [PSCustomObject]) {
                        $errors += "Property '$propName' should be an object, found: $($actualValue.GetType().Name)"
                    }
                }
            }
        }
    }
    
    if ($errors.Count -gt 0) {
        $errorMessage = "$ConfigType validation failed:`n" + ($errors -join "`n")
        throw $errorMessage
    }
    
    Write-Log -Message "$ConfigType schema validation passed" -Level "DEBUG"
}

function Get-ConfigurationHash {
    <#
    .SYNOPSIS
        Generates a hash for configuration caching
    #>
    param(
        [string]$DeviceFile,
        [int]$OsId,
        [string]$BuildConfigPath
    )
    
    try {
        $deviceModified = (Get-Item $DeviceFile).LastWriteTime.Ticks
        $buildModified = (Get-Item $BuildConfigPath).LastWriteTime.Ticks
        $hashInput = "$DeviceFile|$OsId|$deviceModified|$buildModified"
        
        # Simple hash generation
        $md5 = [System.Security.Cryptography.MD5]::Create()
        $hash = [System.BitConverter]::ToString($md5.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($hashInput)))
        $md5.Dispose()
        
        return $hash -replace '-', ''
    } catch {
        Write-Log -Message "Could not generate configuration hash: $($_.Exception.Message)" -Level "DEBUG"
        return $null
    }
}

function Get-CachedConfiguration {
    <#
    .SYNOPSIS
        Retrieves cached configuration if available and valid
    #>
    param(
        [string]$CacheKey,
        [string]$CachePath
    )
    
    if (-not $CachePath -or -not $CacheKey) {
        return $null
    }
    
    $cacheFile = Join-Path $CachePath "$CacheKey.json"
    
    if (-not (Test-Path $cacheFile)) {
        return $null
    }
    
    try {
        $cachedConfig = Get-Content $cacheFile -Raw | ConvertFrom-Json
        Write-Log -Message "Configuration loaded from cache: $cacheFile" -Level "DEBUG"
        return $cachedConfig
    } catch {
        Write-Log -Message "Failed to load cached configuration: $($_.Exception.Message)" -Level "WARNING"
        # Remove invalid cache file
        Remove-Item $cacheFile -Force -ErrorAction SilentlyContinue
        return $null
    }
}

function Set-CachedConfiguration {
    <#
    .SYNOPSIS
        Saves configuration to cache
    #>
    param(
        [object]$Config,
        [string]$CacheKey,
        [string]$CachePath
    )
    
    if (-not $CachePath -or -not $CacheKey -or -not $Config) {
        return
    }
    
    try {
        if (-not (Test-Path $CachePath)) {
            New-Item -Path $CachePath -ItemType Directory -Force | Out-Null
        }
        
        $cacheFile = Join-Path $CachePath "$CacheKey.json"
        $Config | ConvertTo-Json -Depth 10 | Set-Content $cacheFile -Force
        
        Write-Log -Message "Configuration cached: $cacheFile" -Level "DEBUG"
    } catch {
        Write-Log -Message "Failed to cache configuration: $($_.Exception.Message)" -Level "WARNING"
    }
}

function Resolve-PathPlaceholders {
    <#
    .SYNOPSIS
        Resolves ${root} placeholders and normalizes paths in configuration objects
    #>
    param (
        [object]$Config,
        [string]$RootPath
    )

    if (-not $Config) {
        throw "Configuration object cannot be null"
    }
    
    if (-not $RootPath) {
        throw "Root path cannot be null or empty"
    }
    
    Write-Log -Message "Resolving path placeholders with root: $RootPath" -Level "DEBUG"
    
    # Create a deep copy to avoid modifying the original
    $resolvedConfig = $Config | ConvertTo-Json -Depth 10 | ConvertFrom-Json
    
    $processedPaths = 0
    
    foreach ($prop in $resolvedConfig.PSObject.Properties) {
        if ($prop.Value -is [string] -and $prop.Value -like '*${root}*') {
            $originalValue = $prop.Value
            $resolvedValue = $originalValue -replace '\$\{root\}', $RootPath
            
            # Normalize path separators for Windows
            $resolvedValue = $resolvedValue -replace '/', '\'
            
            # Resolve to full path if it looks like a path
            if ($resolvedValue -match '^[A-Za-z]:\\|^\\\\') {
                try {
                    if (Test-Path $resolvedValue) {
                        $resolvedValue = (Resolve-Path $resolvedValue).Path
                    } else {
                        $resolvedValue = [System.IO.Path]::GetFullPath($resolvedValue)
                    }
                } catch {
                    Write-Log -Message "Could not resolve path '$resolvedValue': $($_.Exception.Message)" -Level "WARNING"
                }
            }
            
            $prop.Value = $resolvedValue
            $processedPaths++
            
            Write-Log -Message "Resolved path: $originalValue → $resolvedValue" -Level "DEBUG"
        }
    }
    
    Write-Log -Message "Resolved $processedPaths path placeholders" -Level "DEBUG"
    return $resolvedConfig
}

function Get-DeviceProfile {
    <#
    .SYNOPSIS
        Loads and validates device profile configuration
    #>
    param([string]$DeviceFile)
    
    $deviceProfilePath = Join-Path "$global:rootPath\DeviceConfig" $DeviceFile
    Write-Log -Message "Loading device profile: $deviceProfilePath" -Level "DEBUG"
    
    if (-not (Test-Path $deviceProfilePath)) {
        throw "Device configuration not found: $deviceProfilePath"
    }
    
    try {
        $deviceProfile = Get-Content $deviceProfilePath -Raw | ConvertFrom-Json
        
        # Validate schema
        Test-ConfigurationSchema -Config $deviceProfile -Schema $script:DeviceProfileSchema -ConfigType "Device Profile"
        
        Write-Log -Message "Device profile loaded successfully: $($deviceProfile.deviceId)" -Level "OK"
        return $deviceProfile
        
    } catch {
        throw "Failed to load device profile '$DeviceFile': $($_.Exception.Message)"
    }
}

function Get-BuildConfiguration {
    <#
    .SYNOPSIS
        Loads and validates build configuration
    #>
    
    $kassiaConfigPath = Join-Path $PSScriptRoot "config.json"
    Write-Log -Message "Loading build configuration: $kassiaConfigPath" -Level "DEBUG"
    
    if (-not (Test-Path $kassiaConfigPath)) {
        throw "Build configuration not found: $kassiaConfigPath"
    }
    
    try {
        $buildConfig = Get-Content $kassiaConfigPath -Raw | ConvertFrom-Json
        
        # Validate schema
        Test-ConfigurationSchema -Config $buildConfig -Schema $script:BuildConfigSchema -ConfigType "Build Configuration"
        
        Write-Log -Message "Build configuration loaded successfully" -Level "OK"
        return $buildConfig
        
    } catch {
        throw "Failed to load build configuration: $($_.Exception.Message)"
    }
}

function New-EnhancedBuildConfig {
    <#
    .SYNOPSIS
        Creates enhanced build configuration with OS-specific settings
    #>
    param(
        [object]$BuildConfigRaw,
        [int]$OsId
    )
    
    # Extract OS WIM mapping
    $osWimMap = @{}
    if ($BuildConfigRaw.osWimMap) {
        foreach ($key in $BuildConfigRaw.osWimMap.PSObject.Properties.Name) {
            $osWimMap[$key] = $BuildConfigRaw.osWimMap.$key
        }
    }
    
    # Validate OS ID mapping
    if (-not $osWimMap.ContainsKey("$OsId")) {
        $availableIds = $osWimMap.Keys -join ', '
        throw "No WIM mapping found for OS ID $OsId. Available IDs: $availableIds"
    }
    
    # Create mutable configuration object
    $buildConfig = [PSCustomObject]@{}
    foreach ($prop in $BuildConfigRaw.PSObject.Properties) {
        $buildConfig | Add-Member -MemberType NoteProperty -Name $prop.Name -Value $prop.Value
    }
    
    # Add OS-specific properties
    $sourceWim = $osWimMap["$OsId"]
    $buildConfig | Add-Member -MemberType NoteProperty -Name "sourceWim" -Value $sourceWim -Force
    $buildConfig | Add-Member -MemberType NoteProperty -Name "selectedOSId" -Value $OsId -Force
    
    Write-Log -Message "Using WIM for OS ID $OsId → $sourceWim" -Level "DEBUG"
    
    return $buildConfig
}

function Test-OSCompatibility {
    <#
    .SYNOPSIS
        Validates OS ID compatibility with device profile
    #>
    param(
        [object]$DeviceProfile,
        [int]$OsId
    )
    
    if ($SkipValidation) {
        Write-Log -Message "Skipping OS compatibility validation" -Level "DEBUG"
        return
    }
    
    if (-not $DeviceProfile.supportedOS) {
        Write-Log -Message "Device profile missing supportedOS array - assuming compatible" -Level "WARNING"
        return
    }
    
    if ($OsId -notin $DeviceProfile.supportedOS) {
        $supportedIds = $DeviceProfile.supportedOS -join ', '
        throw "OS ID $OsId not supported by device profile '$($DeviceProfile.deviceId)'. Supported IDs: $supportedIds"
    }
    
    Write-Log -Message "OS ID $OsId is compatible with device profile" -Level "OK"
}

#endregion

#region Main Execution

try {
    Write-Log -Message "ReadConfig v1.1.0 starting..." -Level "DEBUG"
    Write-Log -Message "Device: $DeviceProfileFile, OS ID: $OsId" -Level "DEBUG"
    
    # Validate dependencies
    Test-GlobalDependencies
    
    # Setup caching
    if (-not $ConfigCachePath) {
        $ConfigCachePath = Join-Path $global:rootPath "Runtime\Cache"
    }
    
    # Generate cache key
    $deviceProfilePath = Join-Path "$global:rootPath\DeviceConfig" $DeviceProfileFile
    $buildConfigPath = Join-Path $PSScriptRoot "config.json"
    $cacheKey = Get-ConfigurationHash -DeviceFile $deviceProfilePath -OsId $OsId -BuildConfigPath $buildConfigPath
    
    # Try to load from cache first
    if ($cacheKey) {
        $cachedConfig = Get-CachedConfiguration -CacheKey $cacheKey -CachePath $ConfigCachePath
        if ($cachedConfig) {
            Write-Log -Message "Configuration loaded from cache" -Level "OK"
            return $cachedConfig
        }
    }
    
    # Load configurations
    Write-Log -Message "Loading fresh configuration..." -Level "INFO"
    
    $deviceProfile = Get-DeviceProfile -DeviceFile $DeviceProfileFile
    $buildConfigRaw = Get-BuildConfiguration
    
    # Validate OS compatibility
    Test-OSCompatibility -DeviceProfile $deviceProfile -OsId $OsId
    
    # Create enhanced build configuration
    $buildConfig = New-EnhancedBuildConfig -BuildConfigRaw $buildConfigRaw -OsId $OsId
    
    # Resolve path placeholders
    $resolvedBuildConfig = Resolve-PathPlaceholders -Config $buildConfig -RootPath $global:rootPath
    
    # Create final configuration object
    $finalConfig = [PSCustomObject]@{
        DeviceProfile = $deviceProfile
        BuildConfig = $resolvedBuildConfig
        Metadata = @{
            LoadedAt = Get-Date
            DeviceFile = $DeviceProfileFile
            OsId = $OsId
            Version = "1.1.0"
        }
    }
    
    # Cache the configuration
    if ($cacheKey) {
        Set-CachedConfiguration -Config $finalConfig -CacheKey $cacheKey -CachePath $ConfigCachePath
    }
    
    Write-Log -Message "Configuration loading completed successfully" -Level "OK"
    Write-Log -Message "Device: $($deviceProfile.deviceId), Source WIM: $($resolvedBuildConfig.sourceWim)" -Level "INFO"
    
    return $finalConfig
    
} catch {
    Write-Log -Message "Configuration loading failed: $($_.Exception.Message)" -Level "ERROR"
    throw
}

#endregion