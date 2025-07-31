# web/app.py - Fixed Job System Integration

"""
Kassia Web Interface - FastAPI Backend mit korrigiertem Job-System
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.requests import Request
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
import uuid
import time

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import logging system
from app.utils.logging import (
    get_logger, configure_logging, LogLevel, LogCategory, get_log_buffer,
    get_job_logger, create_job_logger, finalize_job_logging, get_job_log_files
)

# Import database system
from app.utils.job_database import get_job_database, init_job_database

# Import existing modules
from app.models.config import ConfigLoader
from app.core.asset_providers import LocalAssetProvider
from app.core.wim_handler import WimHandler, WimWorkflow, DismError
from app.core.driver_integration import DriverIntegrator, DriverIntegrationManager
from app.core.update_integration import UpdateIntegrator, UpdateIntegrationManager

# Configure logging for WebUI
configure_logging(
    level=LogLevel.INFO,
    log_dir=Path("runtime/logs"),
    enable_console=True,
    enable_file=True,
    enable_webui=True  # Enable WebUI logging
)

# Initialize logger
logger = get_logger("kassia.webui")

# Initialize database
print("🗄️ Initializing job database...")
job_db = init_job_database(Path("runtime/data/kassia_webui_jobs.db"))

# Log database initialization
logger.info("Database initialized", LogCategory.WEBUI, {
    'database_path': str(job_db.db_path),
    'database_size_mb': job_db.get_database_info().get('database_size_mb', 0)
})

# FastAPI app
app = FastAPI(
    title="Kassia Web Interface",
    description="Windows Image Preparation System - Web Edition with Database Integration",
    version="2.0.0"
)

# Static files and templates
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# Log startup
logger.info("Kassia WebUI starting", LogCategory.WEBUI, {
    'version': "2.0.0",
    'startup_time': datetime.now().isoformat(),
    'database_enabled': True
})

# Enhanced Job Status with Database Integration
class JobStatus:
    """Job status tracking mit integrierter Datenbank."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.logger = get_logger("kassia.webui.jobs")
        self.job_db = get_job_database()
        
        # Load existing jobs from database on startup
        self._load_jobs_from_database()
    
    def _load_jobs_from_database(self):
        """Load all jobs from database on startup."""
        try:
            jobs = self.job_db.get_all_jobs()
            self.logger.info(f"Loaded {len(jobs)} jobs from database", LogCategory.WEBUI)
            
            # Reset running jobs to failed (app was restarted while job was running)
            interrupted_jobs = []
            for job in jobs:
                if job['status'] == 'running':
                    self.logger.warning(f"Found interrupted job {job['id']}, marking as failed")
                    self.job_db.update_job(job['id'], {
                        'status': 'failed',
                        'error': 'Application restart during execution',
                        'completed_at': datetime.now().isoformat()
                    })
                    interrupted_jobs.append(job['id'])
            
            if interrupted_jobs:
                self.logger.info("Marked interrupted jobs as failed", LogCategory.WEBUI, {
                    'interrupted_jobs': interrupted_jobs
                })
            
        except Exception as e:
            self.logger.error(f"Failed to load jobs from database: {e}", LogCategory.WEBUI)
    
    def create_job(self, device: str, os_id: int, user_id: str = "web_user", 
                   skip_drivers: bool = False, skip_updates: bool = False, 
                   skip_validation: bool = False) -> str:
        """Create new job with database persistence."""
        job_id = str(uuid.uuid4())
        
        job_data = {
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
            'user_id': user_id,
            'skip_drivers': skip_drivers,
            'skip_updates': skip_updates,
            'skip_validation': skip_validation,
            'created_by': 'webui'
        }
        
        # Save to database
        if self.job_db.create_job(job_data):
            self.logger.info("Job created and saved to database", LogCategory.WEBUI, {
                'job_id': job_id,
                'device': device,
                'os_id': os_id,
                'user_id': user_id
            })
            
            # Create dedicated job logger
            create_job_logger(job_id)
            
            return job_id
        else:
            raise Exception("Failed to save job to database")
    
    def update_job(self, job_id: str, **kwargs):
        """Update job status with database persistence."""
        
        # Update in database
        if self.job_db.update_job(job_id, kwargs):
            # Get old status for logging
            old_job = self.job_db.get_job(job_id)
            old_status = old_job.get('status') if old_job else None
            new_status = kwargs.get('status')
            
            # Log status changes
            if old_status != new_status and new_status:
                self.logger.info("Job status changed", LogCategory.WEBUI, {
                    'job_id': job_id,
                    'old_status': old_status,
                    'new_status': new_status,
                    'progress': kwargs.get('progress'),
                    'current_step': kwargs.get('current_step')
                })
            
            # Broadcast to connected websockets
            asyncio.create_task(self.broadcast_job_update(job_id))
        else:
            self.logger.warning("Failed to update job in database", LogCategory.WEBUI, {
                'job_id': job_id
            })
    
    def add_job_log(self, job_id: str, message: str, level: str = "INFO", 
                   component: str = "webui", category: str = "JOB"):
        """Add log entry to job with database persistence."""
        timestamp = datetime.now().isoformat()
        
        # Save to database
        self.job_db.add_job_log(
            job_id=job_id,
            timestamp=timestamp,
            level=level,
            message=message,
            component=component,
            category=category
        )
        
        # Broadcast update
        asyncio.create_task(self.broadcast_job_update(job_id))
    
    async def broadcast_job_update(self, job_id: str):
        """Broadcast job update to all connected clients."""
        # Get current job data from database
        job_data = self.job_db.get_job(job_id)
        
        if not job_data:
            return
        
        # Add recent logs to the broadcast
        recent_logs = self.job_db.get_job_logs(job_id, limit=10)
        job_data['logs'] = [
            {
                'timestamp': log['timestamp'],
                'level': log['level'],
                'message': log['message'],
                'category': log.get('category', 'JOB'),
                'component': log.get('component', 'webui')
            }
            for log in recent_logs
        ]
        
        message = {
            'type': 'job_update',
            'job_id': job_id,
            'data': job_data
        }
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message, default=str))
            except Exception as e:
                self.logger.warning("WebSocket send failed", LogCategory.WEBUI, {
                    'error': str(e)
                })
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)
    
    def get_all_jobs(self) -> List[Dict]:
        """Get all jobs from database."""
        return self.job_db.get_all_jobs()
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get single job from database."""
        return self.job_db.get_job(job_id)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel job and update in database."""
        updates = {
            'status': 'cancelled',
            'completed_at': datetime.now().isoformat()
        }
        
        if self.job_db.update_job(job_id, updates):
            # Finalize job logging
            finalize_job_logging(job_id, "cancelled")
            
            self.logger.info("Job cancelled", LogCategory.WEBUI, {
                'job_id': job_id
            })
            
            return True
        
        return False

    def delete_job(self, job_id: str) -> bool:
        """Delete job from database."""
        if self.job_db.delete_job(job_id):
            self.logger.info("Job deleted from database", LogCategory.WEBUI, {
                'job_id': job_id
            })
            return True
        return False

