# web/app.py - Korrigierte Version mit Asset Provider Fix

"""
Kassia Web Interface - FastAPI Backend (Fixed)
Modern web interface for Windows Image Preparation System
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.requests import Request
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
import uuid

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.config import ConfigLoader
from app.core.asset_providers import LocalAssetProvider
from app.core.wim_handler import WimHandler, WimWorkflow, DismError
from app.core.driver_integration import DriverIntegrator, DriverIntegrationManager
from app.core.update_integration import UpdateIntegrator, UpdateIntegrationManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Kassia Web Interface",
    description="Windows Image Preparation System - Web Edition",
    version="2.0.0"
)

# Static files and templates
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# Global state for job management
class JobStatus:
    """Job status tracking."""
    def __init__(self):
        self.jobs: Dict[str, Dict] = {}
        self.active_connections: List[WebSocket] = []
    
    def create_job(self, device: str, os_id: int) -> str:
        """Create new job."""
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = {
            'id': job_id,
            'device': device,
            'os_id': os_id,
            'status': 'created',
            'progress': 0,
            'current_step': 'Initializing',
            'step_number': 0,
            'total_steps': 9,
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None,
            'error': None,
            'results': {},
            'logs': []
        }
        return job_id
    
    def update_job(self, job_id: str, **kwargs):
        """Update job status."""
        if job_id in self.jobs:
            self.jobs[job_id].update(kwargs)
            # Broadcast to connected websockets
            asyncio.create_task(self.broadcast_job_update(job_id))
    
    async def broadcast_job_update(self, job_id: str):
        """Broadcast job update to all connected clients."""
        if job_id in self.jobs:
            message = {
                'type': 'job_update',
                'job_id': job_id,
                'data': self.jobs[job_id]
            }
            
            # Send to all connected websockets
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    disconnected.append(connection)
            
            # Remove disconnected clients
            for conn in disconnected:
                if conn in self.active_connections:
                    self.active_connections.remove(conn)

job_status = JobStatus()

# Pydantic models for API
class BuildRequest(BaseModel):
    device: str
    os_id: int
    skip_drivers: bool = False
    skip_updates: bool = False
    skip_validation: bool = False

class AssetInfo(BaseModel):
    name: str
    type: str
    path: str
    size: Optional[int] = None
    valid: bool = True

class DeviceInfo(BaseModel):
    device_id: str
    supported_os: List[int]
    description: Optional[str] = None

# API Routes

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/index-{lang}.html", response_class=HTMLResponse)
async def dashboard_lang(request: Request, lang: str):
    """Language-specific dashboard page."""
    supported = {"de", "en", "ru", "cs"}
    if lang not in supported:
        lang = "en"
    template = f"index-{lang}.html"
    return templates.TemplateResponse(template, {"request": request})

@app.get("/api/devices")
async def list_devices() -> List[DeviceInfo]:
    """List available device configurations."""
    try:
        device_configs_path = Path("config/device_configs")
        devices = []
        
        if device_configs_path.exists():
            for json_file in device_configs_path.glob("*.json"):
                try:
                    device_config = ConfigLoader.load_device_config(json_file.stem)
                    devices.append(DeviceInfo(
                        device_id=device_config.deviceId,
                        supported_os=device_config.get_supported_os_ids(),
                        description=getattr(device_config, 'description', None)
                    ))
                except Exception as e:
                    logger.error(f"Failed to load device {json_file.stem}: {e}")
        
        return devices
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/assets/{device}/{os_id}")
async def get_assets(device: str, os_id: int) -> Dict[str, Any]:
    """Get assets for specific device and OS - FIXED VERSION."""
    try:
        # Load configuration
        kassia_config = ConfigLoader.create_kassia_config(device, os_id)
        
        # FIXED: Create asset provider with proper build config integration
        assets_path = Path("assets")
        
        # Pass build config to asset provider for proper path resolution
        build_config_dict = {
            'driverRoot': kassia_config.build.driverRoot,
            'updateRoot': kassia_config.build.updateRoot,
            'sbiRoot': kassia_config.build.sbiRoot,
            'yunonaPath': kassia_config.build.yunonaPath,
            'osWimMap': kassia_config.build.osWimMap
        }
        
        provider = LocalAssetProvider(assets_path, build_config=build_config_dict)
        
        # Get SBI with proper path resolution
        sbi_asset = await provider.get_sbi(os_id)
        sbi_info = None
        if sbi_asset:
            sbi_info = AssetInfo(
                name=sbi_asset.name,
                type="SBI",
                path=str(sbi_asset.path),
                size=sbi_asset.size,
                valid=await provider.validate_asset(sbi_asset)
            )
        
        # Get drivers
        drivers = await provider.get_drivers(device, os_id)
        driver_list = []
        for driver in drivers:
            is_valid = await provider.validate_asset(driver)
            driver_list.append(AssetInfo(
                name=driver.name,
                type=f"Driver ({driver.driver_type.value.upper()})",
                path=str(driver.path),
                size=driver.size,
                valid=is_valid
            ))
        
        # Get updates
        updates = await provider.get_updates(os_id)
        update_list = []
        for update in updates:
            is_valid = await provider.validate_asset(update)
            update_list.append(AssetInfo(
                name=update.name,
                type=f"Update ({update.update_type.value.upper()})",
                path=str(update.path),
                size=update.size,
                valid=is_valid
            ))
        
        # Get Yunona scripts
        scripts = await provider.get_yunona_scripts()
        script_list = []
        for script in scripts:
            is_valid = await provider.validate_asset(script)
            script_list.append(AssetInfo(
                name=script.name,
                type="Yunona Script",
                path=str(script.path),
                size=script.size,
                valid=is_valid
            ))
        
        return {
            "device": kassia_config.device.deviceId,
            "os_id": kassia_config.selectedOsId,
            "sbi": sbi_info.dict() if sbi_info else None,
            "drivers": [d.dict() for d in driver_list],
            "updates": [u.dict() for u in update_list],
            "yunona_scripts": [s.dict() for s in script_list],
            "driver_families_required": len(kassia_config.get_driver_families()),
            "wim_path": str(kassia_config.get_wim_path()) if kassia_config.get_wim_path() else None
        }
        
    except Exception as e:
        logger.error(f"Failed to get assets for {device}/{os_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/build")
async def start_build(build_request: BuildRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    """Start a new build job."""
    try:
        # Create job
        job_id = job_status.create_job(build_request.device, build_request.os_id)
        
        # Start build in background
        background_tasks.add_task(
            execute_build_job, 
            job_id, 
            build_request.device, 
            build_request.os_id,
            build_request.skip_drivers,
            build_request.skip_updates
        )
        
        return {"job_id": job_id, "status": "started"}
        
    except Exception as e:
        logger.error(f"Failed to start build: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs")
async def list_jobs() -> List[Dict]:
    """List all jobs."""
    return list(job_status.jobs.values())

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> Dict:
    """Get specific job status."""
    if job_id not in job_status.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_status.jobs[job_id]

@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str) -> Dict[str, str]:
    """Cancel/delete a job."""
    if job_id not in job_status.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Mark as cancelled
    job_status.update_job(job_id, status="cancelled", completed_at=datetime.now().isoformat())
    
    return {"status": "cancelled"}

# WebSocket for live updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live updates."""
    await websocket.accept()
    job_status.active_connections.append(websocket)
    
    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        if websocket in job_status.active_connections:
            job_status.active_connections.remove(websocket)

