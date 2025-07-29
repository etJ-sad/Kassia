"""
Kassia Python - Main CLI Entry Point (With WIM Handler Integration)
Windows Image Preparation System - Python Edition
"""

import click
import sys
import os
import asyncio
from pathlib import Path
from typing import Optional, List
from datetime import datetime

# Import our models, asset providers, WIM handler, driver integration, and update integration
from app.models.config import (
    KassiaConfig, ConfigLoader, ValidationResult, 
    DeviceConfig, BuildConfig, RuntimeState
)
from app.core.asset_providers import LocalAssetProvider, AssetType
from app.core.wim_handler import WimHandler, WimWorkflow, DismError
from app.core.driver_integration import DriverIntegrator, DriverIntegrationManager
from app.core.update_integration import UpdateIntegrator, UpdateIntegrationManager

# Version info
__version__ = "2.0.0"

def check_prerequisites() -> ValidationResult:
    """Check system prerequisites with detailed validation."""
    result = ValidationResult(isValid=True)
    
    # Check if we're on Windows
    if os.name != 'nt':
        result.add_warning("This tool is designed for Windows systems")
    
    # Check if running as admin
    try:
        is_admin = os.access(os.sep, os.W_OK)
        if not is_admin:
            result.add_error("Administrator privileges required for WIM operations")
    except:
        result.add_warning("Could not check administrator privileges")
    
    # Check if DISM is available (enhanced check)
    try:
        wim_handler = WimHandler()
        result.add_warning("DISM validation successful")  # Convert to info message
    except DismError as e:
        result.add_error(f"DISM not available: {e}")
    except:
        result.add_error("DISM tool verification failed")
    
    # Check Python version
    if sys.version_info < (3, 11):
        result.add_warning(f"Python 3.11+ recommended. Current: {sys.version}")
    
    return result

def list_devices() -> List[str]:
    """List available device configurations."""
    device_configs_path = Path("config/device_configs")
    if not device_configs_path.exists():
        return []
    
    devices = []
    for json_file in device_configs_path.glob("*.json"):
        device_name = json_file.stem
        devices.append(device_name)
    
    return sorted(devices)

def interactive_device_selection() -> str:
    """Interactive device selection with validation."""
    devices = list_devices()
    
    if not devices:
        click.echo("❌ No device configurations found in config/device_configs/")
        click.echo("   Please add device configuration files (.json)")
        sys.exit(1)
    
    click.echo("\n📱 Available device profiles:")
    for i, device in enumerate(devices):
        try:
            device_config = ConfigLoader.load_device_config(device)
            supported_os = device_config.get_supported_os_ids()
            click.echo(f"[{i}] {device} (OS IDs: {supported_os})")
        except Exception:
            click.echo(f"[{i}] {device} (config error)")
    
    while True:
        try:
            selection = click.prompt(f"\nSelect device profile (0-{len(devices)-1})", type=int)
            if 0 <= selection < len(devices):
                selected = devices[selection]
                click.echo(f"✅ Selected device: {selected}")
                return selected
            else:
                click.echo(f"❌ Invalid selection. Please choose 0-{len(devices)-1}")
        except (ValueError, click.Abort):
            click.echo("\n❌ Selection cancelled")
            sys.exit(1)

