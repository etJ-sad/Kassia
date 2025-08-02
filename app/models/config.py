# app/models/config.py - Verbesserte Pfad-Validierung

"""
Kassia Configuration Models - Type-safe configuration handling
"""

from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, validator, model_validator
from datetime import datetime
import os


class AssetProviderType(str, Enum):
    """Asset provider types."""
    LOCAL = "local"
    SHAREPOINT = "sharepoint"
    HYBRID = "hybrid"


class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class OSSupport(BaseModel):
    """Operating system support configuration."""
    osId: int = Field(..., description="Operating system ID")
    driverFamilyIds: List[int] = Field(default_factory=list, description="Required driver family IDs")
    customScript: Optional[str] = Field(None, description="Custom post-deployment script")
    
    @validator('osId')
    def validate_os_id(cls, v):
        if v <= 0:
            raise ValueError('OS ID must be positive')
        return v


class DeviceConfig(BaseModel):
    """Device configuration model."""
    deviceId: str = Field(..., description="Device identifier")
    supportedDeviceIds: List[int] = Field(default_factory=list, description="Supported device IDs")
    osSupport: List[OSSupport] = Field(default_factory=list, description="Operating system support")
    description: Optional[str] = Field(None, description="Device description")
    manufacturer: Optional[str] = Field(None, description="Device manufacturer")
    model: Optional[str] = Field(None, description="Device model")
    
    @validator('deviceId')
    def validate_device_id(cls, v):
        if not v or not v.strip():
            raise ValueError('Device ID cannot be empty')
        return v.strip()
    
    def get_supported_os_ids(self) -> List[int]:
        """Get list of supported OS IDs."""
        return [os.osId for os in self.osSupport]
    
    def get_driver_families_for_os(self, os_id: int) -> List[int]:
        """Get driver family IDs for specific OS."""
        for os_support in self.osSupport:
            if os_support.osId == os_id:
                return os_support.driverFamilyIds
        return []
    
    def supports_os(self, os_id: int) -> bool:
        """Check if device supports specific OS."""
        return os_id in self.get_supported_os_ids()


class WindowsTools(BaseModel):
    """Windows-specific tool paths."""
    dismPath: str = Field(default="C:\\Windows\\System32\\dism.exe", description="DISM executable path")
    powershellPath: str = Field(
        default="C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe", 
        description="PowerShell executable path"
    )
    
    @validator('dismPath', 'powershellPath')
    def validate_tool_path(cls, v):
        if not v:
            raise ValueError('Tool path cannot be empty')
        # Convert to Path object for validation
        path = Path(v)
        return str(path)


class AssetProviderConfig(BaseModel):
    """Asset provider configuration."""
    type: AssetProviderType = Field(..., description="Asset provider type")
    config: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration")


class LocalAssetConfig(BaseModel):
    """Local asset provider configuration."""
    assetsPath: str = Field(default=".\\assets", description="Local assets directory path")
    
    @validator('assetsPath')
    def validate_assets_path(cls, v):
        return str(Path(v))


class SharePointAssetConfig(BaseModel):
    """SharePoint asset provider configuration."""
    siteUrl: str = Field(..., description="SharePoint site URL")
    clientId: str = Field(..., description="Azure AD client ID")
    clientSecret: str = Field(..., description="Azure AD client secret")
    cachePath: str = Field(default=".\\cache", description="Local cache directory")
    cacheTTL: int = Field(default=3600, description="Cache TTL in seconds")
    
    @validator('siteUrl')
    def validate_site_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Site URL must start with http:// or https://')
        return v
    
    @validator('cacheTTL')
    def validate_cache_ttl(cls, v):
        if v < 0:
            raise ValueError('Cache TTL must be non-negative')
        return v


class BuildConfig(BaseModel):
    """Main build configuration."""
    name: str = Field(default="Kassia Python", description="Configuration name")
    version: str = Field(default="2.0.0", description="Configuration version")
    
    # Directory paths
    mountPoint: str = Field(default=".\\runtime\\mount", description="WIM mount point")
    tempPath: str = Field(default=".\\runtime\\temp", description="Temporary files directory") 
    exportPath: str = Field(default=".\\runtime\\export", description="Export directory")
    driverRoot: str = Field(default=".\\assets\\drivers", description="Drivers directory")
    updateRoot: str = Field(default=".\\assets\\updates", description="Updates directory")
    yunonaPath: str = Field(default=".\\assets\\yunona", description="Yunona scripts directory")
    sbiRoot: str = Field(default=".\\assets\\sbi", description="System Base Images directory")
    
    # OS to WIM mapping
    osWimMap: Dict[str, str] = Field(default_factory=dict, description="OS ID to WIM file mapping")
    
    # Asset provider
    assetProvider: Optional[AssetProviderConfig] = Field(None, description="Asset provider configuration")
    
    # Windows tools
    windowsTools: Optional[WindowsTools] = Field(default_factory=WindowsTools, description="Windows tool paths")
    
    @validator('mountPoint', 'tempPath', 'exportPath', 'driverRoot', 'updateRoot', 'yunonaPath', 'sbiRoot')
    def validate_directory_paths(cls, v):
        # Normalisiere Pfad aber validiere nicht die Existenz
        return str(Path(v).resolve())
    
    @validator('osWimMap')
    def validate_os_wim_map(cls, v):
        if not v:
            raise ValueError('OS WIM mapping cannot be empty')
        
        # Validate that all paths are strings and normalize them
        normalized_map = {}
        for os_id, wim_path in v.items():
            if not isinstance(wim_path, str):
                raise ValueError(f'WIM path for OS {os_id} must be a string')
            
            # Normalisiere den Pfad (unterstützt sowohl relative als auch absolute Pfade)
            try:
                normalized_path = str(Path(wim_path).resolve())
                normalized_map[os_id] = normalized_path
            except Exception as e:
                raise ValueError(f'Invalid WIM path for OS {os_id}: {wim_path} - {e}')
        
        return normalized_map
    
    def get_wim_path(self, os_id: int) -> Optional[Path]:
        """Get WIM path for specific OS ID as Path object."""
        wim_path_str = self.osWimMap.get(str(os_id))
        if wim_path_str:
            return Path(wim_path_str)
        return None
    
    def get_supported_os_ids(self) -> List[int]:
        """Get list of supported OS IDs."""
        return [int(os_id) for os_id in self.osWimMap.keys()]
    
    def validate_wim_files_exist(self) -> Dict[str, bool]:
        """Validate that WIM files actually exist."""
        results = {}
        for os_id, wim_path_str in self.osWimMap.items():
            wim_path = Path(wim_path_str)
            results[os_id] = wim_path.exists() and wim_path.is_file()
        return results