# Background job execution
async def execute_build_job(job_id: str, device: str, os_id: int, skip_drivers: bool, skip_updates: bool):
    """Execute build job in background - FIXED VERSION."""
    try:
        # Update job status
        job_status.update_job(
            job_id,
            status="running",
            started_at=datetime.now().isoformat(),
            current_step="Loading configuration",
            step_number=1,
            progress=10
        )
        
        # Load configuration
        kassia_config = ConfigLoader.create_kassia_config(device, os_id)
        
        job_status.update_job(
            job_id,
            current_step="Discovering assets",
            step_number=2,
            progress=20
        )
        
        # FIXED: Create asset provider with proper build config
        assets_path = Path("assets")
        build_config_dict = {
            'driverRoot': kassia_config.build.driverRoot,
            'updateRoot': kassia_config.build.updateRoot,
            'sbiRoot': kassia_config.build.sbiRoot,
            'yunonaPath': kassia_config.build.yunonaPath,
            'osWimMap': kassia_config.build.osWimMap
        }
        
        provider = LocalAssetProvider(assets_path, build_config=build_config_dict)
        
        sbi_asset = await provider.get_sbi(os_id)
        drivers = await provider.get_drivers(device, os_id)
        updates = await provider.get_updates(os_id)
        
        if not sbi_asset:
            job_status.update_job(
                job_id,
                status="failed",
                error="No SBI found for OS ID",
                completed_at=datetime.now().isoformat()
            )
            return
        
        job_status.update_job(
            job_id,
            current_step="Preparing WIM",
            step_number=3,
            progress=30,
            results={
                'sbi_found': True,
                'drivers_count': len(drivers),
                'updates_count': len(updates)
            }
        )
        
        # Initialize WIM workflow
        wim_handler = WimHandler()
        workflow = WimWorkflow(wim_handler)
        
        # Prepare WIM
        temp_dir = Path(kassia_config.build.tempPath)
        temp_wim = await workflow.prepare_wim_for_modification(sbi_asset.path, temp_dir)
        
        job_status.update_job(
            job_id,
            current_step="Mounting WIM",
            step_number=4,
            progress=40
        )
        
        # Mount WIM
        mount_point = Path(kassia_config.build.mountPoint)
        mount_info = await workflow.mount_wim_for_modification(temp_wim, mount_point)
        
        # Driver integration
        if not skip_drivers and drivers:
            job_status.update_job(
                job_id,
                current_step=f"Integrating {len(drivers)} drivers",
                step_number=5,
                progress=50
            )
            
            driver_integrator = DriverIntegrator()
            driver_manager = DriverIntegrationManager(driver_integrator)
            
            driver_result = await driver_manager.integrate_drivers_for_device(
                drivers, mount_point, Path(kassia_config.build.yunonaPath),
                kassia_config.device.deviceId, kassia_config.selectedOsId
            )
            
            job_status.update_job(
                job_id,
                results={
                    **job_status.jobs[job_id]['results'],
                    'driver_integration': driver_result
                }
            )
        
        # Update integration
        if not skip_updates and updates:
            job_status.update_job(
                job_id,
                current_step=f"Integrating {len(updates)} updates",
                step_number=6,
                progress=70
            )
            
            update_integrator = UpdateIntegrator()
            update_manager = UpdateIntegrationManager(update_integrator)
            
            update_result = await update_manager.integrate_updates_for_os(
                updates, mount_point, Path(kassia_config.build.yunonaPath), kassia_config.selectedOsId
            )
            
            job_status.update_job(
                job_id,
                results={
                    **job_status.jobs[job_id]['results'],
                    'update_integration': update_result
                }
            )
        
        # Export WIM
        job_status.update_job(
            job_id,
            current_step="Exporting WIM",
            step_number=7,
            progress=85
        )
        
        export_dir = Path(kassia_config.build.exportPath)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_name = f"{kassia_config.selectedOsId}_{kassia_config.device.deviceId}_{timestamp}.wim"
        export_path = export_dir / export_name
        
        final_wim = await workflow.finalize_and_export_wim(
            mount_point, export_path, 
            export_name=f"Kassia {kassia_config.device.deviceId} OS{kassia_config.selectedOsId}"
        )
        
        # Cleanup
        job_status.update_job(
            job_id,
            current_step="Cleanup",
            step_number=8,
            progress=95
        )
        
        await workflow.cleanup_workflow(keep_export=True)
        
        # Complete
        final_size = final_wim.stat().st_size
        final_size_mb = final_size / (1024 * 1024)
        
        job_status.update_job(
            job_id,
            status="completed",
            current_step="Completed",
            step_number=9,
            progress=100,
            completed_at=datetime.now().isoformat(),
            results={
                **job_status.jobs[job_id]['results'],
                'final_wim_path': str(final_wim),
                'final_wim_size_mb': final_size_mb
            }
        )
        
    except Exception as e:
        logger.error(f"Build job {job_id} failed: {e}")
        job_status.update_job(
            job_id,
            status="failed",
            error=str(e),
            completed_at=datetime.now().isoformat()
        )

# Health check
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    print("🌐 Starting Kassia Web Interface...")
    print("=" * 50)
    print("🚀 FastAPI server starting...")
    print("📊 Dashboard: http://localhost:8000")
    print("📋 API Docs: http://localhost:8000/docs")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
