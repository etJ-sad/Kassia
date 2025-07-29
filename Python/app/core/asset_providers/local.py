"""
Local Asset Provider Implementation
"""

import json
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

from .base import AssetProvider, DriverAsset, UpdateAsset, SBIAsset, AssetInfo, AssetType, DriverType, UpdateType


logger = logging.getLogger(__name__)


class LocalAssetProvider(AssetProvider):
    """Local filesystem asset provider for development and testing."""
    
    def __init__(self, assets_path: Path):
        self.assets_path = Path(assets_path)
        self.drivers_path = self.assets_path / "drivers"
        self.updates_path = self.assets_path / "updates"
        self.sbi_path = self.assets_path / "sbi"
        self.yunona_path = self.assets_path / "yunona"
        
        logger.info(f"LocalAssetProvider initialized with path: {self.assets_path}")
    
    async def get_drivers(self, device_family: str, os_id: int) -> List[DriverAsset]:
        """Get drivers for specific device family and OS."""
        drivers = []
        
        if not self.drivers_path.exists():
            logger.warning(f"Drivers path does not exist: {self.drivers_path}")
            return drivers
        
        # Search for driver configurations
        for config_file in self.drivers_path.rglob("*.json"):
            try:
                driver_asset = await self._load_driver_from_config(config_file, device_family, os_id)
                if driver_asset:
                    drivers.append(driver_asset)
            except Exception as e:
                logger.error(f"Failed to load driver config {config_file}: {e}")
        
        # Sort by order
        drivers.sort(key=lambda d: d.order)
        
        logger.info(f"Found {len(drivers)} compatible drivers for {device_family} OS {os_id}")
        return drivers
    
    async def get_updates(self, os_id: int) -> List[UpdateAsset]:
        """Get updates for specific OS."""
        updates = []
        
        if not self.updates_path.exists():
            logger.warning(f"Updates path does not exist: {self.updates_path}")
            return updates
        
        # Search for update configurations
        for config_file in self.updates_path.rglob("*.json"):
            try:
                update_asset = await self._load_update_from_config(config_file, os_id)
                if update_asset:
                    updates.append(update_asset)
            except Exception as e:
                logger.error(f"Failed to load update config {config_file}: {e}")
        
        # Sort by order
        updates.sort(key=lambda u: u.order)
        
        logger.info(f"Found {len(updates)} compatible updates for OS {os_id}")
        return updates
    
    async def get_sbi(self, os_id: int) -> Optional[SBIAsset]:
        """Get System Base Image for OS."""
        if not self.sbi_path.exists():
            logger.warning(f"SBI path does not exist: {self.sbi_path}")
            return None
        
        # Look for WIM files
        wim_patterns = [
            f"*{os_id}*.wim",
            f"w{os_id}_*.wim",
            "*.wim"
        ]
        
        for pattern in wim_patterns:
            for wim_file in self.sbi_path.glob(pattern):
                if wim_file.is_file():
                    logger.info(f"Found SBI for OS {os_id}: {wim_file}")
                    return SBIAsset(
                        name=wim_file.stem,
                        path=wim_file,
                        asset_type=AssetType.SBI,
                        metadata={"discovered_pattern": pattern},
                        os_id=os_id
                    )
        
        logger.warning(f"No SBI found for OS {os_id}")
        return None
    
    async def get_yunona_scripts(self) -> List[AssetInfo]:
        """Get Yunona post-deployment scripts."""
        scripts = []
        
        if not self.yunona_path.exists():
            logger.warning(f"Yunona path does not exist: {self.yunona_path}")
            return scripts
        
        # Find all script files
        script_patterns = ["*.py", "*.ps1", "*.cmd", "*.bat"]
        
        for pattern in script_patterns:
            for script_file in self.yunona_path.rglob(pattern):
                if script_file.is_file():
                    scripts.append(AssetInfo(
                        name=script_file.name,
                        path=script_file,
                        asset_type=AssetType.YUNONA,
                        metadata={"script_type": script_file.suffix}
                    ))
        
        logger.info(f"Found {len(scripts)} Yunona scripts")
        return scripts
    
    async def validate_asset(self, asset: AssetInfo) -> bool:
        """Validate asset integrity."""
        if not asset.path.exists():
            logger.error(f"Asset path does not exist: {asset.path}")
            return False
        
        # For drivers, validate the directory and its contents
        if asset.asset_type == AssetType.DRIVER:
            return await self._validate_driver_directory(asset)
        
        # For other assets, expect a file
        if not asset.path.is_file():
            logger.error(f"Asset path is not a file: {asset.path}")
            return False
        
        # Basic size check
        if asset.path.stat().st_size == 0:
            logger.warning(f"Asset file is empty: {asset.path}")
            return False
        
        # Additional validation based on asset type
        if asset.asset_type == AssetType.SBI:
            return await self._validate_wim_file(asset.path)
        
        return True
    
    async def _load_driver_from_config(self, config_file: Path, device_family: str, os_id: int) -> Optional[DriverAsset]:
        """Load driver configuration and check compatibility."""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Check OS compatibility
            supported_os = config.get('supportedOperatingSystems', [])
            if supported_os and os_id not in supported_os:
                return None
            
            # Check device compatibility (simplified - would need device family mapping)
            supported_devices = config.get('supportedDevices', [])
            
            # Determine driver type from files in directory
            driver_dir = config_file.parent
            driver_type = self._detect_driver_type(driver_dir)
            
            # Find actual driver files
            driver_files = self._find_driver_files(driver_dir, driver_type)
            if not driver_files:
                logger.warning(f"No driver files found in {driver_dir}")
                return None
            
            return DriverAsset(
                name=config.get('driverName', config_file.parent.name),
                path=driver_dir,
                asset_type=AssetType.DRIVER,
                metadata=config,
                driver_type=driver_type,
                family_id=config.get('driverFamilyId'),
                supported_devices=supported_devices,
                supported_os=supported_os,
                order=config.get('order', 9999)
            )
        
        except Exception as e:
            logger.error(f"Failed to load driver config {config_file}: {e}")
            return None
    
    async def _load_update_from_config(self, config_file: Path, os_id: int) -> Optional[UpdateAsset]:
        """Load update configuration and check compatibility."""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Check OS compatibility
            supported_os = config.get('supportedOperatingSystems', [])
            if supported_os and os_id not in supported_os:
                return None
            
            # Find update file
            update_file = config_file.parent / config.get('downloadFileName', '')
            if not update_file.exists():
                logger.warning(f"Update file not found: {update_file}")
                return None
            
            # Determine update type from file extension
            update_type = UpdateType(config.get('updateType', update_file.suffix[1:].lower()))
            
            return UpdateAsset(
                name=config.get('updateName', config_file.parent.name),
                path=update_file,
                asset_type=AssetType.UPDATE,
                metadata=config,
                update_type=update_type,
                update_version=config.get('updateVersion'),
                supported_os=supported_os,
                requires_reboot=config.get('rebootRequired', False),
                order=config.get('order', 9999)
            )
        
        except Exception as e:
            logger.error(f"Failed to load update config {config_file}: {e}")
            return None
    
    def _detect_driver_type(self, driver_dir: Path) -> DriverType:
        """Detect driver type from files in directory."""
        if list(driver_dir.rglob("*.inf")):
            return DriverType.INF
        elif list(driver_dir.rglob("*.appx")):
            return DriverType.APPX
        elif list(driver_dir.rglob("*.exe")):
            return DriverType.EXE
        else:
            return DriverType.INF  # Default
    
    def _find_driver_files(self, driver_dir: Path, driver_type: DriverType) -> List[Path]:
        """Find driver files of specific type."""
        patterns = {
            DriverType.INF: "*.inf",
            DriverType.APPX: "*.appx",
            DriverType.EXE: "*.exe"
        }
        
        pattern = patterns.get(driver_type, "*.inf")
        return list(driver_dir.rglob(pattern))
    
    async def _validate_wim_file(self, wim_path: Path) -> bool:
        """Validate WIM file integrity (basic check)."""
        try:
            # Basic file size check (WIM files should be substantial)
            size_mb = wim_path.stat().st_size / (1024 * 1024)
            if size_mb < 100:  # Less than 100MB is suspicious
                logger.warning(f"WIM file suspiciously small: {size_mb:.1f}MB")
                return False
            
            # TODO: Could add DISM validation here
            # result = subprocess.run(['dism', '/Get-WimInfo', f'/WimFile:{wim_path}'], 
            #                        capture_output=True, text=True)
            # return result.returncode == 0
            
            return True
        except Exception as e:
            logger.error(f"Failed to validate WIM file {wim_path}: {e}")
            return False
    
    async def _validate_driver_directory(self, asset: AssetInfo) -> bool:
        """Validate driver directory structure."""
        if not asset.path.is_dir():
            logger.error(f"Driver asset path is not a directory: {asset.path}")
            return False
        
        # Check if directory contains expected files based on driver type
        if hasattr(asset, 'driver_type'):
            driver_type = asset.driver_type
            
            if driver_type == DriverType.INF:
                inf_files = list(asset.path.rglob("*.inf"))
                if not inf_files:
                    logger.error(f"No INF files found in driver directory: {asset.path}")
                    return False
                logger.info(f"Found {len(inf_files)} INF files in {asset.path}")
                
            elif driver_type == DriverType.APPX:
                appx_files = list(asset.path.rglob("*.appx"))
                if not appx_files:
                    logger.error(f"No APPX files found in driver directory: {asset.path}")
                    return False
                logger.info(f"Found {len(appx_files)} APPX files in {asset.path}")
                
            elif driver_type == DriverType.EXE:
                exe_files = list(asset.path.rglob("*.exe"))
                if not exe_files:
                    logger.error(f"No EXE files found in driver directory: {asset.path}")
                    return False
                logger.info(f"Found {len(exe_files)} EXE files in {asset.path}")
        
        # Check if there's a JSON config file
        json_files = list(asset.path.glob("*.json"))
        if json_files:
            logger.info(f"Found configuration files: {[f.name for f in json_files]}")
        
        return True