"""
Update Integration Engine
Integrates Windows updates into mounted WIM images using DISM and Yunona staging
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

from .asset_providers import UpdateAsset, UpdateType, AssetType
from .wim_handler import DismError

logger = logging.getLogger(__name__)


@dataclass
class UpdateIntegrationResult:
    """Result of update integration operation."""
    update_asset: UpdateAsset
    success: bool
    method: str  # "DISM", "YUNONA", "SKIPPED"
    message: str
    duration: Optional[float] = None
    size_added: Optional[int] = None  # Bytes added to WIM


class UpdateIntegrator:
    """Update integration engine for WIM images."""
    
    def __init__(self, dism_path: str = "dism.exe"):
        self.dism_path = dism_path
        self.integration_stats = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'msu_via_dism': 0,
            'cab_via_dism': 0,
            'exe_via_yunona': 0,
            'msi_via_yunona': 0,
            'total_size_added': 0
        }
    
    async def integrate_updates(self, updates: List[UpdateAsset], mount_point: Path, 
                               yunona_path: Path) -> List[UpdateIntegrationResult]:
        """Integrate all updates into mounted WIM."""
        logger.info(f"Starting integration of {len(updates)} updates")
        
        if not mount_point.exists():
            raise DismError(f"Mount point does not exist: {mount_point}")
        
        # Verify mount point has Windows directory
        windows_dir = mount_point / "Windows"
        if not windows_dir.exists():
            raise DismError(f"Invalid mount point - no Windows directory: {mount_point}")
        
        # Ensure Yunona directory exists in mounted WIM
        yunona_target = mount_point / "Users" / "Public" / "Yunona"
        yunona_target.mkdir(parents=True, exist_ok=True)
        
        # Ensure Updates directory in Yunona
        updates_target = yunona_target / "Updates"
        updates_target.mkdir(parents=True, exist_ok=True)
        
        results = []
        self.integration_stats['total'] = len(updates)
        
        # Sort updates by order for proper installation sequence
        sorted_updates = sorted(updates, key=lambda u: u.order)
        
        for update in sorted_updates:
            logger.info(f"Processing update: {update.name} [{update.update_type.value}]")
            
            try:
                result = await self._integrate_single_update(update, mount_point, updates_target)
                results.append(result)
                
                if result.success:
                    self.integration_stats['successful'] += 1
                    if result.size_added:
                        self.integration_stats['total_size_added'] += result.size_added
                    logger.info(f"Update integration successful: {update.name}")
                else:
                    self.integration_stats['failed'] += 1
                    logger.error(f"Update integration failed: {update.name} - {result.message}")
                    
            except Exception as e:
                error_result = UpdateIntegrationResult(
                    update_asset=update,
                    success=False,
                    method="ERROR",
                    message=f"Unexpected error: {str(e)}"
                )
                results.append(error_result)
                self.integration_stats['failed'] += 1
                logger.error(f"Update integration error for {update.name}: {e}")
        
        logger.info(f"Update integration completed. Success: {self.integration_stats['successful']}, "
                   f"Failed: {self.integration_stats['failed']}")
        
        return results
    
    async def _integrate_single_update(self, update: UpdateAsset, mount_point: Path, 
                                     updates_target: Path) -> UpdateIntegrationResult:
        """Integrate a single update based on its type."""
        start_time = datetime.now()
        
        # Get initial WIM size for size calculation
        initial_size = self._get_mount_size(mount_point)
        
        if update.update_type in [UpdateType.MSU, UpdateType.CAB]:
            result = await self._integrate_dism_update(update, mount_point)
            if result.success:
                if update.update_type == UpdateType.MSU:
                    self.integration_stats['msu_via_dism'] += 1
                else:
                    self.integration_stats['cab_via_dism'] += 1
                    
        elif update.update_type in [UpdateType.EXE, UpdateType.MSI]:
            result = await self._stage_update_to_yunona(update, updates_target)
            if result.success:
                if update.update_type == UpdateType.EXE:
                    self.integration_stats['exe_via_yunona'] += 1
                else:
                    self.integration_stats['msi_via_yunona'] += 1
        else:
            result = UpdateIntegrationResult(
                update_asset=update,
                success=False,
                method="SKIPPED",
                message=f"Unknown update type: {update.update_type}"
            )
        
        # Calculate duration and size added
        duration = (datetime.now() - start_time).total_seconds()
        result.duration = duration
        
        if result.success and update.update_type in [UpdateType.MSU, UpdateType.CAB]:
            final_size = self._get_mount_size(mount_point)
            result.size_added = max(0, final_size - initial_size)
        
        return result
    
    async def _integrate_dism_update(self, update: UpdateAsset, mount_point: Path) -> UpdateIntegrationResult:
        """Integrate MSU/CAB update using DISM."""
        logger.info(f"Integrating {update.update_type.value.upper()} update via DISM: {update.name}")
        
        try:
            if not update.path.exists():
                return UpdateIntegrationResult(
                    update_asset=update,
                    success=False,
                    method="DISM",
                    message=f"Update file not found: {update.path}"
                )
            
            # Validate file size
            file_size = update.path.stat().st_size
            if file_size == 0:
                return UpdateIntegrationResult(
                    update_asset=update,
                    success=False,
                    method="DISM",
                    message="Update file is empty"
                )
            
            # Build DISM command for update installation
            cmd = [
                self.dism_path,
                f"/Image:{mount_point}",
                "/Add-Package",
                f"/PackagePath:{update.path}"
            ]
            
            logger.debug(f"DISM command: {' '.join(cmd)}")
            
            # Execute DISM command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=600)  # 10 minute timeout
            
            # Parse result
            if process.returncode == 0:
                file_size_mb = file_size / (1024 * 1024)
                return UpdateIntegrationResult(
                    update_asset=update,
                    success=True,
                    method="DISM",
                    message=f"{update.update_type.value.upper()} update installed successfully ({file_size_mb:.1f} MB)"
                )
            else:
                error_output = stderr.decode('utf-8', errors='ignore')
                stdout_output = stdout.decode('utf-8', errors='ignore')
                
                # Check for common DISM errors
                if "not applicable" in error_output.lower() or "not applicable" in stdout_output.lower():
                    return UpdateIntegrationResult(
                        update_asset=update,
                        success=False,
                        method="DISM",
                        message="Update not applicable to this image"
                    )
                elif "already installed" in error_output.lower() or "already installed" in stdout_output.lower():
                    return UpdateIntegrationResult(
                        update_asset=update,
                        success=True,
                        method="DISM",
                        message="Update already installed"
                    )
                else:
                    return UpdateIntegrationResult(
                        update_asset=update,
                        success=False,
                        method="DISM",
                        message=f"DISM failed with exit code {process.returncode}: {error_output[:200]}"
                    )
                
        except asyncio.TimeoutError:
            return UpdateIntegrationResult(
                update_asset=update,
                success=False,
                method="DISM",
                message="DISM operation timed out (600 seconds)"
            )
        except Exception as e:
            return UpdateIntegrationResult(
                update_asset=update,
                success=False,
                method="DISM",
                message=f"DISM execution failed: {str(e)}"
            )
    
    async def _stage_update_to_yunona(self, update: UpdateAsset, updates_target: Path) -> UpdateIntegrationResult:
        """Stage EXE/MSI update to Yunona for post-deployment installation."""
        logger.info(f"Staging {update.update_type.value.upper()} update to Yunona: {update.name}")
        
        try:
            if not update.path.exists():
                return UpdateIntegrationResult(
                    update_asset=update,
                    success=False,
                    method="YUNONA",
                    message=f"Update file not found: {update.path}"
                )
            
            # Create target directory for this update
            update_target = updates_target / update.path.stem
            update_target.mkdir(parents=True, exist_ok=True)
            
            # Copy update file and any accompanying files from the same directory
            copied_files = 0
            source_dir = update.path.parent
            
            for item in source_dir.rglob("*"):
                if item.is_file():
                    relative_path = item.relative_to(source_dir)
                    target_file = update_target / relative_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy file
                    await self._copy_file_async(item, target_file)
                    copied_files += 1
            
            # Create installation script
            if update.update_type == UpdateType.EXE:
                install_script = self._create_exe_update_script(update)
                script_path = update_target / "install_update.cmd"
            else:  # MSI
                install_script = self._create_msi_update_script(update)
                script_path = update_target / "install_update.cmd"
            
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(install_script)
            
            # Create update metadata
            metadata = {
                "updateName": update.name,
                "updateVersion": update.update_version,
                "updateType": update.update_type.value,
                "requiresReboot": update.requires_reboot,
                "stagedAt": datetime.now().isoformat(),
                "originalPath": str(update.path),
                "filesCopied": copied_files
            }
            
            metadata_path = update_target / "update_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            file_size = update.path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            
            return UpdateIntegrationResult(
                update_asset=update,
                success=True,
                method="YUNONA",
                message=f"{update.update_type.value.upper()} update staged successfully ({file_size_mb:.1f} MB, {copied_files} files)"
            )
            
        except Exception as e:
            return UpdateIntegrationResult(
                update_asset=update,
                success=False,
                method="YUNONA",
                message=f"Failed to stage {update.update_type.value.upper()} update: {str(e)}"
            )
    
    def _create_exe_update_script(self, update: UpdateAsset) -> str:
        """Create batch script for EXE update installation."""
        script_lines = [
            "@echo off",
            f"REM EXE Update Installation Script",
            f"REM Update: {update.name}",
            f"REM Version: {update.update_version}",
            f"REM Generated: {datetime.now().isoformat()}",
            "",
            f"echo Installing update: {update.name}...",
            "",
            f'echo Executing: {update.path.name}',
            f'"{update.path.name}" /quiet /norestart',
            f"set INSTALL_RESULT=%errorlevel%",
            "",
            f"if %INSTALL_RESULT% equ 0 (",
            f"    echo Successfully installed: {update.name}",
        ]
        
        if update.requires_reboot:
            script_lines.extend([
                f"    echo Reboot required for: {update.name}",
                f"    echo REBOOT_REQUIRED=true > install_result.txt"
            ])
        else:
            script_lines.append(f"    echo No reboot required")
        
        script_lines.extend([
            f") else (",
            f"    echo Failed to install: {update.name} (Exit code: %INSTALL_RESULT%)",
            f"    echo INSTALL_FAILED=true > install_result.txt",
            f")",
            "",
            f"echo Update installation completed with result: %INSTALL_RESULT%"
        ])
        
        return "\n".join(script_lines)
    
    def _create_msi_update_script(self, update: UpdateAsset) -> str:
        """Create batch script for MSI update installation."""
        script_lines = [
            "@echo off",
            f"REM MSI Update Installation Script",
            f"REM Update: {update.name}",
            f"REM Version: {update.update_version}",
            f"REM Generated: {datetime.now().isoformat()}",
            "",
            f"echo Installing MSI update: {update.name}...",
            "",
            f'echo Executing: msiexec /i {update.path.name}',
            f'msiexec /i "{update.path.name}" /quiet /norestart /l*v install_log.txt',
            f"set INSTALL_RESULT=%errorlevel%",
            "",
            f"if %INSTALL_RESULT% equ 0 (",
            f"    echo Successfully installed: {update.name}",
        ]
        
        if update.requires_reboot:
            script_lines.extend([
                f"    echo Reboot required for: {update.name}",
                f"    echo REBOOT_REQUIRED=true > install_result.txt"
            ])
        else:
            script_lines.append(f"    echo No reboot required")
        
        script_lines.extend([
            f") else (",
            f"    echo Failed to install: {update.name} (Exit code: %INSTALL_RESULT%)",
            f"    echo INSTALL_FAILED=true > install_result.txt",
            f")",
            "",
            f"echo MSI installation completed with result: %INSTALL_RESULT%"
        ])
        
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
    
    def _get_mount_size(self, mount_point: Path) -> int:
        """Get approximate size of mounted directory."""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(mount_point):
                for filename in filenames:
                    filepath = Path(dirpath) / filename
                    try:
                        total_size += filepath.stat().st_size
                    except (OSError, FileNotFoundError):
                        pass
            return total_size
        except Exception:
            return 0
    
    def get_integration_summary(self) -> Dict[str, int]:
        """Get integration statistics summary."""
        return self.integration_stats.copy()


class UpdateIntegrationManager:
    """High-level update integration management."""
    
    def __init__(self, integrator: UpdateIntegrator):
        self.integrator = integrator
    
    async def integrate_updates_for_os(self, updates: List[UpdateAsset], mount_point: Path,
                                     yunona_path: Path, os_id: int) -> Dict:
        """Integrate updates for specific OS."""
        logger.info(f"Starting update integration for OS {os_id}")
        
        if not updates:
            return {
                'success': True,
                'message': 'No updates to integrate',
                'results': [],
                'stats': self.integrator.get_integration_summary()
            }
        
        # Filter and validate updates
        compatible_updates = []
        for update in updates:
            if self._validate_update_compatibility(update, os_id):
                compatible_updates.append(update)
            else:
                logger.warning(f"Skipping incompatible update: {update.name}")
        
        if not compatible_updates:
            return {
                'success': True,
                'message': 'No compatible updates found',
                'results': [],
                'stats': self.integrator.get_integration_summary()
            }
        
        # Execute integration
        try:
            results = await self.integrator.integrate_updates(
                compatible_updates, mount_point, yunona_path
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
            logger.error(f"Update integration failed: {e}")
            return {
                'success': False,
                'message': f'Integration failed: {str(e)}',
                'results': [],
                'stats': self.integrator.get_integration_summary()
            }
    
    def _validate_update_compatibility(self, update: UpdateAsset, os_id: int) -> bool:
        """Validate update compatibility with OS."""
        if not update.supported_os:
            return True  # Assume compatible if no OS restriction
        
        return os_id in update.supported_os
    
    def format_integration_results(self, results: List[UpdateIntegrationResult]) -> List[str]:
        """Format integration results for display."""
        formatted = []
        
        for result in results:
            update = result.update_asset
            status = "✅" if result.success else "❌"
            duration_str = f" ({result.duration:.1f}s)" if result.duration else ""
            
            formatted.append(
                f"   {status} {update.name} [{update.update_type.value.upper()}] "
                f"via {result.method}{duration_str}"
            )
            
            if not result.success:
                formatted.append(f"      💥 {result.message}")
            elif result.size_added and result.size_added > 0:
                size_mb = result.size_added / (1024 * 1024)
                formatted.append(f"      📊 Added {size_mb:.1f} MB to WIM")
            elif "files" in result.message.lower():
                formatted.append(f"      📁 {result.message}")
        
        return formatted