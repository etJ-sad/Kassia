# app/core/asset_providers/base.py
"""
Asset Provider Base Classes
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass


class AssetType(str, Enum):
    """Asset types."""
    DRIVER = "driver"
    UPDATE = "update"
    SBI = "sbi"  # System Base Image
    YUNONA = "yunona"


class DriverType(str, Enum):
    """Driver types."""
    INF = "inf"
    APPX = "appx"
    EXE = "exe"


class UpdateType(str, Enum):
    """Update types."""
    MSU = "msu"
    CAB = "cab"
    EXE = "exe"
    MSI = "msi"


@dataclass
class AssetInfo:
    """Asset information."""
    name: str
    path: Path
    asset_type: AssetType
    metadata: Dict[str, Any]
    size: Optional[int] = None
    
    def __post_init__(self):
        if self.size is None and self.path.exists():
            self.size = self.path.stat().st_size


@dataclass
class DriverAsset(AssetInfo):
    """Driver asset information."""
    driver_type: DriverType = DriverType.INF
    family_id: Optional[int] = None
    supported_devices: List[int] = None
    supported_os: List[int] = None
    order: int = 9999
    
    def __post_init__(self):
        super().__post_init__()
        if self.supported_devices is None:
            self.supported_devices = []
        if self.supported_os is None:
            self.supported_os = []


@dataclass
class UpdateAsset(AssetInfo):
    """Update asset information."""
    update_type: UpdateType = UpdateType.MSU
    update_version: Optional[str] = None
    supported_os: List[int] = None
    requires_reboot: bool = False
    order: int = 9999
    
    def __post_init__(self):
        super().__post_init__()
        if self.supported_os is None:
            self.supported_os = []


@dataclass
class SBIAsset(AssetInfo):
    """System Base Image asset information."""
    os_id: int = 0
    architecture: str = "x64"
    build_number: Optional[str] = None


class AssetProvider(ABC):
    """Abstract base class for asset providers."""
    
    @abstractmethod
    async def get_drivers(self, device_family: str, os_id: int) -> List[DriverAsset]:
        """Get drivers for specific device family and OS."""
        pass
    
    @abstractmethod 
    async def get_updates(self, os_id: int) -> List[UpdateAsset]:
        """Get updates for specific OS."""
        pass
    
    @abstractmethod
    async def get_sbi(self, os_id: int) -> Optional[SBIAsset]:
        """Get System Base Image for OS."""
        pass
    
    @abstractmethod
    async def get_yunona_scripts(self) -> List[AssetInfo]:
        """Get Yunona post-deployment scripts."""
        pass
    
    @abstractmethod
    async def validate_asset(self, asset: AssetInfo) -> bool:
        """Validate asset integrity."""
        pass