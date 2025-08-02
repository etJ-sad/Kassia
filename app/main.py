# app/main.py - CLI mit Datenbank-Integration und verbessertem Logging

"""
Kassia Python - Main CLI Entry Point (Mit Database Integration und Advanced Logging)
"""

import click
import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime
import time
import uuid
from typing import Optional, List

# Import our logging system
from app.utils.logging import (
    get_logger, configure_logging, LogLevel, LogCategory, create_job_logger, finalize_job_logging
)

# Import database system
from app.utils.job_database import get_job_database, init_job_database

# Import existing modules
from app.models.config import ConfigLoader, ValidationResult
from app.core.asset_providers import LocalAssetProvider
from app.core.wim_handler import WimHandler, WimWorkflow, DismError
from app.core.driver_integration import DriverIntegrator, DriverIntegrationManager
from app.core.update_integration import UpdateIntegrator, UpdateIntegrationManager

# Version info
__version__ = "2.0.0"

# Initialize logger
logger = get_logger("kassia.cli")

def setup_logging_and_database(debug: bool = False, log_file: bool = True, db_path: Optional[Path] = None):
    """Setup logging configuration and initialize database."""
    level = LogLevel.DEBUG if debug else LogLevel.INFO
    
    configure_logging(
        level=level,
        log_dir=Path("runtime/logs"),
        enable_console=True,
        enable_file=log_file,
        enable_webui=False
    )
    
    # Initialize database
    if db_path is None:
        db_path = Path("runtime/data/kassia_cli_jobs.db")
    
    job_db = init_job_database(db_path)
    
    logger.info("Logging and Database system initialized", LogCategory.SYSTEM, {
        'version': __version__,
        'debug_mode': debug,
        'log_level': level.name,
        'database_path': str(db_path)
    })
    
    return job_db

def create_cli_job(job_db, device: str, os_id: int, **kwargs) -> str:
    """Create a CLI job entry in database."""
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
        'user_id': 'cli_user',
        'created_by': 'cli',
        'skip_drivers': kwargs.get('skip_drivers', False),
        'skip_updates': kwargs.get('skip_updates', False),
        'skip_validation': kwargs.get('skip_validation', False)
    }
    
    if job_db.create_job(job_data):
        logger.info("CLI job created in database", LogCategory.CLI, {
            'job_id': job_id,
            'device': device,
            'os_id': os_id
        })
        
        # Create dedicated job logger
        create_job_logger(job_id)
        
        return job_id
    else:
        raise Exception("Failed to create job in database")

def update_cli_job(job_db, job_id: str, **kwargs):
    """Update CLI job in database."""
    if job_db.update_job(job_id, kwargs):
        # Log to job-specific file if available
        if 'status' in kwargs:
            logger.info("CLI job status updated", LogCategory.CLI, {
                'job_id': job_id,
                'new_status': kwargs['status'],
                'progress': kwargs.get('progress')
            })
        
        # Also add to job logs table
        if 'current_step' in kwargs:
            job_db.add_job_log(
                job_id=job_id,
                timestamp=datetime.now().isoformat(),
                level='INFO',
                message=f"Step: {kwargs['current_step']}",
                component='cli',
                category='CLI'
            )
    else:
        logger.warning("Failed to update CLI job in database", LogCategory.CLI, {
            'job_id': job_id
        })

def check_prerequisites() -> ValidationResult:
    """Check system prerequisites with detailed logging."""
    logger.log_operation_start("prerequisites_check")
    start_time = time.time()
    
    result = ValidationResult(isValid=True)
    
    try:
        # Check if we're on Windows
        if os.name != 'nt':
            msg = "This tool is designed for Windows systems"
            result.add_warning(msg)
            logger.warning(msg, LogCategory.SYSTEM, {'os_name': os.name})
        
        # Check if running as admin
        try:
            is_admin = os.access(os.sep, os.W_OK)
            if not is_admin:
                msg = "Administrator privileges required for WIM operations"
                result.add_error(msg)
                logger.error(msg, LogCategory.SYSTEM, {'is_admin': False})
            else:
                logger.info("Administrator privileges confirmed", LogCategory.SYSTEM)
        except Exception as e:
            msg = "Could not check administrator privileges"
            result.add_warning(msg)
            logger.warning(msg, LogCategory.SYSTEM, {'error': str(e)})
        
        # Check if DISM is available
        try:
            wim_handler = WimHandler()
            logger.info("DISM validation successful", LogCategory.WIM)
        except DismError as e:
            msg = f"DISM not available: {e}"
            result.add_error(msg)
            logger.error(msg, LogCategory.WIM, {'dism_error': str(e)})
        except Exception as e:
            msg = "DISM tool verification failed"
            result.add_error(msg)
            logger.error(msg, LogCategory.WIM, {'error': str(e)})
        
        # Check Python version
        if sys.version_info < (3, 11):
            msg = f"Python 3.11+ recommended. Current: {sys.version}"
            result.add_warning(msg)
            logger.warning(msg, LogCategory.SYSTEM, {
                'python_version': sys.version,
                'recommended_version': '3.11+'
            })
        
        duration = time.time() - start_time
        if result.has_errors():
            logger.log_operation_failure("prerequisites_check", "Prerequisites validation failed", duration, {
                'errors': result.errors,
                'warnings': result.warnings
            })
        else:
            logger.log_operation_success("prerequisites_check", duration, {
                'warnings': len(result.warnings)
            })
        
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        logger.log_operation_failure("prerequisites_check", str(e), duration)
        result.add_error(f"Prerequisites check failed: {e}")
        return result