# Global job status instance
job_status = JobStatus()

# Pydantic models
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

class LogEntry(BaseModel):
    timestamp: str
    level: str
    category: str
    component: str
    message: str
    details: Optional[Dict[str, Any]] = None
    job_id: Optional[str] = None

# Language detection for templates
def get_template_path(request: Request, template_name: str = "index.html") -> tuple[str, str]:
    """Determine template path and language based on the request settings."""
    # Path parameter takes highest precedence
    lang = request.path_params.get('lang') if hasattr(request, 'path_params') else None

    # Fallback to explicit query parameter
    if not lang:
        lang = request.query_params.get('lang')

    # Finally inspect the Accept-Language header
    if not lang:
        accept_language = request.headers.get('accept-language', '').lower()
        if 'de' in accept_language:
            lang = 'de'
        elif 'ru' in accept_language:
            lang = 'ru'
        elif 'cs' in accept_language:
            lang = 'cs'
        else:
            lang = 'en'
    
    # Check if specific language template exists
    lang_template = f"index-{lang}.html"
    template_path = Path("web/templates") / lang_template
    
    if template_path.exists():
        return lang_template, lang
    else:
        return "index.html", lang  # Fallback to default


def load_translations(lang: str) -> Dict[str, str]:
    """Load translation dictionary for the given language."""
    file_path = Path("web/translations") / f"{lang}.json"
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# API Routes with Database Integration

@app.get("/", response_class=HTMLResponse)
@app.get("/index-{lang}.html", response_class=HTMLResponse)
async def dashboard(request: Request, lang: str = None):
    """Main dashboard page with language support."""
    logger.debug("Dashboard page requested", LogCategory.API, {
        'client_ip': request.client.host,
        'user_agent': request.headers.get('user-agent', 'unknown'),
        'language': lang
    })
    
    template_file, resolved_lang = get_template_path(request)
    strings = load_translations(resolved_lang)
    context = {"request": request, "lang": resolved_lang, "strings": strings}
    return templates.TemplateResponse(template_file, context)

