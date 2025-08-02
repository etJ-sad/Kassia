"""
Driver Integration Engine
Integrates drivers into mounted WIM images using DISM and Yunona staging
"""

import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
import shutil
import json

from .asset_providers import DriverAsset, DriverType, AssetType
from .wim_handler import DismError

logger = logging.getLogger(__name__)


@dataclass
class DriverIntegrationResult:
    """Result of driver integration operation."""
    driver_asset: DriverAsset
    success: bool
    method: str  # "DISM", "YUNONA", "SKIPPED"
    message: str
    duration: Optional[float] = None
    files_processed: int = 0


class DriverIntegrator:
    """Driver integration engine for WIM images."""
    
    def __init__(self, dism_path: str = "dism.exe"):
        self.dism_path = dism_path
        self.integration_stats = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'inf_via_dism': 0,
            'appx_via_yunona': 0,
            'exe_via_yunona': 0
        }
    
    async def integrate_drivers(self, drivers: List[DriverAsset], mount_point: Path, 
                               yunona_path: Path) -> List[DriverIntegrationResult]:
        """Integrate all drivers into mounted WIM."""
        logger.info(f"Starting integration of {len(drivers)} drivers")
        
        if not mount_point.exists():
            raise DismError(f"Mount point does not exist: {mount_point}")
        
        # Verify mount point has Windows directory
        windows_dir = mount_point / "Windows"
        if not windows_dir.exists():
            raise DismError(f"Invalid mount point - no Windows directory: {mount_point}")
        
        # Ensure Yunona directory exists in mounted WIM
        yunona_target = mount_point / "Users" / "Public" / "Yunona"
        yunona_target.mkdir(parents=True, exist_ok=True)
        
        # Copy Yunona core files if not present
        await self._ensure_yunona_in_wim(yunona_path, yunona_target)
        
        results = []
        self.integration_stats['total'] = len(drivers)
        
        # Sort drivers by order for proper installation sequence
        sorted_drivers = sorted(drivers, key=lambda d: d.order)
        
        for driver in sorted_drivers:
            logger.info(f"Processing driver: {driver.name} [{driver.driver_type.value}]")
            
            try:
                result = await self._integrate_single_driver(driver, mount_point, yunona_target)
                results.append(result)
                
                if result.success:
                    self.integration_stats['successful'] += 1
                    logger.info(f"Driver integration successful: {driver.name}")
                else:
                    self.integration_stats['failed'] += 1
                    logger.error(f"Driver integration failed: {driver.name} - {result.message}")
                    
            except Exception as e:
                error_result = DriverIntegrationResult(
                    driver_asset=driver,
                    success=False,
                    method="ERROR",
                    message=f"Unexpected error: {str(e)}"
                )
                results.append(error_result)
                self.integration_stats['failed'] += 1
                logger.error(f"Driver integration error for {driver.name}: {e}")
        
        logger.info(f"Driver integration completed. Success: {self.integration_stats['successful']}, "
                   f"Failed: {self.integration_stats['failed']}")
        
        return results
    
    async def _integrate_single_driver(self, driver: DriverAsset, mount_point: Path, 
                                     yunona_target: Path) -> DriverIntegrationResult:
        """Integrate a single driver based on its type."""
        start_time = datetime.now()
        
        if driver.driver_type == DriverType.INF:
            result = await self._integrate_inf_driver(driver, mount_point)
            if result.success:
                self.integration_stats['inf_via_dism'] += 1
                
        elif driver.driver_type == DriverType.APPX:
            result = await self._stage_appx_driver(driver, yunona_target)
            if result.success:
                self.integration_stats['appx_via_yunona'] += 1
                
        elif driver.driver_type == DriverType.EXE:
            result = await self._stage_exe_driver(driver, yunona_target)
            if result.success:
                self.integration_stats['exe_via_yunona'] += 1
        else:
            result = DriverIntegrationResult(
                driver_asset=driver,
                success=False,
                method="SKIPPED",
                message=f"Unknown driver type: {driver.driver_type}"
            )
        
        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()
        result.duration = duration
        
        return result
    
    async def _integrate_inf_driver(self, driver: DriverAsset, mount_point: Path) -> DriverIntegrationResult:
        """Integrate INF driver using DISM."""
        logger.info(f"Integrating INF driver via DISM: {driver.name}")
        
        try:
            # Find INF files in driver directory
            inf_files = list(driver.path.rglob("*.inf"))
            if not inf_files:
                return DriverIntegrationResult(
                    driver_asset=driver,
                    success=False,
                    method="DISM",
                    message="No INF files found in driver directory"
                )
            
            # Build DISM command for driver installation
            cmd = [
                self.dism_path,
                f"/Image:{mount_point}",
                "/Add-Driver",
                f"/Driver:{driver.path}",
                "/Recurse",
                "/ForceUnsigned"  # Allow unsigned drivers for development
            ]
            
            logger.debug(f"DISM command: {' '.join(cmd)}")
            
            # Execute DISM command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
            
            # Parse result
            if process.returncode == 0:
                return DriverIntegrationResult(
                    driver_asset=driver,
                    success=True,
                    method="DISM",
                    message=f"INF driver installed successfully ({len(inf_files)} files)",
                    files_processed=len(inf_files)
                )
            else:
                error_output = stderr.decode('utf-8', errors='ignore')
                return DriverIntegrationResult(
                    driver_asset=driver,
                    success=False,
                    method="DISM",
                    message=f"DISM failed with exit code {process.returncode}: {error_output}"
                )
                
        except asyncio.TimeoutError:
            return DriverIntegrationResult(
                driver_asset=driver,
                success=False,
                method="DISM",
                message="DISM operation timed out (300 seconds)"
            )
        except Exception as e:
            return DriverIntegrationResult(
                driver_asset=driver,
                success=False,
                method="DISM",
                message=f"DISM execution failed: {str(e)}"
            )
    
    async def _stage_appx_driver(self, driver: DriverAsset, yunona_target: Path) -> DriverIntegrationResult:
        """Stage APPX driver package to Yunona for post-deployment installation."""
        logger.info(f"Staging APPX driver to Yunona: {driver.name}")
        
        try:
            # Find APPX files
            appx_files = list(driver.path.rglob("*.appx"))
            if not appx_files:
                return DriverIntegrationResult(
                    driver_asset=driver,
                    success=False,
                    method="YUNONA",
                    message="No APPX files found in driver directory"
                )
            
            # Create target directory in Yunona
            driver_target = yunona_target / "Drivers" / driver.path.name
            driver_target.mkdir(parents=True, exist_ok=True)
            
            # Copy entire driver directory to preserve dependencies
            copied_files = 0
            for item in driver.path.rglob("*"):
                if item.is_file():
                    relative_path = item.relative_to(driver.path)
                    target_file = driver_target / relative_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy file
                    await self._copy_file_async(item, target_file)
                    copied_files += 1
            
            # Create installation script for APPX
            install_script = self._create_appx_install_script(driver, appx_files)
            script_path = driver_target / "install_appx.ps1"
            
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(install_script)
            
            return DriverIntegrationResult(
                driver_asset=driver,
                success=True,
                method="YUNONA",
                message=f"APPX driver staged successfully ({len(appx_files)} packages)",
                files_processed=copied_files
            )
            
        except Exception as e:
            return DriverIntegrationResult(
                driver_asset=driver,
                success=False,
                method="YUNONA",
                message=f"Failed to stage APPX driver: {str(e)}"
            )
    
    async def _stage_exe_driver(self, driver: DriverAsset, yunona_target: Path) -> DriverIntegrationResult:
        """Stage EXE driver installer to Yunona for post-deployment installation."""
        logger.info(f"Staging EXE driver to Yunona: {driver.name}")
        
        try:
            # Find EXE files
            exe_files = list(driver.path.rglob("*.exe"))
            if not exe_files:
                return DriverIntegrationResult(
                    driver_asset=driver,
                    success=False,
                    method="YUNONA",
                    message="No EXE files found in driver directory"
                )
            
            # Create target directory in Yunona
            driver_target = yunona_target / "Drivers" / driver.path.name
            driver_target.mkdir(parents=True, exist_ok=True)
            
            # Copy entire driver directory
            copied_files = 0
            for item in driver.path.rglob("*"):
                if item.is_file():
                    relative_path = item.relative_to(driver.path)
                    target_file = driver_target / relative_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy file
                    await self._copy_file_async(item, target_file)
                    copied_files += 1
            
            # Create installation script for EXE
            install_script = self._create_exe_install_script(driver, exe_files)
            script_path = driver_target / "install_exe.cmd"
            
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(install_script)
            
            return DriverIntegrationResult(
                driver_asset=driver,
                success=True,
                method="YUNONA",
                message=f"EXE driver staged successfully ({len(exe_files)} installers)",
                files_processed=copied_files
            )
            
        except Exception as e:
            return DriverIntegrationResult(
                driver_asset=driver,
                success=False,
                method="YUNONA",
                message=f"Failed to stage EXE driver: {str(e)}"
            )
    
    async def _ensure_yunona_in_wim(self, yunona_source: Path, yunona_target: Path) -> None:
        """Ensure Yunona core files are present in the mounted WIM."""
        if not yunona_source.exists():
            logger.warning(f"Yunona source path does not exist: {yunona_source}")
            return
        
        # Check if Yunona config exists in target
        config_target = yunona_target / "config.json"
        
        if not config_target.exists():
            logger.info("Copying Yunona core files to WIM")
            
            # Copy Yunona core files
            for item in yunona_source.rglob("*"):
                if item.is_file() and not item.name.startswith('.'):
                    relative_path = item.relative_to(yunona_source)
                    target_file = yunona_target / relative_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    await self._copy_file_async(item, target_file)
            
            logger.info("Yunona core files copied to WIM")
    
    def _create_appx_install_script(self, driver: DriverAsset, appx_files: List[Path]) -> str:
        """Create PowerShell script for APPX installation."""
        script_lines = [
            "# APPX Driver Installation Script",
            f"# Generated for: {driver.name}",
            f"# Family ID: {driver.family_id}",
            "",
            "Write-Host 'Installing APPX driver packages...'",
            ""
        ]
        
        for appx_file in appx_files:
            script_lines.extend([
                f"Write-Host 'Installing {appx_file.name}...'",
                f"try {{",
                f"    Add-AppxPackage -Path '{appx_file.name}' -ForceApplicationShutdown",
                f"    Write-Host 'Successfully installed {appx_file.name}'",
                f"}} catch {{",
                f"    Write-Host 'Failed to install {appx_file.name}: $_' -ForegroundColor Red",
                f"}}",
                ""
            ])
        
        script_lines.append("Write-Host 'APPX driver installation completed.'")
        
        return "\n".join(script_lines)
    
    def _create_exe_install_script(self, driver: DriverAsset, exe_files: List[Path]) -> str:
        """Create batch script for EXE installation."""
        script_lines = [
            "@echo off",
            f"REM EXE Driver Installation Script",
            f"REM Generated for: {driver.name}",
            f"REM Family ID: {driver.family_id}",
            "",
            "echo Installing EXE driver packages...",
            ""
        ]
        
        for exe_file in exe_files:
            script_lines.extend([
                f"echo Installing {exe_file.name}...",
                f'"{exe_file.name}" /S /V"/qn"',
                f"if errorlevel 1 (",
                f"    echo Failed to install {exe_file.name}",
                f") else (",
                f"    echo Successfully installed {exe_file.name}",
                f")",
                ""
            ])
        
        script_lines.append("echo EXE driver installation completed.")
        
        return "\n".join(script_lines)
    
    async def _copy_file_async(self, source: Path, dest: Path, chunk_size: int = 1024*1024) -> None:
        """Copy file asynchronously."""
        def copy_file():
            with open(source, 'rb') as src, open(dest, 'wb') as dst:
                while True:
                    chunk = src.read(chunk_size)
                    if not chunk:
                        break
                    dst.write(chunk)
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, copy_file)
    
    def get_integration_summary(self) -> Dict[str, int]:
        """Get integration statistics summary."""
        return self.integration_stats.copy()


