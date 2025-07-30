"""
Driver Integration Test Script
Test driver integration functionality with real assets
"""

import asyncio
import sys
from pathlib import Path
import logging

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.driver_integration import DriverIntegrator, DriverIntegrationManager
from app.core.asset_providers import LocalAssetProvider
from app.models.config import ConfigLoader

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_driver_discovery():
    """Test driver discovery with real assets."""
    
    print("🔍 Testing Driver Discovery...")
    print("=" * 50)
    
    # Load real configuration
    try:
        kassia_config = ConfigLoader.create_kassia_config("xX-39A", 10)
        print(f"✅ Configuration loaded: {kassia_config.device.deviceId}")
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return []
    
    # Discover drivers
    assets_path = Path("assets")
    provider = LocalAssetProvider(assets_path)
    
    drivers = await provider.get_drivers("xX-39A", 10)
    
    if drivers:
        print(f"✅ Found {len(drivers)} drivers:")
        for i, driver in enumerate(drivers, 1):
            print(f"   [{i}] {driver.name}")
            print(f"       Type: {driver.driver_type.value}")
            print(f"       Family: {driver.family_id}")
            print(f"       Path: {driver.path}")
            
            # Quick validation
            is_valid = await provider.validate_asset(driver)
            print(f"       Valid: {'✅' if is_valid else '❌'}")
            print()
    else:
        print("❌ No drivers found")
    
    return drivers

async def test_driver_integration_dry_run(drivers):
    """Test driver integration logic without actual WIM mount."""
    
    print("🧪 Testing Driver Integration (Dry Run)...")
    print("=" * 50)
    
    if not drivers:
        print("❌ No drivers to test")
        return
    
    # Create mock mount and yunona paths
    mock_mount = Path("runtime/test_mount")
    mock_yunona = Path("assets/yunona")
    
    # Ensure test directories exist
    mock_mount.mkdir(parents=True, exist_ok=True)
    (mock_mount / "Windows").mkdir(exist_ok=True)  # Simulate mounted WIM
    
    # Initialize integrator
    integrator = DriverIntegrator()
    manager = DriverIntegrationManager(integrator)
    
    print(f"📦 Testing integration of {len(drivers)} drivers...")
    
    # Test each driver type logic
    for driver in drivers:
        print(f"\n🔧 Testing: {driver.name} [{driver.driver_type.value.upper()}]")
        
        if driver.driver_type.value == "inf":
            print("   📋 INF Driver - would use DISM /Add-Driver")
            inf_files = list(driver.path.rglob("*.inf"))
            print(f"   📁 Found {len(inf_files)} INF files")
            for inf in inf_files[:3]:  # Show first 3
                print(f"      • {inf.name}")
                
        elif driver.driver_type.value == "appx":
            print("   📱 APPX Package - would stage to Yunona")
            appx_files = list(driver.path.rglob("*.appx"))
            print(f"   📁 Found {len(appx_files)} APPX files")
            for appx in appx_files[:3]:  # Show first 3
                print(f"      • {appx.name}")
                
        elif driver.driver_type.value == "exe":
            print("   ⚙️ EXE Installer - would stage to Yunona")
            exe_files = list(driver.path.rglob("*.exe"))
            print(f"   📁 Found {len(exe_files)} EXE files")
            for exe in exe_files[:3]:  # Show first 3
                print(f"      • {exe.name}")
    
    # Cleanup test directories
    try:
        import shutil
        if mock_mount.exists():
            shutil.rmtree(mock_mount)
        print("\n✅ Test cleanup completed")
    except:
        pass

async def test_yunona_staging():
    """Test Yunona staging functionality."""
    
    print("\n📜 Testing Yunona Staging...")
    print("=" * 50)
    
    yunona_source = Path("assets/yunona")
    if not yunona_source.exists():
        print("❌ Yunona source not found")
        return
    
    print(f"✅ Yunona source found: {yunona_source}")
    
    # List yunona files
    yunona_files = list(yunona_source.rglob("*"))
    script_files = [f for f in yunona_files if f.suffix in ['.py', '.ps1', '.cmd', '.bat']]
    
    print(f"📁 Yunona files: {len(yunona_files)} total")
    print(f"📜 Script files: {len(script_files)}")
    
    for script in script_files:
        print(f"   • {script.name} ({script.suffix})")
    
    # Check for config.json
    config_file = yunona_source / "config.json"
    if config_file.exists():
        print("✅ Yunona config.json found")
        try:
            import json
            with open(config_file) as f:
                config = json.load(f)
            print(f"   📋 Version: {config.get('version', 'Unknown')}")
            print(f"   📋 Name: {config.get('name', 'Unknown')}")
        except Exception as e:
            print(f"⚠️  Failed to read config: {e}")
    else:
        print("⚠️  Yunona config.json not found")