@app.get("/api/devices")
async def list_devices() -> List[DeviceInfo]:
    """List available device configurations with logging."""
    logger.log_operation_start("list_devices")
    start_time = time.time()
    
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
                    logger.error("Failed to load device config", LogCategory.API, {
                        'device_file': json_file.stem,
                        'error': str(e)
                    })
        
        duration = time.time() - start_time
        logger.log_operation_success("list_devices", duration, {
            'device_count': len(devices),
            'devices': [d.device_id for d in devices]
        })
        
        return devices
        
    except Exception as e:
        duration = time.time() - start_time
        logger.log_operation_failure("list_devices", str(e), duration)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/assets/{device}/{os_id}")
async def get_assets(device: str, os_id: int) -> Dict[str, Any]:
    """Get assets for specific device and OS with detailed logging."""
    logger.set_context(device=device, os_id=os_id)
    logger.log_operation_start("get_assets")
    start_time = time.time()
    
    try:
        # Load configuration
        kassia_config = ConfigLoader.create_kassia_config(device, os_id)
        
        # Create asset provider with proper build config integration
        assets_path = Path("assets")
        
        build_config_dict = {
            'driverRoot': kassia_config.build.driverRoot,
            'updateRoot': kassia_config.build.updateRoot,
            'sbiRoot': kassia_config.build.sbiRoot,
            'yunonaPath': kassia_config.build.yunonaPath,
            'osWimMap': kassia_config.build.osWimMap
        }
        
        provider = LocalAssetProvider(assets_path, build_config=build_config_dict)
        
        logger.info("Asset provider initialized", LogCategory.ASSET, {
            'provider_config': build_config_dict
        })
        
        # Get SBI with proper path resolution
        logger.debug("Discovering SBI assets", LogCategory.ASSET)
        sbi_asset = await provider.get_sbi(os_id)
        sbi_info = None
        if sbi_asset:
            is_valid = await provider.validate_asset(sbi_asset)
            sbi_info = AssetInfo(
                name=sbi_asset.name,
                type="SBI",
                path=str(sbi_asset.path),
                size=sbi_asset.size,
                valid=is_valid
            )
            logger.info("SBI asset found", LogCategory.ASSET, {
                'name': sbi_asset.name,
                'path': str(sbi_asset.path),
                'size_mb': sbi_asset.size / (1024 * 1024) if sbi_asset.size else 0,
                'valid': is_valid
            })
        else:
            logger.warning("No SBI asset found", LogCategory.ASSET)
        
        # Get drivers
        logger.debug("Discovering driver assets", LogCategory.DRIVER)
        drivers = await provider.get_drivers(device, os_id)
        driver_list = []
        driver_validation_results = []
        
        for driver in drivers:
            is_valid = await provider.validate_asset(driver)
            driver_list.append(AssetInfo(
                name=driver.name,
                type=f"Driver ({driver.driver_type.value.upper()})",
                path=str(driver.path),
                size=driver.size,
                valid=is_valid
            ))
            driver_validation_results.append({
                'name': driver.name,
                'type': driver.driver_type.value,
                'family_id': driver.family_id,
                'valid': is_valid
            })
        
        logger.info("Driver assets discovered", LogCategory.DRIVER, {
            'count': len(drivers),
            'validation_results': driver_validation_results
        })
        
        # Get updates
        logger.debug("Discovering update assets", LogCategory.UPDATE)
        updates = await provider.get_updates(os_id)
        update_list = []
        update_validation_results = []
        
        for update in updates:
            is_valid = await provider.validate_asset(update)
            update_list.append(AssetInfo(
                name=update.name,
                type=f"Update ({update.update_type.value.upper()})",
                path=str(update.path),
                size=update.size,
                valid=is_valid
            ))
            update_validation_results.append({
                'name': update.name,
                'type': update.update_type.value,
                'version': update.update_version,
                'valid': is_valid
            })
        
        logger.info("Update assets discovered", LogCategory.UPDATE, {
            'count': len(updates),
            'validation_results': update_validation_results
        })
        
        # Get Yunona scripts
        logger.debug("Discovering Yunona scripts", LogCategory.ASSET)
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
        
        logger.info("Yunona scripts discovered", LogCategory.ASSET, {
            'count': len(scripts)
        })
        
        # Build response
        response = {
            "device": kassia_config.device.deviceId,
            "os_id": kassia_config.selectedOsId,
            "sbi": sbi_info.dict() if sbi_info else None,
            "drivers": [d.dict() for d in driver_list],
            "updates": [u.dict() for u in update_list],
            "yunona_scripts": [s.dict() for s in script_list],
            "driver_families_required": len(kassia_config.get_driver_families()),
            "wim_path": str(kassia_config.get_wim_path()) if kassia_config.get_wim_path() else None
        }
        
        duration = time.time() - start_time
        logger.log_operation_success("get_assets", duration, {
            'sbi_found': bool(sbi_info),
            'drivers_count': len(driver_list),
            'updates_count': len(update_list),
            'scripts_count': len(script_list)
        })
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        logger.log_operation_failure("get_assets", str(e), duration)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        logger.clear_context()