def initialize_directories(build_config: BuildConfig) -> None:
    """Initialize required directories using build config."""
    directories = [
        build_config.tempPath,
        build_config.mountPoint,
        build_config.exportPath,
        "runtime/logs"
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            click.echo(f"❌ Failed to create directory {dir_path}: {e}")
            sys.exit(1)

async def discover_and_display_assets(kassia_config: KassiaConfig, device_name: str) -> dict:
    """Discover and display available assets."""
    assets_path = Path("assets")
    provider = LocalAssetProvider(assets_path)
    
    click.echo("\n🔍 Discovering assets...")
    
    assets_summary = {
        'sbi': None,
        'drivers': [],
        'updates': [],
        'yunona_scripts': []
    }
    
    # Discover SBI (System Base Image)
    sbi_asset = await provider.get_sbi(kassia_config.selectedOsId)
    if sbi_asset:
        size_mb = sbi_asset.size / (1024 * 1024) if sbi_asset.size else 0
        click.echo(f"📀 SBI Found: {sbi_asset.name} ({size_mb:.1f} MB)")
        assets_summary['sbi'] = sbi_asset
        
        # Validate SBI with WIM Handler
        try:
            wim_handler = WimHandler()
            wim_info = await wim_handler.get_wim_info(sbi_asset.path)
            click.echo(f"   ✅ WIM validated: {wim_info.name}")
            click.echo(f"   📋 Architecture: {wim_info.architecture or 'Not specified'}")
        except DismError as e:
            click.echo(f"   ❌ WIM validation failed: {e}")
    else:
        click.echo(f"❌ No SBI found for OS ID {kassia_config.selectedOsId}")
        click.echo(f"   Expected location: assets/sbi/*.wim")
    
    # Discover other assets (same as before)
    drivers = await provider.get_drivers(device_name, kassia_config.selectedOsId)
    assets_summary['drivers'] = drivers
    
    if drivers:
        click.echo(f"\n🚗 Found {len(drivers)} compatible drivers:")
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
    
    updates = await provider.get_updates(kassia_config.selectedOsId)
    assets_summary['updates'] = updates
    if updates:
        click.echo(f"\n📦 Found {len(updates)} compatible updates")
    
    scripts = await provider.get_yunona_scripts()
    assets_summary['yunona_scripts'] = scripts
    if scripts:
        click.echo(f"\n📜 Found {len(scripts)} Yunona scripts")
    
    return assets_summary

def display_configuration_summary(config: KassiaConfig, assets_summary: dict) -> None:
    """Display enhanced configuration summary with assets."""
    click.echo("\n📋 Build Configuration Summary:")
    click.echo(f"   Device: {config.device.deviceId}")
    click.echo(f"   OS ID: {config.selectedOsId}")
    click.echo(f"   Required Driver Families: {len(config.get_driver_families())}")
    click.echo(f"   WIM: {config.get_wim_path()}")
    
    # Build readiness with WIM focus
    click.echo("\n🎯 Build Readiness Assessment:")
    
    if assets_summary['sbi']:
        click.echo("   ✅ SBI ready for WIM processing")
    else:
        click.echo("   ❌ SBI missing - cannot proceed with WIM build")
    
    drivers_count = len(assets_summary['drivers'])
    if drivers_count > 0:
        click.echo(f"   ✅ Drivers ready for integration ({drivers_count} packages)")
    else:
        click.echo("   ⚠️  No drivers found - WIM will be built without driver integration")

async def execute_wim_workflow(kassia_config: KassiaConfig, assets_summary: dict, 
                              skip_drivers: bool, skip_updates: bool, debug: bool) -> Optional[Path]:
    """Execute the complete WIM workflow."""
    
    if not assets_summary['sbi']:
        click.echo("❌ Cannot execute WIM workflow without SBI")
        return None
    
    sbi_asset = assets_summary['sbi']
    build_config = kassia_config.build
    
    # Initialize WIM Handler and Workflow
    try:
        wim_handler = WimHandler()
        workflow = WimWorkflow(wim_handler)
        
        click.echo("\n🚀 Starting WIM processing workflow...")
        
        # Step 1: Prepare WIM for modification
        click.echo("   Step 2/9: 🔄 WIM Preparation - copying to temporary location...")
        temp_dir = Path(build_config.tempPath)
        temp_wim = await workflow.prepare_wim_for_modification(sbi_asset.path, temp_dir)
        click.echo(f"   Step 2/9: ✅ WIM copied to: {temp_wim}")
        
        # Step 2: Mount WIM
        click.echo("   Step 3/9: 🔄 WIM Mounting - mounting for modification...")
        mount_point = Path(build_config.mountPoint)
        mount_info = await workflow.mount_wim_for_modification(temp_wim, mount_point)
        click.echo(f"   Step 3/9: ✅ WIM mounted at: {mount_point}")
        
        # Verify mount
        windows_dir = mount_point / "Windows"
        if windows_dir.exists():
            click.echo(f"   📁 Mount verified: Windows directory found")
            
            # Show some mounted content
            try:
                dirs = [d.name for d in mount_point.iterdir() if d.is_dir()][:5]
                click.echo(f"   📋 Mounted directories: {', '.join(dirs)}")
            except:
                pass
        
        # Step 3: Driver Integration (REAL IMPLEMENTATION!)
        if not skip_drivers and assets_summary['drivers']:
            driver_count = len(assets_summary['drivers'])
            click.echo(f"   Step 5/9: 🔄 Driver Integration - integrating {driver_count} drivers...")
            
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
            
            if integration_result['success']:
                successful = integration_result['successful_count']
                click.echo(f"   Step 5/9: ✅ Driver Integration completed ({successful}/{driver_count} successful)")
                
                # Display detailed results
                formatted_results = driver_manager.format_integration_results(integration_result['results'])
                for result_line in formatted_results:
                    click.echo(result_line)
                
                # Show statistics
                stats = integration_result['stats']
                if stats['inf_via_dism'] > 0:
                    click.echo(f"      📦 INF drivers via DISM: {stats['inf_via_dism']}")
                if stats['appx_via_yunona'] > 0:
                    click.echo(f"      📱 APPX packages to Yunona: {stats['appx_via_yunona']}")
                if stats['exe_via_yunona'] > 0:
                    click.echo(f"      ⚙️ EXE installers to Yunona: {stats['exe_via_yunona']}")
                    
            else:
                failed = integration_result['failed_count']
                click.echo(f"   Step 5/9: ❌ Driver Integration failed ({failed}/{driver_count} failed)")
                click.echo(f"      💥 Error: {integration_result['message']}")
                
                # Show failed drivers
                if integration_result['results']:
                    formatted_results = driver_manager.format_integration_results(integration_result['results'])
                    for result_line in formatted_results:
                        click.echo(result_line)
                        
        elif skip_drivers:
            click.echo(f"   Step 5/9: ⏭️ Driver Integration skipped")
        else:
            click.echo(f"   Step 5/9: ⚠️ No drivers found for integration")
        
        # Step 4: Update Integration (REAL IMPLEMENTATION!)
        if not skip_updates and assets_summary['updates']:
            update_count = len(assets_summary['updates'])
            click.echo(f"   Step 4/9: 🔄 Update Integration - integrating {update_count} updates...")
            
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
            
            if integration_result['success']:
                successful = integration_result['successful_count']
                click.echo(f"   Step 4/9: ✅ Update Integration completed ({successful}/{update_count} successful)")
                
                # Display detailed results
                formatted_results = update_manager.format_integration_results(integration_result['results'])
                for result_line in formatted_results:
                    click.echo(result_line)
                
                # Show statistics
                stats = integration_result['stats']
                if stats['msu_via_dism'] > 0:
                    click.echo(f"      📦 MSU updates via DISM: {stats['msu_via_dism']}")
                if stats['cab_via_dism'] > 0:
                    click.echo(f"      📦 CAB updates via DISM: {stats['cab_via_dism']}")
                if stats['exe_via_yunona'] > 0:
                    click.echo(f"      📱 EXE updates to Yunona: {stats['exe_via_yunona']}")
                if stats['msi_via_yunona'] > 0:
                    click.echo(f"      ⚙️ MSI updates to Yunona: {stats['msi_via_yunona']}")
                if stats['total_size_added'] > 0:
                    size_mb = stats['total_size_added'] / (1024 * 1024)
                    click.echo(f"      📊 Total size added to WIM: {size_mb:.1f} MB")
                    
            else:
                failed = integration_result['failed_count']
                click.echo(f"   Step 4/9: ❌ Update Integration failed ({failed}/{update_count} failed)")
                click.echo(f"      💥 Error: {integration_result['message']}")
                
                # Show failed updates
                if integration_result['results']:
                    formatted_results = update_manager.format_integration_results(integration_result['results'])
                    for result_line in formatted_results:
                        click.echo(result_line)
                        
        elif skip_updates:
            click.echo(f"   Step 4/9: ⏭️ Update Integration skipped")
        else:
            click.echo(f"   Step 4/9: ⚠️ No updates found for integration")
        
        # Step 5: Export WIM
        click.echo("   Step 7/9: 🔄 WIM Export - creating final image...")
        export_dir = Path(build_config.exportPath)
        
        # Generate export filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_name = f"{kassia_config.selectedOsId}_{kassia_config.device.deviceId}_{timestamp}.wim"
        export_path = export_dir / export_name
        
        # Export final WIM
        final_wim = await workflow.finalize_and_export_wim(
            mount_point, 
            export_path, 
            export_name=f"Kassia {kassia_config.device.deviceId} OS{kassia_config.selectedOsId}"
        )
        
        click.echo(f"   Step 7/9: ✅ WIM exported to: {final_wim}")
        
        # Get export size
        export_size = final_wim.stat().st_size
        export_size_mb = export_size / (1024 * 1024)
        click.echo(f"   📊 Final WIM size: {export_size_mb:.1f} MB")
        
        # Step 6: Cleanup
        click.echo("   Step 8/9: 🔄 Cleanup - removing temporary files...")
        await workflow.cleanup_workflow(keep_export=True)
        click.echo("   Step 8/9: ✅ Cleanup completed")
        
        return final_wim
        
    except DismError as e:
        click.echo(f"   ❌ WIM workflow failed: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        
        # Emergency cleanup
        try:
            await workflow.cleanup_workflow(keep_export=False)
        except:
            pass
        
        return None
    except Exception as e:
        click.echo(f"   ❌ Unexpected error in WIM workflow: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return None

@click.command()
@click.option('--device', '-d', help='Device profile name (without .json extension)')
@click.option('--os-id', '-o', type=int, required=True, help='Operating system ID')
@click.option('--validate', is_flag=True, help='Validate configuration only (no build)')
@click.option('--debug', is_flag=True, help='Enable debug mode')
@click.option('--skip-drivers', is_flag=True, help='Skip driver integration')
@click.option('--skip-updates', is_flag=True, help='Skip update integration')
@click.option('--no-cleanup', is_flag=True, help='Skip cleanup (for debugging)')
@click.option('--list-assets', is_flag=True, help='List available assets and exit')
@click.version_option(version=__version__)
def cli(device: Optional[str], os_id: int, validate: bool, debug: bool, 
        skip_drivers: bool, skip_updates: bool, no_cleanup: bool, list_assets: bool):
    """
    🚀 Kassia Windows Image Preparation System - Python Edition
    
    Prepares customized Windows images (WIM) for deployment using device-specific configurations.
    
    Examples:
    
      kassia --device xX-39A --os-id 10
      
      kassia --os-id 10  (interactive device selection)
      
      kassia --device xX-39A --os-id 10 --validate
    """
    
    start_time = datetime.now()
    
    # Display startup banner
    click.echo(f"""
+===============================================================+
|                    KASSIA v{__version__}                      |
|              Windows Image Preparation System                |
|                  Python Edition with WIM Handler             |
|                                                               |
|  Starting: {start_time.strftime('%Y-%m-%d %H:%M:%S')}                    |
+===============================================================+
""")
    
    try:
        # Check prerequisites (enhanced for WIM operations)
        click.echo("🔍 Checking prerequisites...")
        prereq_result = check_prerequisites()
        
        if prereq_result.has_errors():
            click.echo("❌ Prerequisites errors:")
            for error in prereq_result.errors:
                click.echo(f"   - {error}")
            click.echo("\n💡 Solution: Run as Administrator for WIM operations")
            sys.exit(1)
        
        if prereq_result.has_warnings():
            click.echo("⚠️  Prerequisites warnings:")
            for warning in prereq_result.warnings:
                click.echo(f"   - {warning}")
        else:
            click.echo("✅ Prerequisites check passed")
        
        # Device selection
        if not device:
            device = interactive_device_selection()
        else:
            click.echo(f"📱 Device: {device}")
        
        click.echo(f"🖥️  OS ID: {os_id}")
        
        if debug:
            click.echo("🐛 Debug mode enabled")
        
        # Load and validate configuration
        click.echo("🔧 Loading and validating configuration...")
        try:
            kassia_config = ConfigLoader.create_kassia_config(device, os_id)
            click.echo("✅ Configuration loaded and validated successfully")
        except Exception as e:
            click.echo(f"❌ Configuration validation failed: {e}")
            if debug:
                import traceback
                traceback.print_exc()
            sys.exit(1)
        
        # Initialize directories
        click.echo("📁 Initializing directories...")
        initialize_directories(kassia_config.build)
        click.echo("✅ Directories initialized")
        
        # Asset Discovery with WIM validation
        assets_summary = asyncio.run(discover_and_display_assets(kassia_config, device))
        
        # Display configuration summary
        display_configuration_summary(kassia_config, assets_summary)
        
        # List assets and exit if requested
        if list_assets:
            click.echo("\n🎯 Asset listing completed.")
            return
        
        # Validation-only mode
        if validate:
            duration = datetime.now() - start_time
            total_assets = (
                (1 if assets_summary['sbi'] else 0) +
                len(assets_summary['drivers']) +
                len(assets_summary['updates']) +
                len(assets_summary['yunona_scripts'])
            )
            
            click.echo(f"""
============================================================
✅ VALIDATION COMPLETED SUCCESSFULLY (WITH WIM VALIDATION)
Duration: {duration}
Device: {kassia_config.device.deviceId}
OS ID: {kassia_config.selectedOsId}
Total Assets: {total_assets}
WIM Handler: ✅ Ready
============================================================
""")
            return
        
        # Execute WIM Workflow
        runtime = RuntimeState(totalSteps=9)
        click.echo("\n🚀 Starting build process with WIM integration...")
        
        runtime.stepNumber = 1
        runtime.currentStep = "Configuration & Asset Validation"
        click.echo(f"   Step {runtime.stepNumber}/{runtime.totalSteps}: ✅ {runtime.currentStep} completed")
        
        # Execute the actual WIM workflow
        final_wim = asyncio.run(execute_wim_workflow(
            kassia_config, assets_summary, skip_drivers, skip_updates, debug
        ))
        
        runtime.stepNumber = 9
        runtime.currentStep = "Process Completed"
        click.echo(f"   Step {runtime.stepNumber}/{runtime.totalSteps}: ✅ {runtime.currentStep}")
        
        # Final summary
        duration = datetime.now() - start_time
        progress = runtime.get_progress_percentage()
        
        if final_wim:
            final_size = final_wim.stat().st_size / (1024 * 1024)
            click.echo(f"""
============================================================
✅ KASSIA WIM BUILD COMPLETED SUCCESSFULLY!
Duration: {duration}
Progress: {progress:.1f}%
Device: {kassia_config.device.deviceId}
OS ID: {kassia_config.selectedOsId}
Final WIM: {final_wim}
Final Size: {final_size:.1f} MB
============================================================

🎉 Success! Your customized Windows image is ready for deployment!
""")
        else:
            click.echo(f"""
============================================================
❌ KASSIA WIM BUILD FAILED
Duration: {duration}
Device: {kassia_config.device.deviceId}
OS ID: {kassia_config.selectedOsId}
============================================================

💡 Check error messages above for details.
""")
            sys.exit(1)
        
    except KeyboardInterrupt:
        click.echo("\n\n❌ Operation cancelled by user")
        # Emergency cleanup
        try:
            wim_handler = WimHandler()
            asyncio.run(wim_handler.cleanup_all_mounts(force=True))
        except:
            pass
        sys.exit(1)
    except Exception as e:
        duration = datetime.now() - start_time
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

if __name__ == "__main__":
    cli()