"""
WIM Handler - DISM Integration for Windows Image Management
"""

import subprocess
import asyncio
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import logging
import os
import tempfile

logger = logging.getLogger(__name__)


@dataclass
class WimInfo:
    """WIM file information."""
    path: Path
    index: int = 1
    name: Optional[str] = None
    description: Optional[str] = None
    architecture: Optional[str] = None
    size: Optional[int] = None
    image_count: int = 1


@dataclass
class MountInfo:
    """WIM mount information."""
    wim_path: Path
    mount_point: Path
    index: int = 1
    is_mounted: bool = False
    mount_time: Optional[datetime] = None
    read_write: bool = True


class DismError(Exception):
    """DISM operation error."""
    def __init__(self, message: str, exit_code: int = None, output: str = None):
        super().__init__(message)
        self.exit_code = exit_code
        self.output = output


class WimHandler:
    """Windows Image Management with DISM integration."""
    
    def __init__(self, dism_path: str = "dism.exe"):
        self.dism_path = dism_path
        self.mounted_images: Dict[str, MountInfo] = {}
        self._validate_dism()
    
    def _validate_dism(self) -> None:
        """Validate DISM availability."""
        try:
            result = subprocess.run(
                [self.dism_path, "/?"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                raise DismError(f"DISM validation failed with exit code {result.returncode}")
            
            logger.info("DISM validation successful")
        except FileNotFoundError:
            raise DismError(f"DISM not found at: {self.dism_path}")
        except Exception as e:
            raise DismError(f"DISM validation error: {str(e)}")
    
    async def get_wim_info(self, wim_path: Path) -> WimInfo:
        """Get WIM file information using DISM."""
        logger.info(f"Getting WIM info for: {wim_path}")
        
        if not wim_path.exists():
            raise DismError(f"WIM file not found: {wim_path}")
        
        try:
            # Run DISM to get WIM info
            cmd = [self.dism_path, "/Get-WimInfo", f"/WimFile:{wim_path}"]
            
            result = await self._run_dism_async(cmd)
            
            # Parse DISM output
            wim_info = self._parse_wim_info(result.stdout, wim_path)
            
            logger.info(f"WIM info retrieved: {wim_info.name}, Index: {wim_info.index}")
            return wim_info
            
        except Exception as e:
            raise DismError(f"Failed to get WIM info: {str(e)}")
    
    async def copy_wim_to_temp(self, source_wim: Path, temp_dir: Path) -> Path:
        """Copy WIM file to temporary location with progress."""
        logger.info(f"Copying WIM to temporary location...")
        
        if not source_wim.exists():
            raise DismError(f"Source WIM not found: {source_wim}")
        
        # Create temp directory
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        temp_wim = temp_dir / source_wim.name
        
        try:
            # Get source size for progress
            source_size = source_wim.stat().st_size
            source_size_mb = source_size / (1024 * 1024)
            
            logger.info(f"Copying {source_size_mb:.1f} MB from {source_wim} to {temp_wim}")
            
            # Copy with chunked reading for large files
            await self._copy_file_async(source_wim, temp_wim)
            
            # Verify copy
            if not temp_wim.exists():
                raise DismError("WIM copy failed - destination file not created")
            
            temp_size = temp_wim.stat().st_size
            if temp_size != source_size:
                raise DismError(f"WIM copy failed - size mismatch: {temp_size} != {source_size}")
            
            logger.info(f"WIM copied successfully to: {temp_wim}")
            return temp_wim
            
        except Exception as e:
            # Cleanup on failure
            if temp_wim.exists():
                temp_wim.unlink()
            raise DismError(f"WIM copy failed: {str(e)}")
    
    async def mount_wim(self, wim_path: Path, mount_point: Path, index: int = 1, read_write: bool = True) -> MountInfo:
        """Mount WIM image using DISM."""
        logger.info(f"Mounting WIM: {wim_path} at {mount_point}")
        
        if not wim_path.exists():
            raise DismError(f"WIM file not found: {wim_path}")
        
        # Create mount point
        mount_point.mkdir(parents=True, exist_ok=True)
        
        # Check if already mounted
        mount_key = str(mount_point)
        if mount_key in self.mounted_images:
            existing_mount = self.mounted_images[mount_key]
            if existing_mount.is_mounted:
                logger.warning(f"Mount point already in use: {mount_point}")
                return existing_mount
        
        try:
            # Build DISM command
            cmd = [
                self.dism_path,
                "/Mount-Wim",
                f"/WimFile:{wim_path}",
                f"/Index:{index}",
                f"/MountDir:{mount_point}"
            ]
            
            if read_write:
                # No additional flag needed for read-write (default)
                pass
            else:
                cmd.append("/ReadOnly")
            
            # Execute mount command
            logger.info("Executing DISM mount command...")
            result = await self._run_dism_async(cmd, timeout=300)  # 5 minute timeout
            
            # Verify mount
            if not self._verify_mount(mount_point):
                raise DismError("Mount verification failed - Windows directory not found")
            
            # Create mount info
            mount_info = MountInfo(
                wim_path=wim_path,
                mount_point=mount_point,
                index=index,
                is_mounted=True,
                mount_time=datetime.now(),
                read_write=read_write
            )
            
            # Store mount info
            self.mounted_images[mount_key] = mount_info
            
            logger.info(f"WIM mounted successfully at: {mount_point}")
            return mount_info
            
        except Exception as e:
            # Cleanup on failure
            await self._cleanup_failed_mount(mount_point)
            raise DismError(f"WIM mount failed: {str(e)}")
    
    async def unmount_wim(self, mount_point: Path, commit: bool = True, discard: bool = False) -> bool:
        """Unmount WIM image using DISM."""
        logger.info(f"Unmounting WIM: {mount_point} (commit={commit}, discard={discard})")
        
        mount_key = str(mount_point)
        mount_info = self.mounted_images.get(mount_key)
        
        if not mount_info or not mount_info.is_mounted:
            logger.warning(f"No mounted image found at: {mount_point}")
            return True
        
        try:
            # Build DISM command
            cmd = [
                self.dism_path,
                "/Unmount-Wim",
                f"/MountDir:{mount_point}"
            ]
            
            if commit and not discard:
                cmd.append("/Commit")
            elif discard:
                cmd.append("/Discard")
            
            # Execute unmount command
            logger.info("Executing DISM unmount command...")
            result = await self._run_dism_async(cmd, timeout=600)  # 10 minute timeout
            
            # Update mount info
            mount_info.is_mounted = False
            
            # Remove from tracking
            if mount_key in self.mounted_images:
                del self.mounted_images[mount_key]
            
            logger.info(f"WIM unmounted successfully: {mount_point}")
            return True
            
        except Exception as e:
            logger.error(f"WIM unmount failed: {str(e)}")
            # Try to force cleanup
            await self._force_cleanup_mount(mount_point)
            return False
    
    async def export_wim(self, source_wim: Path, dest_wim: Path, source_index: int = 1, 
                        dest_name: str = None, compression: str = "max") -> Path:
        """Export WIM image using DISM."""
        logger.info(f"Exporting WIM: {source_wim} -> {dest_wim}")
        
        if not source_wim.exists():
            raise DismError(f"Source WIM not found: {source_wim}")
        
        # Create destination directory
        dest_wim.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Build DISM command
            cmd = [
                self.dism_path,
                "/Export-Image",
                f"/SourceImageFile:{source_wim}",
                f"/SourceIndex:{source_index}",
                f"/DestinationImageFile:{dest_wim}",
                f"/Compress:{compression}"
            ]
            
            if dest_name:
                cmd.append(f"/DestinationName:{dest_name}")
            
            # Execute export command
            logger.info("Executing DISM export command...")
            result = await self._run_dism_async(cmd, timeout=1800)  # 30 minute timeout
            
            # Verify export
            if not dest_wim.exists():
                raise DismError("Export failed - destination file not created")
            
            # Get export size
            export_size = dest_wim.stat().st_size
            export_size_mb = export_size / (1024 * 1024)
            
            logger.info(f"WIM exported successfully: {dest_wim} ({export_size_mb:.1f} MB)")
            return dest_wim
            
        except Exception as e:
            # Cleanup on failure
            if dest_wim.exists():
                dest_wim.unlink()
            raise DismError(f"WIM export failed: {str(e)}")
    
    async def cleanup_all_mounts(self, force: bool = False) -> List[str]:
        """Cleanup all mounted images."""
        logger.info("Cleaning up all mounted images...")
        
        cleanup_results = []
        mount_points = list(self.mounted_images.keys())
        
        for mount_key in mount_points:
            mount_info = self.mounted_images[mount_key]
            try:
                if force:
                    success = await self.unmount_wim(mount_info.mount_point, commit=False, discard=True)
                else:
                    success = await self.unmount_wim(mount_info.mount_point, commit=True)
                
                status = "SUCCESS" if success else "FAILED"
                cleanup_results.append(f"{mount_info.mount_point}: {status}")
                
            except Exception as e:
                cleanup_results.append(f"{mount_info.mount_point}: ERROR - {str(e)}")
        
        logger.info(f"Cleanup completed. Results: {cleanup_results}")
        return cleanup_results
    
    # Helper methods
    
    async def _run_dism_async(self, cmd: List[str], timeout: int = 300) -> subprocess.CompletedProcess:
        """Run DISM command asynchronously with timeout."""
        logger.debug(f"Running DISM command: {' '.join(cmd)}")
        
        try:
            # Run command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            
            # Create result object
            result = subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=stdout.decode('utf-8', errors='ignore'),
                stderr=stderr.decode('utf-8', errors='ignore')
            )
            
            if result.returncode != 0:
                error_msg = f"DISM command failed with exit code {result.returncode}"
                if result.stderr:
                    error_msg += f"\nError: {result.stderr}"
                raise DismError(error_msg, result.returncode, result.stdout)
            
            return result
            
        except asyncio.TimeoutError:
            raise DismError(f"DISM command timed out after {timeout} seconds")
        except Exception as e:
            raise DismError(f"DISM command execution failed: {str(e)}")
    
    async def _copy_file_async(self, source: Path, dest: Path, chunk_size: int = 1024*1024) -> None:
        """Copy file asynchronously with chunked reading."""
        def copy_chunks():
            with open(source, 'rb') as src, open(dest, 'wb') as dst:
                while True:
                    chunk = src.read(chunk_size)
                    if not chunk:
                        break
                    dst.write(chunk)
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, copy_chunks)
    
    def _parse_wim_info(self, dism_output: str, wim_path: Path) -> WimInfo:
        """Parse DISM WIM info output."""
        lines = dism_output.split('\n')
        
        wim_info = WimInfo(path=wim_path)
        
        for line in lines:
            line = line.strip()
            if 'Index :' in line:
                try:
                    wim_info.index = int(line.split(':')[1].strip())
                except:
                    pass
            elif 'Name :' in line:
                wim_info.name = line.split(':', 1)[1].strip()
            elif 'Description :' in line:
                wim_info.description = line.split(':', 1)[1].strip()
            elif 'Architecture :' in line:
                wim_info.architecture = line.split(':', 1)[1].strip()
        
        # Get file size
        if wim_path.exists():
            wim_info.size = wim_path.stat().st_size
        
        return wim_info
    
    def _verify_mount(self, mount_point: Path) -> bool:
        """Verify that WIM is properly mounted."""
        # Check for Windows directory
        windows_dir = mount_point / "Windows"
        return windows_dir.exists() and windows_dir.is_dir()
    
    async def _cleanup_failed_mount(self, mount_point: Path) -> None:
        """Cleanup failed mount attempt."""
        try:
            # Try to unmount with discard
            cmd = [self.dism_path, "/Unmount-Wim", f"/MountDir:{mount_point}", "/Discard"]
            await self._run_dism_async(cmd, timeout=60)
        except:
            pass  # Ignore errors during cleanup
    
    async def _force_cleanup_mount(self, mount_point: Path) -> None:
        """Force cleanup of mount point."""
        try:
            # Try cleanup-wim command
            cmd = [self.dism_path, "/Cleanup-Wim"]
            await self._run_dism_async(cmd, timeout=60)
        except:
            pass  # Ignore errors during cleanup