async def discover_and_display_assets(kassia_config, device_name: str) -> dict:
    """Discover and display available assets with detailed logging."""
    logger.set_context(device=device_name, os_id=kassia_config.selectedOsId)
    logger.log_operation_start("asset_discovery")
    start_time = time.time()
    
    try:
        assets_path = Path("assets")
        
        # Create asset provider with proper config integration
        build_config_dict = {
            'driverRoot': kassia_config.build.driverRoot,
            'updateRoot': kassia_config.build.updateRoot,
            'sbiRoot': kassia_config.build.sbiRoot,
            'yunonaPath': kassia_config.build.yunonaPath,
            'osWimMap': kassia_config.build.osWimMap
        }
        
        provider = LocalAssetProvider(assets_path, build_config=build_config_dict)
        
        click.echo("\n🔍 Discovering assets...")
        logger.info("Starting asset discovery", LogCategory.ASSET, {
            'assets_path': str(assets_path),
            'config': build_config_dict
        })
        
        assets_summary = {
            'sbi': None,
            'drivers': [],
            'updates': [],
            'yunona_scripts': []
        }
        
        # Discover SBI
        logger.debug("Discovering SBI assets", LogCategory.ASSET)
        sbi_asset = await provider.get_sbi(kassia_config.selectedOsId)
        if sbi_asset:
            size_mb = sbi_asset.size / (1024 * 1024) if sbi_asset.size else 0
            click.echo(f"📀 SBI Found: {sbi_asset.name} ({size_mb:.1f} MB)")
            logger.info("SBI asset found", LogCategory.ASSET, {
                'name': sbi_asset.name,
                'path': str(sbi_asset.path),
                'size_mb': size_mb,
                'source': sbi_asset.metadata.get('source', 'unknown')
            })
            assets_summary['sbi'] = sbi_asset
            
            # Validate SBI with WIM Handler
            try:
                wim_handler = WimHandler()
                wim_info = await wim_handler.get_wim_info(sbi_asset.path)
                click.echo(f"   ✅ WIM validated: {wim_info.name}")
                logger.info("SBI WIM validation successful", LogCategory.WIM, {
                    'wim_name': wim_info.name,
                    'architecture': wim_info.architecture,
                    'index': wim_info.index
                })
            except DismError as e:
                click.echo(f"   ❌ WIM validation failed: {e}")
                logger.error("SBI WIM validation failed", LogCategory.WIM, {
                    'error': str(e),
                    'wim_path': str(sbi_asset.path)
                })
        else:
            click.echo(f"❌ No SBI found for OS ID {kassia_config.selectedOsId}")
            logger.warning("No SBI found", LogCategory.ASSET, {
                'os_id': kassia_config.selectedOsId,
                'expected_locations': {
                    'config_mapping': kassia_config.build.osWimMap.get(str(kassia_config.selectedOsId)),
                    'sbi_directory': kassia_config.build.sbiRoot
                }
            })
        
        # Discover drivers
        logger.debug("Discovering driver assets", LogCategory.DRIVER)
        drivers = await provider.get_drivers(device_name, kassia_config.selectedOsId)
        assets_summary['drivers'] = drivers
        
        if drivers:
            click.echo(f"\n🚗 Found {len(drivers)} compatible drivers:")
            logger.info("Driver assets found", LogCategory.DRIVER, {
                'count': len(drivers),
                'drivers': [{'name': d.name, 'type': d.driver_type.value, 'family_id': d.family_id} for d in drivers]
            })
            
            # Group and display
            family_groups = {}
            for driver in drivers:
                family_id = driver.family_id or "Unknown"
                if family_id not in family_groups:
                    family_groups[family_id] = []
                family_groups[family_id].append(driver)
            
            for family_id, family_drivers in family_groups.items():
                click.echo(f"   📦 Family {family_id}:")
                for driver in family_drivers:
                    click.echo(f"      • {driver.name} [{driver.driver_type.value.upper()}]")
                    is_valid = await provider.validate_asset(driver)
                    status = "✅" if is_valid else "❌"
                    click.echo(f"        {status} {driver.path}")
                    
                    if not is_valid:
                        logger.warning("Driver validation failed", LogCategory.DRIVER, {
                            'driver_name': driver.name,
                            'path': str(driver.path),
                            'family_id': family_id
                        })
        else:
            logger.info("No drivers found", LogCategory.DRIVER)
        
        # Discover updates
        logger.debug("Discovering update assets", LogCategory.UPDATE)
        updates = await provider.get_updates(kassia_config.selectedOsId)
        assets_summary['updates'] = updates
        if updates:
            click.echo(f"\n📦 Found {len(updates)} compatible updates")
            logger.info("Update assets found", LogCategory.UPDATE, {
                'count': len(updates),
                'updates': [{'name': u.name, 'type': u.update_type.value, 'version': u.update_version} for u in updates]
            })
        
        # Discover Yunona scripts
        logger.debug("Discovering Yunona scripts", LogCategory.ASSET)
        scripts = await provider.get_yunona_scripts()
        assets_summary['yunona_scripts'] = scripts
        if scripts:
            click.echo(f"\n📜 Found {len(scripts)} Yunona scripts")
            logger.info("Yunona scripts found", LogCategory.ASSET, {
                'count': len(scripts),
                'scripts': [{'name': s.name, 'type': s.metadata.get('script_type')} for s in scripts]
            })
        
        duration = time.time() - start_time
        logger.log_operation_success("asset_discovery", duration, {
            'sbi_found': bool(assets_summary['sbi']),
            'drivers_count': len(assets_summary['drivers']),
            'updates_count': len(assets_summary['updates']),
            'scripts_count': len(assets_summary['yunona_scripts'])
        })
        
        return assets_summary
        
    except Exception as e:
        duration = time.time() - start_time
        logger.log_operation_failure("asset_discovery", str(e), duration)
        raise
    finally:
        logger.clear_context()