class RuntimeState(BaseModel):
    """Runtime state tracking."""
    currentStep: str = Field(default="INIT", description="Current execution step")
    stepNumber: int = Field(default=0, description="Current step number")
    totalSteps: int = Field(default=9, description="Total number of steps")
    startTime: datetime = Field(default_factory=datetime.now, description="Execution start time")
    isMounted: bool = Field(default=False, description="WIM mount status")
    tempFiles: List[str] = Field(default_factory=list, description="Temporary files for cleanup")
    
    def get_progress_percentage(self) -> float:
        """Get progress as percentage."""
        if self.totalSteps <= 0:
            return 0.0
        return (self.stepNumber / self.totalSteps) * 100
    
    def get_duration(self) -> str:
        """Get execution duration as string."""
        duration = datetime.now() - self.startTime
        return str(duration)


class ValidationResult(BaseModel):
    """Configuration validation result."""
    isValid: bool = Field(..., description="Overall validation status")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    
    def add_error(self, error: str) -> None:
        """Add validation error."""
        self.errors.append(error)
        self.isValid = False
    
    def add_warning(self, warning: str) -> None:
        """Add validation warning."""
        self.warnings.append(warning)
    
    def has_errors(self) -> bool:
        """Check if there are validation errors."""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if there are validation warnings."""
        return len(self.warnings) > 0


class KassiaConfig(BaseModel):
    """Complete Kassia configuration combining all components."""
    device: DeviceConfig = Field(..., description="Device configuration")
    build: BuildConfig = Field(..., description="Build configuration")
    runtime: RuntimeState = Field(default_factory=RuntimeState, description="Runtime state")
    
    # Selected OS for this run
    selectedOsId: Optional[int] = Field(None, description="Selected OS ID for this execution")
    
    @model_validator(mode='after')
    def validate_os_compatibility(self):
        """Validate that selected OS is supported by device."""
        if self.device and self.selectedOsId:
            if not self.device.supports_os(self.selectedOsId):
                supported = self.device.get_supported_os_ids()
                raise ValueError(
                    f'OS ID {self.selectedOsId} not supported by device {self.device.deviceId}. '
                    f'Supported: {supported}'
                )
        
        return self
    
    def get_driver_families(self) -> List[int]:
        """Get driver family IDs for selected OS."""
        if not self.selectedOsId:
            return []
        return self.device.get_driver_families_for_os(self.selectedOsId)
    
    def get_wim_path(self) -> Optional[Path]:
        """Get WIM path for selected OS."""
        if not self.selectedOsId:
            return None
        return self.build.get_wim_path(self.selectedOsId)
    
    def validate_configuration(self) -> ValidationResult:
        """Validate complete configuration."""
        result = ValidationResult(isValid=True)
        
        # Check WIM file existence
        wim_validation = self.build.validate_wim_files_exist()
        for os_id, exists in wim_validation.items():
            if not exists:
                wim_path = self.build.osWimMap[os_id]
                result.add_warning(f"WIM file not found for OS {os_id}: {wim_path}")
        
        # Check selected OS WIM if specified
        if self.selectedOsId:
            wim_path = self.get_wim_path()
            if wim_path and not wim_path.exists():
                result.add_error(f"Selected OS WIM file not found: {wim_path}")
        
        return result


# Configuration loading utilities
class ConfigLoader:
    """Configuration loader with validation."""
    
    @staticmethod
    def load_device_config(device_name: str, config_dir: str = "config/device_configs") -> DeviceConfig:
        """Load and validate device configuration."""
        config_path = Path(config_dir) / f"{device_name}.json"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Device configuration not found: {config_path}")
        
        try:
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return DeviceConfig(**data)
        except Exception as e:
            raise ValueError(f"Failed to load device config {device_name}: {e}")
    
    @staticmethod
    def load_build_config(config_path: str = "config/config.json") -> BuildConfig:
        """Load and validate build configuration."""
        config_file = Path(config_path)
        
        if not config_file.exists():
            raise FileNotFoundError(f"Build configuration not found: {config_path}")
        
        try:
            import json
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return BuildConfig(**data)
        except Exception as e:
            raise ValueError(f"Failed to load build config: {e}")
    
    @staticmethod
    def create_kassia_config(device_name: str, os_id: int) -> KassiaConfig:
        """Create complete Kassia configuration."""
        device_config = ConfigLoader.load_device_config(device_name)
        build_config = ConfigLoader.load_build_config()
        
        kassia_config = KassiaConfig(
            device=device_config,
            build=build_config,
            selectedOsId=os_id
        )
        
        # Validate configuration
        validation_result = kassia_config.validate_configuration()
        if validation_result.has_errors():
            error_msg = "Configuration validation failed:\n" + "\n".join(validation_result.errors)
            raise ValueError(error_msg)
        
        return kassia_config