class WimWorkflow:
    """High-level WIM workflow management."""
    
    def __init__(self, wim_handler: WimHandler):
        self.wim_handler = wim_handler
        self.workflow_state = {
            'temp_wim': None,
            'mount_info': None,
            'export_path': None
        }
    
    async def prepare_wim_for_modification(self, source_wim: Path, temp_dir: Path) -> Path:
        """Prepare WIM for modification by copying to temp location."""
        logger.info("Step 1: Preparing WIM for modification...")
        
        # Validate source WIM
        wim_info = await self.wim_handler.get_wim_info(source_wim)
        logger.info(f"Source WIM info: {wim_info.name} ({wim_info.architecture})")
        
        # Copy to temp location
        temp_wim = await self.wim_handler.copy_wim_to_temp(source_wim, temp_dir)
        self.workflow_state['temp_wim'] = temp_wim
        
        return temp_wim
    
    async def mount_wim_for_modification(self, wim_path: Path, mount_point: Path) -> MountInfo:
        """Mount WIM for modification."""
        logger.info("Step 2: Mounting WIM for modification...")
        
        mount_info = await self.wim_handler.mount_wim(wim_path, mount_point, read_write=True)
        self.workflow_state['mount_info'] = mount_info
        
        return mount_info
    
    async def finalize_and_export_wim(self, mount_point: Path, export_path: Path, 
                                     export_name: str = None) -> Path:
        """Finalize modifications and export WIM."""
        logger.info("Step 3: Finalizing and exporting WIM...")
        
        # Unmount with commit
        success = await self.wim_handler.unmount_wim(mount_point, commit=True)
        if not success:
            raise DismError("Failed to unmount WIM with changes")
        
        # Export final WIM
        temp_wim = self.workflow_state['temp_wim']
        if not temp_wim:
            raise DismError("No temporary WIM found for export")
        
        final_wim = await self.wim_handler.export_wim(
            temp_wim, export_path, dest_name=export_name
        )
        
        self.workflow_state['export_path'] = final_wim
        return final_wim
    
    async def cleanup_workflow(self, keep_export: bool = True) -> None:
        """Cleanup workflow temporary files."""
        logger.info("Cleaning up workflow...")
        
        # Cleanup any remaining mounts
        await self.wim_handler.cleanup_all_mounts(force=True)
        
        # Remove temp WIM
        temp_wim = self.workflow_state.get('temp_wim')
        if temp_wim and temp_wim.exists():
            try:
                temp_wim.unlink()
                logger.info(f"Removed temporary WIM: {temp_wim}")
            except Exception as e:
                logger.warning(f"Failed to remove temp WIM: {e}")
        
        # Optionally remove export (for testing)
        if not keep_export:
            export_path = self.workflow_state.get('export_path')
            if export_path and export_path.exists():
                try:
                    export_path.unlink()
                    logger.info(f"Removed export WIM: {export_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove export WIM: {e}")
        
        # Reset state
        self.workflow_state = {
            'temp_wim': None,
            'mount_info': None,
            'export_path': None
        }