class DriverIntegrationManager:
    """High-level driver integration management."""
    
    def __init__(self, integrator: DriverIntegrator):
        self.integrator = integrator
    
    async def integrate_drivers_for_device(self, drivers: List[DriverAsset], mount_point: Path,
                                         yunona_path: Path, device_id: str, os_id: int) -> Dict:
        """Integrate drivers for specific device and OS."""
        logger.info(f"Starting driver integration for device {device_id}, OS {os_id}")
        
        if not drivers:
            return {
                'success': True,
                'message': 'No drivers to integrate',
                'results': [],
                'stats': self.integrator.get_integration_summary()
            }
        
        # Filter and validate drivers
        compatible_drivers = []
        for driver in drivers:
            if self._validate_driver_compatibility(driver, os_id):
                compatible_drivers.append(driver)
            else:
                logger.warning(f"Skipping incompatible driver: {driver.name}")
        
        if not compatible_drivers:
            return {
                'success': True,
                'message': 'No compatible drivers found',
                'results': [],
                'stats': self.integrator.get_integration_summary()
            }
        
        # Execute integration
        try:
            results = await self.integrator.integrate_drivers(
                compatible_drivers, mount_point, yunona_path
            )
            
            # Analyze results
            successful_count = sum(1 for r in results if r.success)
            failed_count = len(results) - successful_count
            
            return {
                'success': failed_count == 0,
                'message': f'Integration completed: {successful_count} successful, {failed_count} failed',
                'results': results,
                'stats': self.integrator.get_integration_summary(),
                'successful_count': successful_count,
                'failed_count': failed_count
            }
            
        except Exception as e:
            logger.error(f"Driver integration failed: {e}")
            return {
                'success': False,
                'message': f'Integration failed: {str(e)}',
                'results': [],
                'stats': self.integrator.get_integration_summary()
            }
    
    def _validate_driver_compatibility(self, driver: DriverAsset, os_id: int) -> bool:
        """Validate driver compatibility with OS."""
        if not driver.supported_os:
            return True  # Assume compatible if no OS restriction
        
        return os_id in driver.supported_os
    
    def format_integration_results(self, results: List[DriverIntegrationResult]) -> List[str]:
        """Format integration results for display."""
        formatted = []
        
        for result in results:
            driver = result.driver_asset
            status = "✅" if result.success else "❌"
            duration_str = f" ({result.duration:.1f}s)" if result.duration else ""
            
            formatted.append(
                f"   {status} {driver.name} [{driver.driver_type.value.upper()}] "
                f"via {result.method}{duration_str}"
            )
            
            if not result.success:
                formatted.append(f"      💥 {result.message}")
            elif result.files_processed:
                formatted.append(f"      📁 {result.files_processed} files processed")
        
        return formatted