async def execute_cli_wim_workflow(job_db, job_id: str, kassia_config, assets_summary: dict, 
                                  skip_drivers: bool, skip_updates: bool, debug: bool) -> Optional[Path]:
    """Execute the complete WIM workflow with database persistence."""
    
    logger.set_context(job_id=job_id)
    logger.log_operation_start("cli_wim_workflow")
    workflow_start = time.time()
    
    try:
        if not assets_summary['sbi']:
            error_msg = "Cannot execute WIM workflow without SBI"
            click.echo(f"❌ {error_msg}")
            logger.error(error_msg, LogCategory.WIM)
            
            # Update job in database
            update_cli_job(job_db, job_id, 
                status="failed",
                error=error_msg,
                completed_at=datetime.now().isoformat()
            )
            
            return None
        
        sbi_asset = assets_summary['sbi']
        build_config = kassia_config.build
        
        # Update job to running
        update_cli_job(job_db, job_id,
            status="running",
            started_at=datetime.now().isoformat(),
            current_step="Starting WIM workflow",
            step_number=1,
            progress=5
        )
        
        logger.info("Starting CLI WIM workflow", LogCategory.WORKFLOW, {
            'sbi_name': sbi_asset.name,
            'device': kassia_config.device.deviceId,
            'os_id': kassia_config.selectedOsId,
            'skip_drivers': skip_drivers,
            'skip_updates': skip_updates
        })
        
        # Initialize WIM Handler and Workflow
        wim_handler = WimHandler()
        workflow = WimWorkflow(wim_handler)
        
        click.echo("\n🚀 Starting WIM processing workflow...")
        
        # Step 1: Prepare WIM
        click.echo("   Step 2/9: 🔄 WIM Preparation - copying to temporary location...")
        update_cli_job(job_db, job_id,
            current_step="Preparing WIM",
            step_number=2,
            progress=15
        )
        
        logger.info("Starting WIM preparation", LogCategory.WIM)
        step_start = time.time()
        
        temp_dir = Path(build_config.tempPath)
        temp_wim = await workflow.prepare_wim_for_modification(sbi_asset.path, temp_dir)
        
        step_duration = time.time() - step_start
        click.echo(f"   Step 2/9: ✅ WIM copied to: {temp_wim}")
        logger.info("WIM preparation completed", LogCategory.WIM, {
            'temp_wim': str(temp_wim),
            'duration': step_duration
        })
        
        # Step 2: Mount WIM
        click.echo("   Step 3/9: 🔄 WIM Mounting - mounting for modification...")
        update_cli_job(job_db, job_id,
            current_step="Mounting WIM",
            step_number=3,
            progress=25
        )
        
        logger.info("Starting WIM mount", LogCategory.WIM)
        step_start = time.time()
        
        mount_point = Path(build_config.mountPoint)
        mount_info = await workflow.mount_wim_for_modification(temp_wim, mount_point)
        
        step_duration = time.time() - step_start
        click.echo(f"   Step 3/9: ✅ WIM mounted at: {mount_point}")
        logger.info("WIM mount completed", LogCategory.WIM, {
            'mount_point': str(mount_point),
            'duration': step_duration,
            'read_write': mount_info.read_write
        })
        
        # Verify mount
        windows_dir = mount_point / "Windows"
        if windows_dir.exists():
            click.echo(f"   📁 Mount verified: Windows directory found")
            logger.debug("Mount verification successful", LogCategory.WIM)
        else:
            error_msg = "Mount verification failed: No Windows directory"
            logger.error(error_msg, LogCategory.WIM)
            update_cli_job(job_db, job_id,
                status="failed",
                error=error_msg,
                completed_at=datetime.now().isoformat()
            )
            raise Exception(error_msg)
        
        # Step 3: Driver Integration
        if not skip_drivers and assets_summary['drivers']:
            driver_count = len(assets_summary['drivers'])
            click.echo(f"   Step 5/9: 🔄 Driver Integration - integrating {driver_count} drivers...")
            update_cli_job(job_db, job_id,
                current_step=f"Integrating {driver_count} drivers",
                step_number=5,
                progress=50
            )
            
            logger.info("Starting driver integration", LogCategory.DRIVER, {
                'driver_count': driver_count
            })
            step_start = time.time()
            
            # Initialize driver integration
            driver_integrator = DriverIntegrator()
            driver_manager = DriverIntegrationManager(driver_integrator)
            
            # Execute driver integration
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
                click.echo(f"   Step 5/9: ✅ Driver Integration completed ({successful}/{driver_count} successful)")
                logger.info("Driver integration completed", LogCategory.DRIVER, {
                    'duration': step_duration,
                    'successful_count': successful,
                    'failed_count': integration_result['failed_count'],
                    'stats': integration_result['stats']
                })
                
                # Display detailed results
                formatted_results = driver_manager.format_integration_results(integration_result['results'])
                for result_line in formatted_results:
                    click.echo(result_line)
                    
            else:
                failed = integration_result['failed_count']
                click.echo(f"   Step 5/9: ❌ Driver Integration failed ({failed}/{driver_count} failed)")
                logger.error("Driver integration failed", LogCategory.DRIVER, {
                    'duration': step_duration,
                    'failed_count': failed,
                    'error_message': integration_result['message'],
                    'results': [r.__dict__ for r in integration_result['results']]
                })
                
        elif skip_drivers:
            click.echo(f"   Step 5/9: ⏭️ Driver Integration skipped")
            update_cli_job(job_db, job_id,
                current_step="Driver integration skipped",
                step_number=5,
                progress=50
            )
            logger.info("Driver integration skipped by user", LogCategory.DRIVER)
        else:
            click.echo(f"   Step 5/9: ⚠️ No drivers found for integration")
            update_cli_job(job_db, job_id,
                current_step="No drivers found",
                step_number=5,
                progress=50
            )
            logger.warning("No drivers found for integration", LogCategory.DRIVER)
        
        # Step 4: Update Integration
        if not skip_updates and assets_summary['updates']:
            update_count = len(assets_summary['updates'])
            click.echo(f"   Step 6/9: 🔄 Update Integration - integrating {update_count} updates...")
            update_cli_job(job_db, job_id,
                current_step=f"Integrating {update_count} updates",
                step_number=6,
                progress=70
            )
            
            logger.info("Starting update integration", LogCategory.UPDATE, {
                'update_count': update_count
            })
            step_start = time.time()
            
            # Initialize update integration
            update_integrator = UpdateIntegrator()
            update_manager = UpdateIntegrationManager(update_integrator)
            
            # Execute update integration
            integration_result = await update_manager.integrate_updates_for_os(
                assets_summary['updates'],
                mount_point,
                Path(kassia_config.build.yunonaPath),
                kassia_config.selectedOsId
            )
            
            step_duration = time.time() - step_start
            
            if integration_result['success']:
                successful = integration_result['successful_count']
                click.echo(f"   Step 6/9: ✅ Update Integration completed ({successful}/{update_count} successful)")
                logger.info("Update integration completed", LogCategory.UPDATE, {
                    'duration': step_duration,
                    'successful_count': successful,
                    'failed_count': integration_result['failed_count'],
                    'stats': integration_result['stats']
                })
                
                # Display detailed results
                formatted_results = update_manager.format_integration_results(integration_result['results'])
                for result_line in formatted_results:
                    click.echo(result_line)
                    
            else:
                failed = integration_result['failed_count']
                click.echo(f"   Step 6/9: ❌ Update Integration failed ({failed}/{update_count} failed)")
                logger.error("Update integration failed", LogCategory.UPDATE, {
                    'duration': step_duration,
                    'failed_count': failed,
                    'error_message': integration_result['message'],
                    'results': [r.__dict__ for r in integration_result['results']]
                })
                
        elif skip_updates:
            click.echo(f"   Step 6/9: ⏭️ Update Integration skipped")
            update_cli_job(job_db, job_id,
                current_step="Update integration skipped",
                step_number=6,
                progress=70
            )
            logger.info("Update integration skipped by user", LogCategory.UPDATE)
        else:
            click.echo(f"   Step 6/9: ⚠️ No updates found for integration")
            update_cli_job(job_db, job_id,
                current_step="No updates found",
                step_number=6,
                progress=70
            )
            logger.warning("No updates found for integration", LogCategory.UPDATE)
        
        # Step 5: Export WIM
        click.echo("   Step 7/9: 🔄 WIM Export - creating final image...")
        update_cli_job(job_db, job_id,
            current_step="Exporting WIM",
            step_number=7,
            progress=85
        )
        
        logger.info("Starting WIM export", LogCategory.WIM)
        step_start = time.time()
        
        export_dir = Path(build_config.exportPath)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_name = f"{kassia_config.selectedOsId}_{kassia_config.device.deviceId}_{timestamp}.wim"
        export_path = export_dir / export_name
        
        # Export final WIM
        final_wim = await workflow.finalize_and_export_wim(
            mount_point, 
            export_path, 
            export_name=f"Kassia {kassia_config.device.deviceId} OS{kassia_config.selectedOsId}"
        )
        
        step_duration = time.time() - step_start
        export_size = final_wim.stat().st_size
        export_size_mb = export_size / (1024 * 1024)
        
        click.echo(f"   Step 7/9: ✅ WIM exported to: {final_wim}")
        click.echo(f"   📊 Final WIM size: {export_size_mb:.1f} MB")
        logger.info("WIM export completed", LogCategory.WIM, {
            'duration': step_duration,
            'final_wim': str(final_wim),
            'size_mb': export_size_mb,
            'export_name': export_name
        })
        
        # Step 6: Cleanup
        click.echo("   Step 8/9: 🔄 Cleanup - removing temporary files...")
        update_cli_job(job_db, job_id,
            current_step="Cleanup",
            step_number=8,
            progress=95
        )
        
        logger.info("Starting cleanup", LogCategory.SYSTEM)
        step_start = time.time()
        
        await workflow.cleanup_workflow(keep_export=True)
        
        step_duration = time.time() - step_start
        click.echo("   Step 8/9: ✅ Cleanup completed")
        logger.info("Cleanup completed", LogCategory.SYSTEM, {
            'duration': step_duration
        })
        
        # Complete job
        workflow_duration = time.time() - workflow_start
        
        final_results = {
            'final_wim_path': str(final_wim),
            'final_wim_size_mb': export_size_mb,
            'total_duration_seconds': workflow_duration,
            'driver_integration': locals().get('integration_result', {}),
            'export_name': export_name
        }
        
        update_cli_job(job_db, job_id,
            status="completed",
            current_step="Completed",
            step_number=9,
            progress=100,
            completed_at=datetime.now().isoformat(),
            results=final_results
        )
        
        logger.log_operation_success("cli_wim_workflow", workflow_duration, {
            'final_wim': str(final_wim),
            'final_size_mb': export_size_mb,
            'device': kassia_config.device.deviceId,
            'os_id': kassia_config.selectedOsId
        })
        
        # Finalize job logging
        finalize_job_logging(job_id, "completed")
        
        return final_wim
        
    except DismError as e:
        workflow_duration = time.time() - workflow_start
        error_msg = f"DISM Error: {str(e)}"
        
        click.echo(f"   ❌ WIM workflow failed: {e}")
        logger.log_operation_failure("cli_wim_workflow", error_msg, workflow_duration, {
            'error_type': 'DismError'
        })
        
        # Update job with error
        update_cli_job(job_db, job_id,
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
        error_msg = f"Unexpected error: {str(e)}"
        
        click.echo(f"   ❌ Unexpected error in WIM workflow: {e}")
        logger.log_operation_failure("cli_wim_workflow", error_msg, workflow_duration, {
            'error_type': type(e).__name__
        })
        
        # Update job with error
        update_cli_job(job_db, job_id,
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

@click.command()
@click.option('--device', '-d', help='Device profile name (without .json extension)')
@click.option('--os-id', '-o', type=int, required=True, help='Operating system ID')
@click.option('--validate', is_flag=True, help='Validate configuration only (no build)')
@click.option('--debug', is_flag=True, help='Enable debug mode')
@click.option('--skip-drivers', is_flag=True, help='Skip driver integration')
@click.option('--skip-updates', is_flag=True, help='Skip update integration')
@click.option('--no-cleanup', is_flag=True, help='Skip cleanup (for debugging)')
@click.option('--list-assets', is_flag=True, help='List available assets and exit')
@click.option('--list-jobs', is_flag=True, help='List previous CLI jobs and exit')
@click.option('--verbose', '-v', is_flag=True, help='Verbose logging')
@click.option('--log-file/--no-log-file', default=True, help='Enable/disable file logging')
@click.option('--db-path', type=click.Path(path_type=Path), help='Custom database path')
@click.version_option(version=__version__)
def cli(device: Optional[str], os_id: int, validate: bool, debug: bool, 
        skip_drivers: bool, skip_updates: bool, no_cleanup: bool, list_assets: bool,
        list_jobs: bool, verbose: bool, log_file: bool, db_path: Optional[Path]):
    """
    🚀 Kassia Windows Image Preparation System - Python CLI with Database Integration
    """
    
    start_time = datetime.now()
    
    # Setup logging and database
    job_db = setup_logging_and_database(debug=debug or verbose, log_file=log_file, db_path=db_path)
    
    # Log startup
    logger.info("Kassia CLI started", LogCategory.SYSTEM, {
        'version': __version__,
        'startup_time': start_time.isoformat(),
        'arguments': {
            'device': device,
            'os_id': os_id,
            'validate': validate,
            'debug': debug,
            'skip_drivers': skip_drivers,
            'skip_updates': skip_updates,
            'verbose': verbose,
            'list_jobs': list_jobs
        }
    })
    
    # Display startup banner
    click.echo(f"""
+===============================================================+
|                    KASSIA v{__version__}                      |
|              Windows Image Preparation System                |
|                CLI with Database Integration                  |
|                                                               |
|  Starting: {start_time.strftime('%Y-%m-%d %H:%M:%S')}                    |
|  Database: {job_db.db_path}             |
+===============================================================+
""")
    
    try:
        # Handle list-jobs command
        if list_jobs:
            click.echo("📋 Previous CLI Jobs:")
            jobs = job_db.get_all_jobs(limit=20)
            
            if not jobs:
                click.echo("   No previous jobs found.")
                return
            
            for job in jobs:
                status_emoji = {
                    'completed': '✅',
                    'failed': '❌', 
                    'cancelled': '🚫',
                    'running': '🔄'
                }.get(job['status'], '❓')
                
                created_date = datetime.fromisoformat(job['created_at']).strftime('%Y-%m-%d %H:%M')
                duration = "N/A"
                
                if job['completed_at']:
                    start = datetime.fromisoformat(job['created_at'])
                    end = datetime.fromisoformat(job['completed_at'])
                    duration = str(end - start).split('.')[0]  # Remove microseconds
                
                click.echo(f"   {status_emoji} {job['id'][:8]}... | {job['device']} OS{job['os_id']} | {created_date} | {duration}")
                
                if job['error']:
                    click.echo(f"      Error: {job['error'][:100]}...")
                
                if job['results'] and job['results'].get('final_wim_path'):
                    final_size = job['results'].get('final_wim_size_mb', 0)
                    click.echo(f"      Result: {job['results']['final_wim_path']} ({final_size:.1f} MB)")
            
            click.echo(f"\n📊 Total jobs in database: {len(jobs)}")
            
            # Show database info
            db_info = job_db.get_database_info()
            click.echo(f"📁 Database size: {db_info.get('database_size_mb', 0):.1f} MB")
            
            return
        
        # Check prerequisites
        click.echo("🔍 Checking prerequisites...")
        prereq_result = check_prerequisites()
        
        if prereq_result.has_errors():
            click.echo("❌ Prerequisites errors:")
            for error in prereq_result.errors:
                click.echo(f"   - {error}")
            click.echo("\n💡 Solution: Run as Administrator for WIM operations")
            logger.critical("Prerequisites check failed - exiting", LogCategory.SYSTEM, {
                'errors': prereq_result.errors
            })
            sys.exit(1)
        
        if prereq_result.has_warnings():
            click.echo("⚠️  Prerequisites warnings:")
            for warning in prereq_result.warnings:
                click.echo(f"   - {warning}")
        else:
            click.echo("✅ Prerequisites check passed")
        
        # Device selection
        if not device:
            devices = list_devices()
            if not devices:
                click.echo("❌ No device configurations found")
                logger.error("No device configurations found", LogCategory.CONFIG)
                sys.exit(1)
            
            # Interactive device selection
            click.echo("\n📱 Available devices:")
            for i, dev in enumerate(devices, 1):
                click.echo(f"   {i}. {dev}")
            
            while True:
                try:
                    choice = click.prompt("Select device number", type=int)
                    if 1 <= choice <= len(devices):
                        device = devices[choice - 1]
                        break
                    else:
                        click.echo("Invalid choice. Please try again.")
                except (ValueError, click.Abort):
                    click.echo("Invalid input. Please enter a number.")
            
            logger.info("Device selected interactively", LogCategory.CONFIG, {
                'device': device,
                'available_devices': devices
            })
        else:
            logger.info("Device specified via argument", LogCategory.CONFIG, {
                'device': device
            })
        
        click.echo(f"📱 Device: {device}")
        click.echo(f"🖥️  OS ID: {os_id}")
        
        # Create job in database
        if not validate and not list_assets:
            job_id = create_cli_job(job_db, device, os_id,
                skip_drivers=skip_drivers,
                skip_updates=skip_updates,
                skip_validation=validate
            )
            click.echo(f"📝 Job ID: {job_id}")
        else:
            job_id = None
        
        # Load and validate configuration
        click.echo("🔧 Loading and validating configuration...")
        logger.log_operation_start("configuration_loading")
        config_start = time.time()
        
        try:
            kassia_config = ConfigLoader.create_kassia_config(device, os_id)
            config_duration = time.time() - config_start
            
            click.echo("✅ Configuration loaded and validated successfully")
            logger.log_operation_success("configuration_loading", config_duration, {
                'device': kassia_config.device.deviceId,
                'os_id': kassia_config.selectedOsId,
                'driver_families': len(kassia_config.get_driver_families())
            })
            
        except Exception as e:
            config_duration = time.time() - config_start
            click.echo(f"❌ Configuration validation failed: {e}")
            logger.log_operation_failure("configuration_loading", str(e), config_duration)
            
            if job_id:
                update_cli_job(job_db, job_id,
                    status="failed",
                    error=f"Configuration validation failed: {e}",
                    completed_at=datetime.now().isoformat()
                )
            
            if debug:
                import traceback
                traceback.print_exc()
            sys.exit(1)
        
        # Initialize directories
        click.echo("📁 Initializing directories...")
        logger.info("Initializing directories", LogCategory.SYSTEM)
        initialize_directories(kassia_config.build)
        click.echo("✅ Directories initialized")
        
        # Asset Discovery
        assets_summary = asyncio.run(discover_and_display_assets(kassia_config, device))
        
        # Display configuration summary
        display_configuration_summary(kassia_config, assets_summary)
        
        # Validation-only mode
        if validate:
            duration = datetime.now() - start_time
            total_assets = (
                (1 if assets_summary['sbi'] else 0) +
                len(assets_summary['drivers']) +
                len(assets_summary['updates']) +
                len(assets_summary['yunona_scripts'])
            )
            
            logger.info("Validation completed", LogCategory.SYSTEM, {
                'validation_only': True,
                'duration': str(duration),
                'total_assets': total_assets,
                'sbi_found': bool(assets_summary['sbi'])
            })
            
            click.echo(f"""
============================================================
✅ VALIDATION COMPLETED SUCCESSFULLY
Duration: {duration}
Device: {kassia_config.device.deviceId}
OS ID: {kassia_config.selectedOsId}
Total Assets: {total_assets}
============================================================
""")
            return
        
        # List assets mode
        if list_assets:
            click.echo("\n📂 Asset Summary:")
            click.echo(f"   SBI: {'✅' if assets_summary['sbi'] else '❌'}")
            click.echo(f"   Drivers: {len(assets_summary['drivers'])}")
            click.echo(f"   Updates: {len(assets_summary['updates'])}")
            click.echo(f"   Yunona Scripts: {len(assets_summary['yunona_scripts'])}")
            return
        
        # Execute WIM Workflow
        final_wim = asyncio.run(execute_cli_wim_workflow(
            job_db, job_id, kassia_config, assets_summary, skip_drivers, skip_updates, debug
        ))
        
        # Final summary
        duration = datetime.now() - start_time
        
        if final_wim:
            final_size = final_wim.stat().st_size / (1024 * 1024)
            logger.info("Kassia CLI completed successfully", LogCategory.SYSTEM, {
                'total_duration': str(duration),
                'final_wim': str(final_wim),
                'final_size_mb': final_size,
                'device': kassia_config.device.deviceId,
                'os_id': kassia_config.selectedOsId,
                'job_id': job_id
            })
            
            click.echo(f"""
============================================================
✅ KASSIA WIM BUILD COMPLETED SUCCESSFULLY!
Duration: {duration}
Device: {kassia_config.device.deviceId}
OS ID: {kassia_config.selectedOsId}
Job ID: {job_id}
Final WIM: {final_wim}
Final Size: {final_size:.1f} MB
============================================================

🎉 Success! Your customized Windows image is ready for deployment!
💾 Job details saved to database: {job_db.db_path}
""")
        else:
            logger.error("Kassia CLI completed with failure", LogCategory.SYSTEM, {
                'total_duration': str(duration),
                'device': kassia_config.device.deviceId,
                'os_id': kassia_config.selectedOsId,
                'job_id': job_id
            })
            
            click.echo(f"""
============================================================
❌ KASSIA WIM BUILD FAILED
Duration: {duration}
Device: {kassia_config.device.deviceId}
OS ID: {kassia_config.selectedOsId}
Job ID: {job_id}
============================================================

💡 Check error messages above for details.
💡 Check logs in runtime/logs/ for detailed information.
💡 Run with --debug for more information.
💾 Job details saved to database: {job_db.db_path}
""")
            sys.exit(1)
        
    except KeyboardInterrupt:
        click.echo("\n\n❌ Operation cancelled by user")
        logger.warning("Operation cancelled by user", LogCategory.SYSTEM)
        
        # Update job if exists
        if 'job_id' in locals() and job_id:
            update_cli_job(job_db, job_id,
                status="cancelled",
                completed_at=datetime.now().isoformat()
            )
        
        # Emergency cleanup
        try:
            wim_handler = WimHandler()
            asyncio.run(wim_handler.cleanup_all_mounts(force=True))
            logger.info("Emergency cleanup completed", LogCategory.SYSTEM)
        except Exception as e:
            logger.error("Emergency cleanup failed", LogCategory.SYSTEM, {
                'error': str(e)
            })
        sys.exit(1)
        
    except Exception as e:
        duration = datetime.now() - start_time
        logger.critical("Kassia CLI failed with unexpected error", LogCategory.ERROR, {
            'duration': str(duration),
            'error': str(e),
            'error_type': type(e).__name__
        })
        
        # Update job if exists
        if 'job_id' in locals() and job_id:
            update_cli_job(job_db, job_id,
                status="failed",
                error=str(e),
                completed_at=datetime.now().isoformat()
            )
        
        click.echo(f"""
============================================================
❌ KASSIA EXECUTION FAILED
Duration: {duration}
Error: {e}
============================================================
""")
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


# Helper functions that need logging integration
def list_devices() -> List[str]:
    """List available device configurations with logging."""
    logger = get_logger("kassia.config")
    logger.debug("Listing available device configurations", LogCategory.CONFIG)
    
    device_configs_path = Path("config/device_configs")
    if not device_configs_path.exists():
        logger.warning("Device configs directory not found", LogCategory.CONFIG, {
            'path': str(device_configs_path)
        })
        return []
    
    devices = []
    for json_file in device_configs_path.glob("*.json"):
        device_name = json_file.stem
        devices.append(device_name)
    
    logger.info("Device configurations discovered", LogCategory.CONFIG, {
        'count': len(devices),
        'devices': devices
    })
    
    return sorted(devices)


def initialize_directories(build_config) -> None:
    """Initialize required directories with logging."""
    logger = get_logger("kassia.system")
    logger.debug("Initializing directories", LogCategory.SYSTEM)
    
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
            click.echo(f"❌ Failed to create directory {dir_path}: {e}")
            sys.exit(1)
    
    logger.info("Directories initialized", LogCategory.SYSTEM, {
        'directories': created_dirs
    })


def display_configuration_summary(config, assets_summary: dict) -> None:
    """Display configuration summary with logging."""
    logger = get_logger("kassia.config")
    
    summary_data = {
        'device': config.device.deviceId,
        'os_id': config.selectedOsId,
        'driver_families_required': len(config.get_driver_families()),
        'sbi_found': bool(assets_summary['sbi']),
        'drivers_count': len(assets_summary['drivers']),
        'updates_count': len(assets_summary['updates']),
        'yunona_scripts_count': len(assets_summary['yunona_scripts'])
    }
    
    logger.info("Configuration summary", LogCategory.CONFIG, summary_data)
    
    click.echo("\n📋 Build Configuration Summary:")
    click.echo(f"   Device: {config.device.deviceId}")
    click.echo(f"   OS ID: {config.selectedOsId}")
    click.echo(f"   Required Driver Families: {len(config.get_driver_families())}")
    
    configured_wim = config.build.osWimMap.get(str(config.selectedOsId))
    if configured_wim:
        click.echo(f"   Configured WIM: {configured_wim}")
    else:
        click.echo(f"   ❌ No WIM configured for OS {config.selectedOsId}")
    
    click.echo("\n🎯 Build Readiness Assessment:")
    
    if assets_summary['sbi']:
        click.echo("   ✅ SBI ready for WIM processing")
        sbi_source = assets_summary['sbi'].metadata.get('source', 'unknown')
        click.echo(f"      📋 Discovery method: {sbi_source}")
    else:
        click.echo("   ❌ SBI missing - cannot proceed with WIM build")
        click.echo("      💡 Check configuration paths and file existence")
    
    drivers_count = len(assets_summary['drivers'])
    if drivers_count > 0:
        click.echo(f"   ✅ Drivers ready for integration ({drivers_count} packages)")
    else:
        click.echo("   ⚠️  No drivers found - WIM will be built without driver integration")


if __name__ == "__main__":
    cli()