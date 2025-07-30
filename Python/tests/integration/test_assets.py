"""
Asset Provider Test Script
Quick test for LocalAssetProvider functionality
"""

import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.asset_providers import LocalAssetProvider

async def test_local_asset_provider():
    """Test LocalAssetProvider functionality."""
    
    print("🚀 Testing LocalAssetProvider...")
    print("=" * 50)
    
    # Initialize provider
    assets_path = Path("assets")
    provider = LocalAssetProvider(assets_path)
    
    print(f"📁 Assets path: {assets_path.absolute()}")
    print(f"   Exists: {assets_path.exists()}")
    
    # Test SBI discovery
    print("\n🔍 Testing SBI (System Base Image) discovery...")
    sbi_asset = await provider.get_sbi(os_id=10)
    if sbi_asset:
        print(f"✅ Found SBI: {sbi_asset.name}")
        print(f"   Path: {sbi_asset.path}")
        print(f"   Size: {sbi_asset.size / (1024*1024):.1f} MB" if sbi_asset.size else "   Size: Unknown")
        
        # Validate SBI
        is_valid = await provider.validate_asset(sbi_asset)
        print(f"   Valid: {is_valid}")
    else:
        print("❌ No SBI found for OS ID 10")
        print("   Expected: Place a .wim file in assets/sbi/")
    
    # Test driver discovery
    print("\n🔍 Testing Driver discovery...")
    drivers = await provider.get_drivers(device_family="xX-39A", os_id=10)
    print(f"📦 Found {len(drivers)} drivers")
    
    for i, driver in enumerate(drivers[:3]):  # Show first 3
        print(f"   [{i+1}] {driver.name}")
        print(f"       Type: {driver.driver_type}")
        print(f"       Path: {driver.path}")
        print(f"       Family ID: {driver.family_id}")
        
        # Validate driver
        is_valid = await provider.validate_asset(driver)
        print(f"       Valid: {is_valid}")
    
    if len(drivers) > 3:
        print(f"   ... and {len(drivers) - 3} more")
    
    # Test update discovery
    print("\n🔍 Testing Update discovery...")
    updates = await provider.get_updates(os_id=10)
    print(f"📦 Found {len(updates)} updates")
    
    for i, update in enumerate(updates[:3]):  # Show first 3
        print(f"   [{i+1}] {update.name}")
        print(f"       Type: {update.update_type}")
        print(f"       Version: {update.update_version}")
        print(f"       Path: {update.path}")
        print(f"       Reboot: {update.requires_reboot}")
        
        # Validate update
        is_valid = await provider.validate_asset(update)
        print(f"       Valid: {is_valid}")
    
    if len(updates) > 3:
        print(f"   ... and {len(updates) - 3} more")
    
    # Test Yunona scripts
    print("\n🔍 Testing Yunona scripts discovery...")
    scripts = await provider.get_yunona_scripts()
    print(f"📦 Found {len(scripts)} Yunona scripts")
    
    for script in scripts:
        print(f"   - {script.name} ({script.metadata.get('script_type', 'unknown')})")
        print(f"     Path: {script.path}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Asset Discovery Summary:")
    print(f"   SBI: {'✅' if sbi_asset else '❌'}")
    print(f"   Drivers: {len(drivers)}")
    print(f"   Updates: {len(updates)}")
    print(f"   Yunona Scripts: {len(scripts)}")
    
    # Recommendations
    print("\n💡 To populate assets:")
    print("   1. Place .wim files in assets/sbi/")
    print("   2. Create driver folders with .json configs in assets/drivers/")
    print("   3. Create update folders with .json configs in assets/updates/")
    print("   4. Place scripts in assets/yunona/")


def create_sample_configs():
    """Create sample configuration files for testing."""
    
    print("\n🔧 Creating sample asset configurations...")
    
    # Create sample driver config
    driver_dir = Path("assets/drivers/sample_intel_driver")
    driver_dir.mkdir(parents=True, exist_ok=True)
    
    driver_config = {
        "driverName": "Intel Sample Driver",
        "driverType": "inf",
        "driverFamilyId": 20007,
        "supportedDevices": [1, 19951, 19952],
        "supportedOperatingSystems": [10, 21656],
        "order": 100
    }
    
    with open(driver_dir / "driver.json", 'w') as f:
        import json
        json.dump(driver_config, f, indent=2)
    
    # Create dummy INF file
    (driver_dir / "sample.inf").touch()
    
    # Create sample update config
    update_dir = Path("assets/updates/2025-06/sample_update")
    update_dir.mkdir(parents=True, exist_ok=True)
    
    update_config = {
        "updateName": "Sample Windows Update",
        "updateVersion": "KB5000001",
        "updateType": "msu",
        "downloadFileName": "sample_update.msu",
        "supportedOperatingSystems": [10, 21656],
        "rebootRequired": True,
        "order": 100
    }
    
    with open(update_dir / "update.json", 'w') as f:
        import json
        json.dump(update_config, f, indent=2)
    
    # Create dummy MSU file
    (update_dir / "sample_update.msu").touch()
    
    # Create sample Yunona script
    yunona_dir = Path("assets/yunona")
    yunona_dir.mkdir(parents=True, exist_ok=True)
    
    yunona_script = '''"""
Sample Yunona post-deployment script
"""

print("Hello from Yunona Python script!")
'''
    
    with open(yunona_dir / "sample_script.py", 'w') as f:
        f.write(yunona_script)
    
    print("✅ Sample configurations created!")


if __name__ == "__main__":
    print("Kassia Asset Provider Test")
    print("=" * 30)
    
    # Check if assets directory exists
    if not Path("assets").exists():
        print("📁 Assets directory not found, creating sample structure...")
        create_sample_configs()
    
    # Run tests
    asyncio.run(test_local_asset_provider())