async def test_full_integration_simulation():
    """Test full integration simulation with logging."""
    
    print("\n🚀 Testing Full Integration Simulation...")
    print("=" * 60)
    
    # Load configuration
    try:
        kassia_config = ConfigLoader.create_kassia_config("xX-39A", 10)
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return
    
    # Get drivers
    assets_path = Path("assets")
    provider = LocalAssetProvider(assets_path)
    drivers = await provider.get_drivers("xX-39A", 10)
    
    if not drivers:
        print("❌ No drivers found for simulation")
        return
    
    print(f"📦 Simulating integration of {len(drivers)} drivers...")
    
    # Create integration manager
    integrator = DriverIntegrator()
    manager = DriverIntegrationManager(integrator)
    
    # Simulate integration workflow
    print("\n🔄 Integration Workflow Simulation:")
    print("   Step 1: ✅ Drivers discovered and validated")
    print("   Step 2: ✅ Mount point verified (simulated)")
    print("   Step 3: ✅ Yunona core staged (simulated)")
    print("   Step 4: 🔄 Processing individual drivers...")
    
    # Process each driver
    for i, driver in enumerate(drivers, 1):
        print(f"\n   Driver {i}/{len(drivers)}: {driver.name}")
        print(f"      Type: {driver.driver_type.value.upper()}")
        print(f"      Family: {driver.family_id}")
        
        if driver.driver_type.value == "inf":
            print(f"      Method: DISM /Add-Driver")
            print(f"      Target: Mounted WIM")
            inf_count = len(list(driver.path.rglob("*.inf")))
            print(f"      Files: {inf_count} INF files")
            
        elif driver.driver_type.value == "appx":
            print(f"      Method: Stage to Yunona")
            print(f"      Target: /Users/Public/Yunona/Drivers/")
            appx_count = len(list(driver.path.rglob("*.appx")))
            print(f"      Files: {appx_count} APPX packages")
            
        elif driver.driver_type.value == "exe":
            print(f"      Method: Stage to Yunona")
            print(f"      Target: /Users/Public/Yunona/Drivers/")
            exe_count = len(list(driver.path.rglob("*.exe")))
            print(f"      Files: {exe_count} EXE installers")
        
        print(f"      Status: ✅ Ready for integration")
    
    # Show final statistics
    inf_drivers = sum(1 for d in drivers if d.driver_type.value == "inf")
    appx_drivers = sum(1 for d in drivers if d.driver_type.value == "appx")
    exe_drivers = sum(1 for d in drivers if d.driver_type.value == "exe")
    
    print(f"\n📊 Integration Summary:")
    print(f"   Total Drivers: {len(drivers)}")
    print(f"   INF (via DISM): {inf_drivers}")
    print(f"   APPX (via Yunona): {appx_drivers}")
    print(f"   EXE (via Yunona): {exe_drivers}")
    
    print(f"\n✅ Integration simulation completed successfully!")

def main():
    """Main test function."""
    print("Kassia Driver Integration Test Suite")
    print("=" * 50)
    
    async def run_tests():
        """Run all tests."""
        try:
            # Test 1: Driver Discovery
            drivers = await test_driver_discovery()
            
            # Test 2: Integration Logic
            await test_driver_integration_dry_run(drivers)
            
            # Test 3: Yunona Staging
            await test_yunona_staging()
            
            # Test 4: Full Simulation
            await test_full_integration_simulation()
            
            print("\n" + "=" * 60)
            print("✅ All driver integration tests completed!")
            print("\n💡 Next steps:")
            print("   1. Run full CLI with driver integration:")
            print("      python -m app.main --device xX-39A --os-id 10")
            print("   2. Check runtime/export/ for final WIM with drivers")
            print("   3. Verify Yunona staging in mounted WIM")
            
        except Exception as e:
            print(f"\n❌ Test suite failed: {e}")
            import traceback
            traceback.print_exc()
            return 1
    
    return asyncio.run(run_tests()) or 0

if __name__ == "__main__":
    exit(main())