@app.post("/api/build")
async def start_build(build_request: BuildRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    """Start a new build job with database persistence."""
    logger.log_operation_start("start_build")
    start_time = time.time()
    
    try:
        # Create job with all build parameters
        job_id = job_status.create_job(
            build_request.device, 
            build_request.os_id,
            skip_drivers=build_request.skip_drivers,
            skip_updates=build_request.skip_updates,
            skip_validation=build_request.skip_validation
        )
        
        logger.info("Build job created", LogCategory.WEBUI, {
            'job_id': job_id,
            'device': build_request.device,
            'os_id': build_request.os_id,
            'skip_drivers': build_request.skip_drivers,
            'skip_updates': build_request.skip_updates
        })
        
        # Start build in background
        background_tasks.add_task(
            execute_build_job_with_logging, 
            job_id, 
            build_request.device, 
            build_request.os_id,
            build_request.skip_drivers,
            build_request.skip_updates,
            build_request.skip_validation
        )
        
        duration = time.time() - start_time
        logger.log_operation_success("start_build", duration, {
            'job_id': job_id
        })
        
        return {"job_id": job_id, "status": "started"}
        
    except Exception as e:
        duration = time.time() - start_time
        logger.log_operation_failure("start_build", str(e), duration)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs")
async def list_jobs(limit: int = 50, status: str = None) -> List[Dict]:
    """List all jobs from database with optional filtering."""
    try:
        jobs = job_status.get_all_jobs()
        
        # Apply status filter if provided
        if status:
            jobs = [job for job in jobs if job['status'] == status]
        
        # Apply limit
        jobs = jobs[:limit]
        
        logger.debug("Jobs list requested", LogCategory.API, {
            'job_count': len(jobs),
            'status_filter': status,
            'limit': limit
        })
        return jobs
    except Exception as e:
        logger.error("Failed to list jobs", LogCategory.API, {'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> Dict:
    """Get specific job status from database."""
    job = job_status.get_job(job_id)
    
    if not job:
        logger.warning("Job not found in database", LogCategory.API, {
            'job_id': job_id
        })
        raise HTTPException(status_code=404, detail="Job not found")
    
    logger.debug("Job details requested", LogCategory.API, {
        'job_id': job_id,
        'status': job['status']
    })
    
    return job

@app.get("/api/jobs/{job_id}/logs")
async def get_job_logs(job_id: str, source: str = "database", level: str = None, limit: int = 1000) -> List[Dict]:
    """Get job logs from database with filtering."""
    job = job_status.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        if source == "errors":
            # Get only error logs
            logs = job_db.get_job_logs(job_id, level_filter="ERROR", limit=limit)
        else:
            # Get all logs (default: database)
            logs = job_db.get_job_logs(job_id, level_filter=level, limit=limit)
        
        logger.debug("Job logs requested", LogCategory.API, {
            'job_id': job_id,
            'source': source,
            'level_filter': level,
            'log_count': len(logs)
        })
        
        return logs
        
    except Exception as e:
        logger.error("Failed to get job logs", LogCategory.API, {
            'job_id': job_id,
            'error': str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs/{job_id}/log-files")
async def get_job_log_files(job_id: str) -> Dict[str, Any]:
    """Get information about job log files."""
    if not job_status.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    
    log_files = get_job_log_files(job_id)
    
    result = {
        'job_id': job_id,
        'files': {}
    }
    
    for file_type, file_path in log_files.items():
        if file_path and file_path.exists():
            stat = file_path.stat()
            result['files'][file_type] = {
                'path': str(file_path),
                'size_bytes': stat.st_size,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'exists': True
            }
        else:
            result['files'][file_type] = {
                'path': str(file_path) if file_path else None,
                'exists': False
            }
    
    logger.debug("Job log files info requested", LogCategory.API, {
        'job_id': job_id,
        'files_available': [k for k, v in result['files'].items() if v['exists']]
    })
    
    return result

@app.get("/api/jobs/{job_id}/download-log")
async def download_job_log(job_id: str, log_type: str = "main"):
    """Download job log file."""
    if not job_status.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    
    log_buffer = get_log_buffer()
    if not log_buffer:
        raise HTTPException(status_code=503, detail="Log buffer not available")
    
    if log_type == "main":
        log_file = log_buffer.get_job_log_file(job_id)
    elif log_type == "error":
        log_file = log_buffer.get_job_error_file(job_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid log type. Use 'main' or 'error'")
    
    if not log_file or not log_file.exists():
        raise HTTPException(status_code=404, detail=f"Job {log_type} log file not found")
    
    logger.info("Job log file downloaded", LogCategory.API, {
        'job_id': job_id,
        'log_type': log_type,
        'file_size': log_file.stat().st_size
    })
    
    return FileResponse(
        path=str(log_file),
        filename=f"kassia_job_{job_id}_{log_type}.log",
        media_type="text/plain"
    )

@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str) -> Dict[str, str]:
    """Cancel/delete a job in database."""
    if not job_status.cancel_job(job_id):
        logger.warning("Failed to cancel job", LogCategory.API, {
            'job_id': job_id
        })
        raise HTTPException(status_code=404, detail="Job not found or could not be cancelled")
    
    return {"status": "cancelled"}

@app.delete("/api/jobs/{job_id}/delete")
async def delete_job(job_id: str) -> Dict[str, str]:
    """Permanently delete a job from database."""
    if not job_status.delete_job(job_id):
        logger.warning("Failed to delete job", LogCategory.API, {
            'job_id': job_id
        })
        raise HTTPException(status_code=404, detail="Job not found or could not be deleted")
    
    return {"status": "deleted"}

# =================== DATABASE MANAGEMENT ROUTES ===================

@app.get("/api/admin/database/info")
async def get_database_info() -> Dict[str, Any]:
    """Get database information and statistics."""
    try:
        db_info = job_db.get_database_info()
        
        logger.info("Database info requested", LogCategory.API, db_info)
        
        return db_info
        
    except Exception as e:
        logger.error("Failed to get database info", LogCategory.API, {'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/statistics")
async def get_statistics(days: int = 30) -> List[Dict[str, Any]]:
    """Get job statistics for the last N days."""
    try:
        stats = job_db.get_statistics(days)
        
        logger.debug("Statistics requested", LogCategory.API, {
            'days': days,
            'statistics_count': len(stats)
        })
        
        return stats
        
    except Exception as e:
        logger.error("Failed to get statistics", LogCategory.API, {'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/maintenance/cleanup")
async def cleanup_old_data(days: int = 90) -> Dict[str, str]:
    """Cleanup old job data from database."""
    try:
        job_db.cleanup_old_data(days)
        
        logger.info("Database cleanup completed", LogCategory.API, {
            'cleanup_days': days
        })
        
        return {"status": "cleanup completed", "days": days}
        
    except Exception as e:
        logger.error("Failed to cleanup database", LogCategory.API, {'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/maintenance/update-statistics")
async def update_statistics() -> Dict[str, str]:
    """Update daily statistics manually."""
    try:
        job_db.update_daily_statistics()
        
        logger.info("Statistics updated manually", LogCategory.API)
        
        return {"status": "statistics updated"}
        
    except Exception as e:
        logger.error("Failed to update statistics", LogCategory.API, {'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/logs")
async def get_system_logs(limit: int = 100, level: Optional[str] = None) -> List[Dict]:
    """Get system logs for WebUI display."""
    log_buffer = get_log_buffer()
    if not log_buffer:
        return []
    
    logs = log_buffer.get_recent_logs(limit)
    
    # Filter by level if specified
    if level:
        logs = [log for log in logs if log.level == level.upper()]
    
    # Convert to dictionary format
    log_dicts = [log.to_dict() for log in logs]
    
    logger.debug("System logs requested", LogCategory.API, {
        'limit': limit,
        'level_filter': level,
        'returned_count': len(log_dicts)
    })
    
    return log_dicts

@app.get("/api/system/health")
async def system_health() -> Dict[str, Any]:
    """Get system health status with logging."""
    logger.debug("System health check requested", LogCategory.API)
    
    try:
        import psutil
        import shutil
        
        # Get disk usage
        disk_usage = shutil.disk_usage('.')
        disk_free_gb = disk_usage.free / (1024**3)
        disk_total_gb = disk_usage.total / (1024**3)
        disk_used_percent = ((disk_usage.total - disk_usage.free) / disk_usage.total) * 100
        
        # Get memory usage
        memory = psutil.virtual_memory()
        
        # Check DISM availability
        try:
            wim_handler = WimHandler()
            dism_available = True
        except:
            dism_available = False
        
        # Count active jobs
        all_jobs = job_status.get_all_jobs()
        active_builds = len([j for j in all_jobs if j['status'] == 'running'])
        
        # Get database stats
        db_info = job_db.get_database_info()
        
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "disk_usage": {
                "free_gb": round(disk_free_gb, 2),
                "total_gb": round(disk_total_gb, 2),
                "used_percent": round(disk_used_percent, 1)
            },
            "memory_usage": {
                "percent": memory.percent,
                "available_gb": round(memory.available / (1024**3), 2),
                "total_gb": round(memory.total / (1024**3), 2)
            },
            "active_builds": active_builds,
            "total_jobs": len(all_jobs),
            "dism_available": dism_available,
            "log_buffer_size": len(get_log_buffer().buffer) if get_log_buffer() else 0,
            "database": {
                "size_mb": db_info.get('database_size_mb', 0),
                "job_count": db_info.get('job_count', 0),
                "log_count": db_info.get('log_count', 0)
            }
        }
        
        logger.info("System health check completed", LogCategory.SYSTEM, health_data)
        
        return health_data
        
    except Exception as e:
        logger.error("System health check failed", LogCategory.SYSTEM, {
            'error': str(e)
        })
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# WebSocket for live updates with logging
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live updates with connection logging."""
    await websocket.accept()
    job_status.active_connections.append(websocket)
    
    client_info = {
        'client_ip': websocket.client.host,
        'connection_count': len(job_status.active_connections)
    }
    
    logger.info("WebSocket connection established", LogCategory.WEBUI, client_info)
    
    try:
        while True:
            # Keep connection alive and send periodic system info
            await asyncio.sleep(30)
            
            # Send heartbeat with system status
            all_jobs = job_status.get_all_jobs()
            heartbeat = {
                "type": "heartbeat",
                "timestamp": datetime.now().isoformat(),
                "active_connections": len(job_status.active_connections),
                "active_jobs": len([j for j in all_jobs if j['status'] == 'running']),
                "total_jobs": len(all_jobs)
            }
            
            await websocket.send_text(json.dumps(heartbeat))
            
    except WebSocketDisconnect:
        if websocket in job_status.active_connections:
            job_status.active_connections.remove(websocket)
        
        logger.info("WebSocket connection closed", LogCategory.WEBUI, {
            'client_ip': websocket.client.host,
            'remaining_connections': len(job_status.active_connections)
        })
    except Exception as e:
        logger.error("WebSocket error", LogCategory.WEBUI, {
            'error': str(e),
            'client_ip': websocket.client.host
        })
        if websocket in job_status.active_connections:
            job_status.active_connections.remove(websocket)

# Background job execution with comprehensive logging and database persistence
async def execute_build_job_with_logging(job_id: str, device: str, os_id: int, 
                                       skip_drivers: bool, skip_updates: bool, skip_validation: bool):
    """Execute build job in background with database persistence and detailed logging."""
    
    # Set up job-specific logger context
    job_logger = get_logger("kassia.webui.build")
    
    # Create job context for enhanced logging
    with job_logger.create_job_context(job_id):
        job_logger.log_operation_start("build_job")
        job_start_time = time.time()
        
        try:
            # Update job status in database
            job_status.update_job(
                job_id,
                status="running",
                started_at=datetime.now().isoformat(),
                current_step="Loading configuration",
                step_number=1,
                progress=10
            )
            
            job_status.add_job_log(job_id, "Build job started", "INFO")
            job_logger.info("Build job execution started", LogCategory.WORKFLOW)
            
            # Load configuration
            job_logger.info("Loading configuration", LogCategory.CONFIG)
            kassia_config = ConfigLoader.create_kassia_config(device, os_id)
            
            job_status.update_job(
                job_id,
                current_step="Discovering assets",
                step_number=2,
                progress=20
            )
            
            job_status.add_job_log(job_id, "Configuration loaded successfully", "INFO")
            job_logger.info("Configuration loaded", LogCategory.CONFIG, {
                'device_id': kassia_config.device.deviceId,
                'selected_os': kassia_config.selectedOsId
            })
            
            # Create asset provider with proper build config
            assets_path = Path("assets")
            build_config_dict = {
                'driverRoot': kassia_config.build.driverRoot,
                'updateRoot': kassia_config.build.updateRoot,
                'sbiRoot': kassia_config.build.sbiRoot,
                'yunonaPath': kassia_config.build.yunonaPath,
                'osWimMap': kassia_config.build.osWimMap
            }
            
            provider = LocalAssetProvider(assets_path, build_config=build_config_dict)
            
            # Discover assets
            job_logger.info("Discovering assets", LogCategory.ASSET)
            sbi_asset = await provider.get_sbi(os_id)
            drivers = await provider.get_drivers(device, os_id)
            updates = await provider.get_updates(os_id)
            
            job_status.add_job_log(job_id, f"Assets discovered: SBI={bool(sbi_asset)}, Drivers={len(drivers)}, Updates={len(updates)}", "INFO")
            job_logger.info("Asset discovery completed", LogCategory.ASSET, {
                'sbi_found': bool(sbi_asset),
                'drivers_count': len(drivers),
                'updates_count': len(updates)
            })
            
            if not sbi_asset:
                error_msg = f"No SBI found for OS ID {os_id}"
                job_status.update_job(
                    job_id,
                    status="failed",
                    error=error_msg,
                    completed_at=datetime.now().isoformat()
                )
                job_status.add_job_log(job_id, error_msg, "ERROR")
                job_logger.error(error_msg, LogCategory.ASSET)
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
            job_logger.info("Initializing WIM workflow", LogCategory.WIM)
            wim_handler = WimHandler()
            workflow = WimWorkflow(wim_handler)
            
            # Prepare WIM
            job_status.add_job_log(job_id, "Copying WIM to temporary location", "INFO")
            temp_dir = Path(kassia_config.build.tempPath)
            temp_wim = await workflow.prepare_wim_for_modification(sbi_asset.path, temp_dir)
            
            job_logger.info("WIM preparation completed", LogCategory.WIM, {
                'temp_wim': str(temp_wim)
            })
            
            job_status.update_job(
                job_id,
                current_step="Mounting WIM",
                step_number=4,
                progress=40
            )
            
            # Mount WIM
            job_status.add_job_log(job_id, "Mounting WIM for modification", "INFO")
            mount_point = Path(kassia_config.build.mountPoint)
            mount_info = await workflow.mount_wim_for_modification(temp_wim, mount_point)
            
            job_logger.info("WIM mounted successfully", LogCategory.WIM, {
                'mount_point': str(mount_point),
                'read_write': mount_info.read_write
            })
            
            # Driver integration
            if not skip_drivers and drivers:
                job_status.update_job(
                    job_id,
                    current_step=f"Integrating {len(drivers)} drivers",
                    step_number=5,
                    progress=50
                )
                
                job_status.add_job_log(job_id, f"Starting driver integration ({len(drivers)} drivers)", "INFO")
                job_logger.info("Starting driver integration", LogCategory.DRIVER, {
                    'driver_count': len(drivers)
                })
                
                driver_integrator = DriverIntegrator()
                driver_manager = DriverIntegrationManager(driver_integrator)
                
                driver_result = await driver_manager.integrate_drivers_for_device(
                    drivers, mount_point, Path(kassia_config.build.yunonaPath),
                    kassia_config.device.deviceId, kassia_config.selectedOsId
                )
                
                job_status.update_job(
                    job_id,
                    results={
                        **job_status.get_job(job_id).get('results', {}),
                        'driver_integration': driver_result
                    }
                )
                
                success_msg = f"Driver integration completed: {driver_result['successful_count']}/{len(drivers)} successful"
                job_status.add_job_log(job_id, success_msg, "INFO")
                job_logger.info("Driver integration completed", LogCategory.DRIVER, driver_result)
            
            # Update integration
            if not skip_updates and updates:
                job_status.update_job(
                    job_id,
                    current_step=f"Integrating {len(updates)} updates",
                    step_number=6,
                    progress=70
                )
                
                job_status.add_job_log(job_id, f"Starting update integration ({len(updates)} updates)", "INFO")
                job_logger.info("Starting update integration", LogCategory.UPDATE, {
                    'update_count': len(updates)
                })
                
                update_integrator = UpdateIntegrator()
                update_manager = UpdateIntegrationManager(update_integrator)
                
                update_result = await update_manager.integrate_updates_for_os(
                    updates, mount_point, Path(kassia_config.build.yunonaPath), kassia_config.selectedOsId
                )
                
                job_status.update_job(
                    job_id,
                    results={
                        **job_status.get_job(job_id).get('results', {}),
                        'update_integration': update_result
                    }
                )
                
                success_msg = f"Update integration completed: {update_result['successful_count']}/{len(updates)} successful"
                job_status.add_job_log(job_id, success_msg, "INFO")
                job_logger.info("Update integration completed", LogCategory.UPDATE, update_result)
            
            # Export WIM
            job_status.update_job(
                job_id,
                current_step="Exporting WIM",
                step_number=7,
                progress=85
            )
            
            job_status.add_job_log(job_id, "Creating final WIM image", "INFO")
            job_logger.info("Starting WIM export", LogCategory.WIM)
            
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
            
            job_status.add_job_log(job_id, "Cleaning up temporary files", "INFO")
            await workflow.cleanup_workflow(keep_export=True)
            
            # Complete
            final_size = final_wim.stat().st_size
            final_size_mb = final_size / (1024 * 1024)
            
            job_duration = time.time() - job_start_time
            
            final_results = {
                'final_wim_path': str(final_wim),
                'final_wim_size_mb': final_size_mb,
                'total_duration_seconds': job_duration,
                'driver_integration': locals().get('driver_result', {}),
                'update_integration': locals().get('update_result', {}),
                'export_name': export_name
            }
            
            job_status.update_job(
                job_id,
                status="completed", 
                current_step="Completed",
                step_number=9,
                progress=100, 
                completed_at=datetime.now().isoformat(),
                results=final_results
            )

            # Force WebSocket broadcast
            await job_status.broadcast_job_update(job_id)
            await asyncio.sleep(0.5)  

            #job_status.update_job(job_id, current_step="Cleanup", progress=95)
            #await workflow.cleanup_workflow(keep_export=True)

            # Final 100% update
            job_status.update_job(job_id, progress=100, current_step="Completed")
            await job_status.broadcast_job_update(job_id)
            
            success_msg = f"Build completed successfully! Final WIM: {final_size_mb:.1f} MB"
            job_status.add_job_log(job_id, success_msg, "INFO")
            job_logger.log_operation_success("build_job", job_duration, {
                'final_wim': str(final_wim),
                'final_size_mb': final_size_mb
            })
            
            # Finalize job logging
            finalize_job_logging(job_id, "completed")
            
            # Update daily statistics
            job_db.update_daily_statistics()
            
        except Exception as e:
            job_duration = time.time() - job_start_time
            error_msg = str(e)
            
            job_logger.log_operation_failure("build_job", error_msg, job_duration)
            
            job_status.update_job(
                job_id,
                status="failed",
                error=error_msg,
                completed_at=datetime.now().isoformat()
            )
            
            job_status.add_job_log(job_id, f"Build failed: {error_msg}", "ERROR")
            
            # Finalize job logging with error
            finalize_job_logging(job_id, "failed", error_msg)
            
            # Update daily statistics
            job_db.update_daily_statistics()
            
            # Re-raise to be handled by job context
            raise

# Health check
@app.get("/api/health")
async def health_check():
    """Health check endpoint with logging."""
    logger.debug("Health check requested", LogCategory.API)
    return {
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "database": "enabled"
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    """Enhanced startup with database initialization."""
    logger.info("Kassia WebUI started successfully", LogCategory.WEBUI, {
        'startup_complete': True,
        'endpoints_count': len(app.routes),
        'database_path': str(job_db.db_path),
        'database_enabled': True
    })
    
    # Update daily statistics on startup
    try:
        job_db.update_daily_statistics()
        logger.info("Daily statistics updated on startup", LogCategory.WEBUI)
    except Exception as e:
        logger.error("Failed to update statistics on startup", LogCategory.WEBUI, {'error': str(e)})

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Enhanced shutdown with database cleanup."""
    all_jobs = job_status.get_all_jobs()
    active_jobs = [j for j in all_jobs if j['status'] == 'running']
    
    # Mark any running jobs as interrupted
    for job in active_jobs:
        job_status.update_job(job['id'], 
            status="failed",
            error="Application shutdown during execution",
            completed_at=datetime.now().isoformat()
        )
    
    logger.info("Kassia WebUI shutting down", LogCategory.WEBUI, {
        'active_connections': len(job_status.active_connections),
        'interrupted_jobs': len(active_jobs),
        'total_jobs': len(all_jobs)
    })

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Kassia WebUI server with database", LogCategory.WEBUI)
    
    print("🌐 Starting Kassia Web Interface with Database Integration...")
    print("=" * 70)
    print("🚀 FastAPI server starting...")
    print("📊 Dashboard: http://localhost:8000")
    print("📋 API Docs: http://localhost:8000/docs")
    print("📜 Logs: runtime/logs/")
    print("🗄️ Database: runtime/data/kassia_webui_jobs.db")
    print("📊 Admin Panel: http://localhost:8000 (Admin Tab)")
    print("🔧 Database Management & Statistics available")
    print("=" * 70)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)  # reload=False für Production