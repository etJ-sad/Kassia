# web/app.py - FIXED Async Initialization Job System Integration

"""
Kassia Web Interface - FastAPI Backend with proper async initialization
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.requests import Request
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import asyncio
import json
import sys
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, timedelta
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
    enable_webui=True
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

# =================== TRANSLATION ROUTES FIRST (CRITICAL ORDER) ===================

# Check translation directory
translations_path = Path("web/translations")
if translations_path.exists():
    available_translations = [f.stem for f in translations_path.glob("*.json")]
    logger.info("Translation system configured", LogCategory.WEBUI, {
        'translations_path': str(translations_path),
        'available_languages': available_translations,
        'translation_files': [str(f) for f in translations_path.glob("*.json")]
    })
    print(f"🌍 Translation system: {len(available_translations)} languages available")
    print(f"   Languages: {', '.join(available_translations)}")
else:
    logger.error("Translation directory not found", LogCategory.WEBUI, {
        'expected_path': str(translations_path),
        'exists': translations_path.exists()
    })
    print(f"❌ Translation directory not found: {translations_path}")

# CRITICAL: Translation routes MUST be defined BEFORE static file mount
@app.get("/static/translations/{language}.json")
async def serve_translation_file(language: str):
    """Directly serve translation files - MUST be before static mount."""
    try:
        print(f"🔍 Translation file requested: {language}")
        
        # Validate language parameter
        if not language.isalpha() or len(language) > 5:
            print(f"❌ Invalid language code: {language}")
            raise HTTPException(status_code=400, detail="Invalid language code")
        
        translation_file = Path("web/translations") / f"{language}.json"
        print(f"🔍 Looking for file: {translation_file}")
        
        if not translation_file.exists():
            logger.warning("Translation file not found", LogCategory.API, {
                'language': language,
                'requested_file': str(translation_file)
            })
            raise HTTPException(status_code=404, detail=f"Translation file for {language} not found")
        
        # Read and return the file content
        with open(translation_file, 'r', encoding='utf-8') as f:
            translations = json.load(f)
        
        print(f"✅ Translation file served: {language} ({len(translations)} keys)")
        
        # Return with proper headers for JSON
        return JSONResponse(content=translations, headers={
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "public, max-age=300"  # Cache for 5 minutes
        })
        
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in translation file", LogCategory.API, {
            'language': language,
            'error': str(e)
        })
        raise HTTPException(status_code=500, detail=f"Invalid JSON in translation file for {language}")
    except Exception as e:
        logger.error("Failed to serve translation file", LogCategory.API, {
            'language': language,
            'error': str(e)
        })
        raise HTTPException(status_code=500, detail="Internal server error")

# Alternative API endpoint for translations (fallback)
@app.get("/api/translations/{language}")
async def get_translation_api(language: str):
    """API endpoint to serve translation files with proper error handling."""
    try:
        translation_file = Path("web/translations") / f"{language}.json"
        
        if not translation_file.exists():
            return {}  # Return empty instead of 404
        
        with open(translation_file, 'r', encoding='utf-8') as f:
            translations = json.load(f)
        
        return translations
        
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in translation file via API", LogCategory.API, {
            'language': language,
            'error': str(e)
        })
        return {}  # Return empty instead of error
    except Exception as e:
        logger.error("Failed to load translation file via API", LogCategory.API, {
            'language': language,
            'error': str(e)
        })
        return {}  # Return empty instead of error

# List available languages
@app.get("/api/languages")
async def list_available_languages():
    """List available translation languages."""
    try:
        translations_dir = Path("web/translations")
        
        if not translations_dir.exists():
            return {
                "languages": ["en"], 
                "default": "en",
                "error": "Translation directory not found"
            }
        
        available_languages = []
        language_info = {}
        
        # Language display names
        language_names = {
            'en': 'English',
            'de': 'Deutsch',
            'ru': 'Русский',
            'cs': 'Čeština',
            'cn': '中文'
        }
        
        for json_file in translations_dir.glob("*.json"):
            lang_code = json_file.stem
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    translations = json.load(f)
                    available_languages.append(lang_code)
                    language_info[lang_code] = {
                        'code': lang_code,
                        'name': language_names.get(lang_code, lang_code.upper()),
                        'keys_count': len(translations),
                        'file_size': json_file.stat().st_size,
                        'file_path': str(json_file)
                    }
            except Exception as e:
                logger.warning("Skipped invalid translation file", LogCategory.API, {
                    'file': str(json_file),
                    'error': str(e)
                })
        
        return {
            "languages": available_languages,
            "default": "en",
            "language_info": language_info,
            "translations_path": str(translations_dir)
        }
        
    except Exception as e:
        logger.error("Failed to list languages", LogCategory.API, {'error': str(e)})
        return {
            "languages": ["en"],
            "default": "en", 
            "error": str(e)
        }

# =================== STATIC FILES AND TEMPLATES (AFTER TRANSLATION ROUTES) ===================

# Static files mount - AFTER translation routes to avoid conflicts
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# Serve project documentation if available
docs_dir = Path(__file__).parent.parent / "docs"
if docs_dir.exists():
    app.mount("/documentation", StaticFiles(directory=str(docs_dir), html=True), name="documentation")

# =================== FIXED JOB STATUS WITH PROPER ASYNC INITIALIZATION ===================

class JobStatus:
    """FIXED Job status tracking with proper async initialization."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.logger = get_logger("kassia.webui.jobs")
        self.job_db = get_job_database()
        self._broadcast_queue = None
        self._broadcast_task = None
        self._initialized = False
        
        # Load existing jobs from database on startup
        self._load_jobs_from_database()
    
    async def initialize_async(self):
        """Initialize async components when event loop is available."""
        if self._initialized:
            return
            
        try:
            self._broadcast_queue = asyncio.Queue()
            # Start broadcast worker in the event loop
            self._broadcast_task = asyncio.create_task(self._broadcast_worker())
            self._initialized = True
            self.logger.info("JobStatus async components initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize async components: {e}")
    
    async def _broadcast_worker(self):
        """Background worker to handle WebSocket broadcasts."""
        self.logger.info("Broadcast worker started")
        
        while True:
            try:
                if not self._broadcast_queue:
                    await asyncio.sleep(1)
                    continue
                    
                # Wait for broadcast messages
                message = await self._broadcast_queue.get()
                
                if message is None:  # Shutdown signal
                    break
                
                await self._send_to_all_connections(message)
                
            except Exception as e:
                self.logger.error(f"Broadcast worker error: {e}")
                await asyncio.sleep(1)  # Brief pause before retrying
    
    async def _send_to_all_connections(self, message: dict):
        """Send message to all active WebSocket connections."""
        if not self.active_connections:
            return
        
        message_json = json.dumps(message, default=str)
        disconnected = []
        
        # Send to all connections
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
                self.logger.debug(f"Sent message to connection: {connection.client}")
                
            except Exception as e:
                self.logger.warning(f"Failed to send to connection {connection.client}: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)
                self.logger.info(f"Removed disconnected connection: {conn.client}")
    
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
        """Update job status with enhanced WebSocket broadcasting."""
        
        # Update in database first
        if self.job_db.update_job(job_id, kwargs):
            # Get updated job data
            job_data = self.job_db.get_job(job_id)
            
            if job_data:
                # Log status changes
                old_status = job_data.get('status')
                new_status = kwargs.get('status')
                
                if old_status != new_status and new_status:
                    self.logger.info("Job status changed", LogCategory.WEBUI, {
                        'job_id': job_id,
                        'old_status': old_status,
                        'new_status': new_status,
                        'progress': kwargs.get('progress'),
                        'current_step': kwargs.get('current_step')
                    })
                
                # Add recent logs to the broadcast
                recent_logs = self.job_db.get_job_logs(job_id, limit=5)
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
                
                # Queue broadcast message if async is initialized
                if self._initialized and self._broadcast_queue:
                    message = {
                        'type': 'job_update',
                        'job_id': job_id,
                        'data': job_data,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Add to broadcast queue (non-blocking)
                    try:
                        self._broadcast_queue.put_nowait(message)
                    except (asyncio.QueueFull, AttributeError):
                        self.logger.warning("Broadcast queue full or not initialized, dropping message")
                
        else:
            self.logger.warning("Failed to update job in database", LogCategory.WEBUI, {
                'job_id': job_id
            })
    
    def add_job_log(self, job_id: str, message: str, level: str = "INFO", 
                   component: str = "webui", category: str = "JOB"):
        """Add log entry to job with immediate broadcast."""
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
        
        # Broadcast log update immediately if async is initialized
        if self._initialized and self._broadcast_queue:
            log_message = {
                'type': 'job_log',
                'job_id': job_id,
                'log': {
                    'timestamp': timestamp,
                    'level': level,
                    'message': message,
                    'category': category,
                    'component': component
                }
            }
            
            try:
                self._broadcast_queue.put_nowait(log_message)
            except (asyncio.QueueFull, AttributeError):
                self.logger.warning("Broadcast queue full or not initialized, dropping log message")
    
    async def add_connection(self, websocket: WebSocket):
        """Add a new WebSocket connection."""
        # Ensure async components are initialized
        await self.initialize_async()
        
        await websocket.accept()
        self.active_connections.append(websocket)
        
        client_info = {
            'client_ip': websocket.client.host,
            'connection_count': len(self.active_connections)
        }
        
        self.logger.info("WebSocket connection established", LogCategory.WEBUI, client_info)
        
        # Send initial status
        await self._send_initial_status(websocket)
    
    async def _send_initial_status(self, websocket: WebSocket):
        """Send initial system status to new connection."""
        try:
            all_jobs = self.get_all_jobs()
            
            initial_message = {
                "type": "system_status",
                "timestamp": datetime.now().isoformat(),
                "active_connections": len(self.active_connections),
                "active_jobs": len([j for j in all_jobs if j['status'] == 'running']),
                "total_jobs": len(all_jobs),
                "status": "connected"
            }
            
            await websocket.send_text(json.dumps(initial_message, default=str))
            
        except Exception as e:
            self.logger.error(f"Failed to send initial status: {e}")
    
    def remove_connection(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
            self.logger.info("WebSocket connection closed", LogCategory.WEBUI, {
                'client_ip': websocket.client.host,
                'remaining_connections': len(self.active_connections)
            })
    
    async def shutdown_broadcast_worker(self):
        """Shutdown the broadcast worker."""
        if self._broadcast_task and not self._broadcast_task.done():
            if self._broadcast_queue:
                await self._broadcast_queue.put(None)  # Shutdown signal
            await self._broadcast_task
    
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

# =================== PYDANTIC MODELS ===================

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

# =================== TEMPLATE HELPER FUNCTIONS ===================

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

# =================== API ROUTES WITH DATABASE INTEGRATION ===================

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
        
        # Get SBI with proper path resolution
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
    
    return FileResponse(
        path=str(log_file),
        filename=f"kassia_job_{job_id}_{log_type}.log",
        media_type="text/plain"
    )

@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str) -> Dict[str, str]:
    """Cancel/delete a job in database."""
    if not job_status.cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found or could not be cancelled")
    
    return {"status": "cancelled"}

@app.delete("/api/jobs/{job_id}/delete")
async def delete_job(job_id: str) -> Dict[str, str]:
    """Permanently delete a job from database."""
    if not job_status.delete_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found or could not be deleted")
    
    return {"status": "deleted"}

# =================== ADMIN API ROUTES ===================

@app.get("/api/admin/database/info")
async def get_database_info() -> Dict[str, Any]:
    """Get database information and statistics."""
    try:
        # Get database info
        db_info = job_db.get_database_info()
        
        # Add additional system info
        all_jobs = job_status.get_all_jobs()
        system_info = {
            'job_count': len(all_jobs),
            'active_connections': len(job_status.active_connections),
            'uptime': datetime.now().isoformat()
        }
        
        # Merge and ensure all required fields
        result = {
            'database_path': str(job_db.db_path),
            'database_size_bytes': 0,
            'database_size_mb': 0,
            'job_count': len(all_jobs),
            'log_count': 0,
            'event_count': 0,
            'statistics_count': 0,
            **db_info,  # Override with actual values if available
            **system_info
        }
        
        # Calculate database size if file exists
        if job_db.db_path.exists():
            size_bytes = job_db.db_path.stat().st_size
            result['database_size_bytes'] = size_bytes
            result['database_size_mb'] = round(size_bytes / (1024 * 1024), 2)
        
        return result
        
    except Exception as e:
        logger.error("Failed to get database info", LogCategory.API, {'error': str(e)})
        # Return default values instead of error to prevent UI crash
        return {
            'database_path': str(job_db.db_path) if job_db.db_path else 'Unknown',
            'database_size_bytes': 0,
            'database_size_mb': 0,
            'job_count': 0,
            'log_count': 0,
            'event_count': 0,
            'statistics_count': 0
        }

@app.get("/api/admin/statistics")
async def get_statistics(days: int = 30) -> List[Dict[str, Any]]:
    """Get job statistics for the last N days."""
    try:
        stats = job_db.get_statistics(days)
        
        # If no stats, generate some dummy data based on actual jobs
        if not stats:
            all_jobs = job_status.get_all_jobs()
            today = datetime.now().date()
            
            # Group jobs by date
            job_dates = {}
            for job in all_jobs:
                try:
                    job_date = datetime.fromisoformat(job['created_at']).date()
                    date_str = job_date.isoformat()
                    
                    if date_str not in job_dates:
                        job_dates[date_str] = {
                            'date': date_str,
                            'total_jobs': 0,
                            'completed_jobs': 0,
                            'failed_jobs': 0,
                            'avg_duration_seconds': None
                        }
                    
                    job_dates[date_str]['total_jobs'] += 1
                    if job['status'] == 'completed':
                        job_dates[date_str]['completed_jobs'] += 1
                    elif job['status'] in ['failed', 'cancelled']:
                        job_dates[date_str]['failed_jobs'] += 1
                        
                except Exception:
                    continue
            
            stats = list(job_dates.values())
            stats.sort(key=lambda x: x['date'], reverse=True)
        
        return stats
        
    except Exception as e:
        logger.error("Failed to get statistics", LogCategory.API, {'error': str(e)})
        return []

@app.post("/api/admin/maintenance/cleanup")
async def cleanup_old_data(days: int = 90) -> Dict[str, Any]:
    """Cleanup old job data from database with proper deletion."""
    logger.log_operation_start("database_cleanup")
    start_time = time.time()
    
    try:
        # Validate days parameter
        if days < 1:
            raise HTTPException(status_code=400, detail="Days must be at least 1")
        
        if days > 3650:  # 10 years max
            raise HTTPException(status_code=400, detail="Days cannot exceed 3650 (10 years)")
        
        # Get database info before cleanup
        db_info_before = job_db.get_database_info()
        
        # Perform cleanup
        deleted_counts = job_db.cleanup_old_data(days)
        
        # Get database info after cleanup
        db_info_after = job_db.get_database_info()
        
        # Calculate space saved
        space_saved_bytes = db_info_before.get('database_size_bytes', 0) - db_info_after.get('database_size_bytes', 0)
        space_saved_mb = round(space_saved_bytes / (1024 * 1024), 2)
        
        duration = time.time() - start_time
        
        result = {
            "status": "completed",
            "days_kept": days,
            "cutoff_date": (datetime.now() - timedelta(days=days)).isoformat(),
            "deleted_counts": deleted_counts,
            "database_before": {
                "size_mb": db_info_before.get('database_size_mb', 0),
                "job_count": db_info_before.get('job_count', 0),
                "log_count": db_info_before.get('log_count', 0)
            },
            "database_after": {
                "size_mb": db_info_after.get('database_size_mb', 0),
                "job_count": db_info_after.get('job_count', 0),
                "log_count": db_info_after.get('log_count', 0)
            },
            "space_saved": {
                "bytes": space_saved_bytes,
                "mb": space_saved_mb
            },
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.now().isoformat()
        }
        
        logger.log_operation_success("database_cleanup", duration, {
            'deleted_counts': deleted_counts,
            'space_saved_mb': space_saved_mb
        })
        
        # Update statistics after cleanup
        try:
            job_db.update_daily_statistics()
        except Exception as e:
            logger.warning("Failed to update statistics after cleanup", LogCategory.DATABASE, {'error': str(e)})
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Database cleanup failed: {str(e)}"
        
        logger.log_operation_failure("database_cleanup", error_msg, duration)
        
        return {
            "status": "failed",
            "error": error_msg,
            "days_requested": days,
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.now().isoformat(),
            "suggestion": "Check database permissions and disk space"
        }

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

# =================== ENHANCED WEBSOCKET WITH PROPER INITIALIZATION ===================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Enhanced WebSocket endpoint for live updates with robust error handling."""
    
    client_ip = websocket.client.host
    connection_id = f"{client_ip}:{websocket.client.port}"
    
    try:
        # Add connection to job status manager (this will initialize async components)
        await job_status.add_connection(websocket)
        
        # Send periodic heartbeats and handle incoming messages
        heartbeat_task = asyncio.create_task(send_heartbeats(websocket))
        
        try:
            while True:
                # Wait for incoming messages (with timeout)
                try:
                    message = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                    
                    # Handle incoming message
                    try:
                        data = json.loads(message)
                        await handle_websocket_message(websocket, data)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from {connection_id}: {message}")
                        
                except asyncio.TimeoutError:
                    # Timeout is normal, continue loop
                    continue
                except WebSocketDisconnect:
                    # Client disconnected
                    break
                    
        except Exception as e:
            logger.error(f"WebSocket error for {connection_id}: {e}")
            
        finally:
            # Cancel heartbeat task
            if not heartbeat_task.done():
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
    
    except Exception as e:
        logger.error(f"WebSocket connection error for {connection_id}: {e}")
    
    finally:
        # Always remove connection
        job_status.remove_connection(websocket)

async def send_heartbeats(websocket: WebSocket):
    """Send periodic heartbeat messages to keep connection alive."""
    try:
        while True:
            await asyncio.sleep(30)  # Send heartbeat every 30 seconds
            
            # Get current system status
            all_jobs = job_status.get_all_jobs()
            
            heartbeat = {
                "type": "heartbeat",
                "timestamp": datetime.now().isoformat(),
                "active_connections": len(job_status.active_connections),
                "active_jobs": len([j for j in all_jobs if j['status'] == 'running']),
                "total_jobs": len(all_jobs),
                "server_time": datetime.now().isoformat()
            }
            
            await websocket.send_text(json.dumps(heartbeat, default=str))
            
    except WebSocketDisconnect:
        # Client disconnected, stop heartbeats
        pass
    except Exception as e:
        logger.error(f"Heartbeat error: {e}")

async def handle_websocket_message(websocket: WebSocket, data: dict):
    """Handle incoming WebSocket messages from clients."""
    message_type = data.get('type')
    
    if message_type == 'ping':
        # Respond to ping with pong
        await websocket.send_text(json.dumps({
            'type': 'pong',
            'timestamp': datetime.now().isoformat()
        }))
        
    elif message_type == 'subscribe_job':
        # Subscribe to specific job updates
        job_id = data.get('job_id')
        if job_id:
            job_data = job_status.get_job(job_id)
            if job_data:
                await websocket.send_text(json.dumps({
                    'type': 'job_update',
                    'job_id': job_id,
                    'data': job_data
                }, default=str))
    
    elif message_type == 'request_status':
        # Send current system status
        await job_status._send_initial_status(websocket)
    
    else:
        logger.debug(f"Unknown WebSocket message type: {message_type}")

# =================== ENHANCED BUILD JOB EXECUTION ===================

async def execute_cli_wim_workflow_real(job_id: str, kassia_config, assets_summary: dict, 
                                       skip_drivers: bool, skip_updates: bool, debug: bool) -> Optional[Path]:
    """FIXED: Execute REAL WIM workflow instead of simulation."""
    
    logger.set_context(job_id=job_id)
    logger.log_operation_start("webui_real_wim_workflow")
    workflow_start = time.time()
    
    try:
        if not assets_summary['sbi']:
            error_msg = "Cannot execute WIM workflow without SBI"
            logger.error(error_msg, LogCategory.WIM)
            
            job_status.update_job(job_id, 
                status="failed",
                error=error_msg,
                completed_at=datetime.now().isoformat()
            )
            
            return None
        
        sbi_asset = assets_summary['sbi']
        build_config = kassia_config.build
        
        # Update job to running
        job_status.update_job(job_id,
            status="running",
            started_at=datetime.now().isoformat(),
            current_step="Starting REAL WIM workflow",
            step_number=1,
            progress=5
        )
        
        logger.info("Starting REAL WebUI WIM workflow", LogCategory.WORKFLOW, {
            'sbi_name': sbi_asset.name,
            'device': kassia_config.device.deviceId,
            'os_id': kassia_config.selectedOsId,
            'skip_drivers': skip_drivers,
            'skip_updates': skip_updates
        })
        
        # FIXED: Initialize REAL WIM Handler and Workflow
        wim_handler = WimHandler()
        workflow = WimWorkflow(wim_handler)
        
        logger.info("REAL WIM workflow components initialized", LogCategory.WIM)
        
        # Step 1: REAL WIM Preparation
        job_status.update_job(job_id,
            current_step="Preparing WIM for modification",
            step_number=2,
            progress=15
        )
        
        logger.info("Starting REAL WIM preparation", LogCategory.WIM)
        step_start = time.time()
        
        temp_dir = Path(build_config.tempPath)
        temp_wim = await workflow.prepare_wim_for_modification(sbi_asset.path, temp_dir)
        
        step_duration = time.time() - step_start
        logger.info("REAL WIM preparation completed", LogCategory.WIM, {
            'temp_wim': str(temp_wim),
            'duration': step_duration
        })
        
        # Step 2: REAL WIM Mount
        job_status.update_job(job_id,
            current_step="Mounting WIM for modification",
            step_number=3,
            progress=25
        )
        
        logger.info("Starting REAL WIM mount", LogCategory.WIM)
        step_start = time.time()
        
        mount_point = Path(build_config.mountPoint)
        mount_info = await workflow.mount_wim_for_modification(temp_wim, mount_point)
        
        step_duration = time.time() - step_start
        logger.info("REAL WIM mount completed", LogCategory.WIM, {
            'mount_point': str(mount_point),
            'duration': step_duration,
            'read_write': mount_info.read_write
        })
        
        # Verify mount
        windows_dir = mount_point / "Windows"
        if windows_dir.exists():
            logger.info("REAL mount verification successful", LogCategory.WIM)
        else:
            error_msg = "REAL mount verification failed: No Windows directory"
            logger.error(error_msg, LogCategory.WIM)
            job_status.update_job(job_id,
                status="failed",
                error=error_msg,
                completed_at=datetime.now().isoformat()
            )
            raise Exception(error_msg)
        
        # Step 3: REAL Driver Integration
        if not skip_drivers and assets_summary['drivers']:
            driver_count = len(assets_summary['drivers'])
            job_status.update_job(job_id,
                current_step=f"Integrating {driver_count} drivers",
                step_number=4,
                progress=40
            )
            
            logger.info("Starting REAL driver integration", LogCategory.DRIVER, {
                'driver_count': driver_count
            })
            step_start = time.time()
            
            # FIXED: Initialize REAL driver integration components
            driver_integrator = DriverIntegrator()
            driver_manager = DriverIntegrationManager(driver_integrator)
            
            # Execute REAL driver integration
            integration_result = await driver_manager.integrate_drivers_for_device(
                assets_summary['drivers'],
                mount_point,
                Path(kassia_config.build.yunonaPath),
                kassia_config.device.deviceId,
                kassia_config.selectedOsId
            )
            
            step_duration = time.time() - step_start
            
            if integration_result['success']:
                successful = integration_result['successful_count']
                logger.info("REAL driver integration completed", LogCategory.DRIVER, {
                    'duration': step_duration,
                    'successful_count': successful,
                    'failed_count': integration_result['failed_count'],
                    'stats': integration_result['stats']
                })
                
                job_status.update_job(job_id,
                    current_step=f"Driver integration completed ({successful}/{driver_count})",
                    step_number=4,
                    progress=50
                )
                
            else:
                failed = integration_result['failed_count']
                error_msg = f"Driver integration failed ({failed}/{driver_count})"
                logger.error(error_msg, LogCategory.DRIVER, {
                    'duration': step_duration,
                    'failed_count': failed,
                    'error_message': integration_result['message']
                })
                
                # Continue with warning (don't fail completely)
                job_status.update_job(job_id,
                    current_step=f"Driver integration failed ({failed}/{driver_count}) - continuing",
                    step_number=4,
                    progress=50
                )
                
        elif skip_drivers:
            job_status.update_job(job_id,
                current_step="Driver integration skipped",
                step_number=4,
                progress=50
            )
            logger.info("REAL driver integration skipped by user", LogCategory.DRIVER)
        else:
            job_status.update_job(job_id,
                current_step="No drivers found for integration",
                step_number=4,
                progress=50
            )
            logger.warning("No drivers found for REAL integration", LogCategory.DRIVER)
        
        # Step 4: REAL Update Integration
        if not skip_updates and assets_summary['updates']:
            update_count = len(assets_summary['updates'])
            job_status.update_job(job_id,
                current_step=f"Integrating {update_count} updates",
                step_number=5,
                progress=65
            )
            
            logger.info("Starting REAL update integration", LogCategory.UPDATE, {
                'update_count': update_count
            })
            step_start = time.time()
            
            # FIXED: Initialize REAL update integration components
            update_integrator = UpdateIntegrator()
            update_manager = UpdateIntegrationManager(update_integrator)
            
            # Execute REAL update integration
            integration_result = await update_manager.integrate_updates_for_os(
                assets_summary['updates'],
                mount_point,
                Path(kassia_config.build.yunonaPath),
                kassia_config.selectedOsId
            )
            
            step_duration = time.time() - step_start
            
            if integration_result['success']:
                successful = integration_result['successful_count']
                logger.info("REAL update integration completed", LogCategory.UPDATE, {
                    'duration': step_duration,
                    'successful_count': successful,
                    'failed_count': integration_result['failed_count'],
                    'stats': integration_result['stats']
                })
                
                job_status.update_job(job_id,
                    current_step=f"Update integration completed ({successful}/{update_count})",
                    step_number=5,
                    progress=75
                )
                
            else:
                failed = integration_result['failed_count']
                error_msg = f"Update integration failed ({failed}/{update_count})"
                logger.error(error_msg, LogCategory.UPDATE, {
                    'duration': step_duration,
                    'failed_count': failed,
                    'error_message': integration_result['message']
                })
                
                # Continue with warning (don't fail completely)
                job_status.update_job(job_id,
                    current_step=f"Update integration failed ({failed}/{update_count}) - continuing",
                    step_number=5,
                    progress=75
                )
                
        elif skip_updates:
            job_status.update_job(job_id,
                current_step="Update integration skipped",
                step_number=5,
                progress=75
            )
            logger.info("REAL update integration skipped by user", LogCategory.UPDATE)
        else:
            job_status.update_job(job_id,
                current_step="No updates found for integration",
                step_number=5,
                progress=75
            )
            logger.warning("No updates found for REAL integration", LogCategory.UPDATE)
        
        # Step 5: REAL WIM Export
        job_status.update_job(job_id,
            current_step="Exporting final WIM",
            step_number=6,
            progress=85
        )
        
        logger.info("Starting REAL WIM export", LogCategory.WIM)
        step_start = time.time()
        
        export_dir = Path(build_config.exportPath)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_name = f"{kassia_config.selectedOsId}_{kassia_config.device.deviceId}_{timestamp}.wim"
        export_path = export_dir / export_name
        
        # REAL WIM Export
        final_wim = await workflow.finalize_and_export_wim(
            mount_point, 
            export_path, 
            export_name=f"Kassia {kassia_config.device.deviceId} OS{kassia_config.selectedOsId}"
        )
        
        step_duration = time.time() - step_start
        export_size = final_wim.stat().st_size
        export_size_mb = export_size / (1024 * 1024)
        
        logger.info("REAL WIM export completed", LogCategory.WIM, {
            'duration': step_duration,
            'final_wim': str(final_wim),
            'size_mb': export_size_mb,
            'export_name': export_name
        })
        
        # Step 6: REAL Cleanup
        job_status.update_job(job_id,
            current_step="Cleanup temporary files",
            step_number=7,
            progress=95
        )
        
        logger.info("Starting REAL cleanup", LogCategory.SYSTEM)
        step_start = time.time()
        
        await workflow.cleanup_workflow(keep_export=True)
        
        step_duration = time.time() - step_start
        logger.info("REAL cleanup completed", LogCategory.SYSTEM, {
            'duration': step_duration
        })
        
        # Complete job with REAL results
        workflow_duration = time.time() - workflow_start
        
        final_results = {
            'final_wim_path': str(final_wim),
            'final_wim_size_mb': export_size_mb,
            'total_duration_seconds': workflow_duration,
            'export_name': export_name,
            'device': kassia_config.device.deviceId,
            'os_id': kassia_config.selectedOsId,
            'drivers_integrated': len(assets_summary['drivers']) if not skip_drivers else 0,
            'updates_integrated': len(assets_summary['updates']) if not skip_updates else 0,
            'workflow_type': 'REAL_WIM_PROCESSING'
        }
        
        job_status.update_job(job_id,
            status="completed",
            current_step="REAL WIM processing completed",
            step_number=8,
            progress=100,
            completed_at=datetime.now().isoformat(),
            results=final_results
        )
        
        logger.log_operation_success("webui_real_wim_workflow", workflow_duration, {
            'final_wim': str(final_wim),
            'final_size_mb': export_size_mb,
            'device': kassia_config.device.deviceId,
            'os_id': kassia_config.selectedOsId,
            'workflow_type': 'REAL'
        })
        
        # Finalize job logging
        finalize_job_logging(job_id, "completed")
        
        return final_wim
        
    except DismError as e:
        workflow_duration = time.time() - workflow_start
        error_msg = f"DISM Error in REAL workflow: {str(e)}"
        
        logger.log_operation_failure("webui_real_wim_workflow", error_msg, workflow_duration, {
            'error_type': 'DismError'
        })
        
        # Update job with error
        job_status.update_job(job_id,
            status="failed",
            error=error_msg,
            completed_at=datetime.now().isoformat()
        )
        
        if debug:
            import traceback
            traceback.print_exc()
        
        # Emergency cleanup
        try:
            await workflow.cleanup_workflow(keep_export=False)
            logger.info("Emergency cleanup completed", LogCategory.SYSTEM)
        except Exception as cleanup_error:
            logger.error("Emergency cleanup failed", LogCategory.SYSTEM, {
                'cleanup_error': str(cleanup_error)
            })
        
        # Finalize job logging with error
        finalize_job_logging(job_id, "failed", error_msg)
        
        return None
        
    except Exception as e:
        workflow_duration = time.time() - workflow_start
        error_msg = f"Unexpected error in REAL workflow: {str(e)}"
        
        logger.log_operation_failure("webui_real_wim_workflow", error_msg, workflow_duration, {
            'error_type': type(e).__name__
        })
        
        # Update job with error
        job_status.update_job(job_id,
            status="failed",
            error=error_msg,
            completed_at=datetime.now().isoformat()
        )
        
        if debug:
            import traceback
            traceback.print_exc()
        
        # Finalize job logging with error
        finalize_job_logging(job_id, "failed", error_msg)
        
        return None
    finally:
        logger.clear_context()


# FIXED: Execute REAL build job instead of simulation
async def execute_build_job_with_logging(job_id: str, device: str, os_id: int, 
                                       skip_drivers: bool, skip_updates: bool, skip_validation: bool):
    """FIXED: Execute REAL build job instead of simulation."""
    
    # Set up job-specific logger context
    job_logger = get_logger("kassia.webui.build")
    
    # Create job context for enhanced logging
    with job_logger.create_job_context(job_id):
        job_logger.log_operation_start("real_build_job")
        job_start_time = time.time()
        
        try:
            # Step 1: Starting
            job_status.update_job(
                job_id,
                status="running",
                started_at=datetime.now().isoformat(),
                current_step="Loading configuration",
                step_number=1,
                progress=10
            )
            
            job_status.add_job_log(job_id, "REAL build job started", "INFO")
            await asyncio.sleep(0.5)  # Allow WebSocket update
            
            # Step 2: Load configuration
            job_logger.info("Loading configuration", LogCategory.CONFIG)
            kassia_config = ConfigLoader.create_kassia_config(device, os_id)
            
            job_status.update_job(
                job_id,
                current_step="Discovering assets",
                step_number=2,
                progress=20
            )
            
            job_status.add_job_log(job_id, "Configuration loaded successfully", "INFO")
            await asyncio.sleep(0.5)
            
            # Step 3: Asset Discovery (REAL)
            job_logger.info("Starting REAL asset discovery", LogCategory.ASSET)
            
            # Create asset provider with proper config integration
            assets_path = Path("assets")
            
            build_config_dict = {
                'driverRoot': kassia_config.build.driverRoot,
                'updateRoot': kassia_config.build.updateRoot,
                'sbiRoot': kassia_config.build.sbiRoot,
                'yunonaPath': kassia_config.build.yunonaPath,
                'osWimMap': kassia_config.build.osWimMap
            }
            
            provider = LocalAssetProvider(assets_path, build_config=build_config_dict)
            
            assets_summary = {
                'sbi': None,
                'drivers': [],
                'updates': [],
                'yunona_scripts': []
            }
            
            # REAL Asset Discovery
            job_status.add_job_log(job_id, "Discovering SBI assets", "INFO")
            sbi_asset = await provider.get_sbi(kassia_config.selectedOsId)
            if sbi_asset:
                assets_summary['sbi'] = sbi_asset
                job_status.add_job_log(job_id, f"SBI found: {sbi_asset.name}", "INFO")
            else:
                job_status.add_job_log(job_id, f"No SBI found for OS {kassia_config.selectedOsId}", "WARNING")
            
            job_status.add_job_log(job_id, "Discovering driver assets", "INFO")
            drivers = await provider.get_drivers(device, kassia_config.selectedOsId)
            assets_summary['drivers'] = drivers
            job_status.add_job_log(job_id, f"Found {len(drivers)} compatible drivers", "INFO")
            
            job_status.add_job_log(job_id, "Discovering update assets", "INFO")
            updates = await provider.get_updates(kassia_config.selectedOsId)
            assets_summary['updates'] = updates
            job_status.add_job_log(job_id, f"Found {len(updates)} compatible updates", "INFO")
            
            job_status.add_job_log(job_id, "Discovering Yunona scripts", "INFO")
            scripts = await provider.get_yunona_scripts()
            assets_summary['yunona_scripts'] = scripts
            job_status.add_job_log(job_id, f"Found {len(scripts)} Yunona scripts", "INFO")
            
            job_status.update_job(
                job_id,
                current_step="Asset discovery completed",
                step_number=3,
                progress=30
            )
            
            # Step 4: REAL WIM Workflow Execution
            job_status.add_job_log(job_id, "Starting REAL WIM workflow", "INFO")
            
            # FIXED: Call the REAL WIM workflow function
            final_wim = await execute_cli_wim_workflow_real(
                job_id, kassia_config, assets_summary, 
                skip_drivers, skip_updates, False  # debug=False for WebUI
            )
            
            if final_wim:
                job_status.add_job_log(job_id, f"REAL WIM processing completed: {final_wim}", "INFO")
                job_logger.info("REAL build job completed successfully", LogCategory.WEBUI, {
                    'job_id': job_id,
                    'final_wim': str(final_wim),
                    'device': device,
                    'os_id': os_id
                })
            else:
                job_status.add_job_log(job_id, "REAL WIM processing failed", "ERROR")
                job_logger.error("REAL build job failed", LogCategory.WEBUI, {
                    'job_id': job_id,
                    'device': device,
                    'os_id': os_id
                })
            
            # Update daily statistics
            job_db.update_daily_statistics()
            
        except Exception as e:
            job_duration = time.time() - job_start_time
            error_msg = str(e)
            
            job_status.update_job(
                job_id,
                status="failed",
                error=error_msg,
                completed_at=datetime.now().isoformat()
            )
            
            job_status.add_job_log(job_id, f"REAL build failed: {error_msg}", "ERROR")
            
            # Finalize job logging with error
            finalize_job_logging(job_id, "failed", error_msg)
            
            # Update daily statistics
            job_db.update_daily_statistics()
            
            # Re-raise to be handled by job context
            raise


# FIXED: Helper functions for directory initialization
def initialize_directories(build_config) -> None:
    """Initialize required directories with logging."""
    logger = get_logger("kassia.webui.system")
    logger.debug("Initializing directories for WebUI job", LogCategory.SYSTEM)
    
    directories = [
        build_config.tempPath,
        build_config.mountPoint,
        build_config.exportPath,
        "runtime/logs",
        "runtime/data"
    ]
    
    created_dirs = []
    for directory in directories:
        dir_path = Path(directory)
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            created_dirs.append(str(dir_path))
        except Exception as e:
            logger.error("Failed to create directory", LogCategory.SYSTEM, {
                'directory': str(dir_path),
                'error': str(e)
            })
            raise Exception(f"Failed to create directory {dir_path}: {e}")
    
    logger.info("Directories initialized for WebUI job", LogCategory.SYSTEM, {
        'directories': created_dirs
    })


# =================== HEALTH CHECK AND STARTUP/SHUTDOWN ===================

@app.get("/api/health")
async def health_check():
    """Health check endpoint with logging."""
    logger.debug("Health check requested", LogCategory.API)
    return {
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "database": "enabled",
        "websocket_connections": len(job_status.active_connections)
    }

@app.on_event("startup")
async def startup_event():
    """Enhanced startup with proper async initialization."""
    # Initialize async components for job status
    await job_status.initialize_async()
    
    logger.info("Kassia WebUI started successfully", LogCategory.WEBUI, {
        'startup_complete': True,
        'endpoints_count': len(app.routes),
        'database_path': str(job_db.db_path),
        'database_enabled': True,
        'websocket_system': 'enhanced',
        'async_initialized': job_status._initialized
    })
    
    # Update daily statistics on startup
    try:
        job_db.update_daily_statistics()
        logger.info("Daily statistics updated on startup", LogCategory.WEBUI)
    except Exception as e:
        logger.error("Failed to update statistics on startup", LogCategory.WEBUI, {'error': str(e)})

@app.on_event("shutdown")
async def shutdown_event():
    """Enhanced shutdown with WebSocket cleanup."""
    all_jobs = job_status.get_all_jobs()
    active_jobs = [j for j in all_jobs if j['status'] == 'running']
    
    # Mark any running jobs as interrupted
    for job in active_jobs:
        job_status.update_job(job['id'], 
            status="failed",
            error="Application shutdown during execution",
            completed_at=datetime.now().isoformat()
        )
    
    # Shutdown broadcast worker
    await job_status.shutdown_broadcast_worker()
    
    logger.info("Kassia WebUI shutting down", LogCategory.WEBUI, {
        'active_connections': len(job_status.active_connections),
        'interrupted_jobs': len(active_jobs),
        'total_jobs': len(all_jobs)
    })


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Kassia WebUI server with REAL WIM processing", LogCategory.WEBUI)
    
    print("🌐 Starting Kassia Web Interface with REAL WIM Processing...")
    print("=" * 70)
    print("🚀 FastAPI server starting...")
    print("📊 Dashboard: http://localhost:8000")
    print("📋 API Docs: http://localhost:8000/docs")
    print("📜 Logs: runtime/logs/")
    print("🗄️ Database: runtime/data/kassia_webui_jobs.db")
    print("⚙️  REAL WIM Processing: ENABLED")
    print("🔧 DISM Integration: ACTIVE")
    print("🔗 WebSocket Live Updates: ws://localhost:8000/ws")
    print("✅ FIXED: Real WIM workflows instead of simulation")
    print("=" * 70)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)