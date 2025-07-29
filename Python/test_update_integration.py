"""
Update Integration Test Script
Test update integration functionality with sample updates
"""

import asyncio
import sys
from pathlib import Path
import logging

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.update_integration import UpdateIntegrator, UpdateIntegrationManager
from app.core.asset_providers import LocalAssetProvider
from app.models.config import ConfigLoader

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_update_discovery():
    """Test update discovery with sample configurations."""
    
    print("🔍 Testing Update Discovery...")
    print("=" * 50)
    
    # Load real configuration
    try:
        kassia_config = ConfigLoader.create_kassia_config("xX-39A", 10)
        print(f"✅ Configuration loaded: {kassia_config.device.deviceId}")
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return []
    
    # Discover updates
    assets_path = Path("assets")
    provider = LocalAssetProvider(assets_path)
    
    updates = await provider.get_updates(10)  # OS ID 10
    
    if updates:
        print(f"✅ Found {len(updates)} updates:")
        for i, update in enumerate(updates, 1):
            print(f"   [{i}] {update.name}")
            print(f"       Version: {update.update_version}")
            print(f"       Type: {update.update_type.value.upper()}")
            print(f"       Reboot Required: {update.requires_reboot}")
            print(f"       Order: {update.order}")
            print(f"       Path: {update.path}")
            
            # Quick validation
            is_valid = await provider.validate_asset(update)
            print(f"       Valid: {'✅' if is_valid else '❌'}")
            print()
    else:
        print("❌ No updates found")
        print("\n💡 To create sample updates:")
        print("   python create_sample_updates.py")
    
    return updates

async def test_update_categorization(updates):
    """Test update categorization and ordering."""
    
    print("📋 Testing Update Categorization...")
    print("=" * 50)
    
    if not updates:
        print("❌ No updates to categorize")
        return
    
    # Sort by order (same as integration system)
    sorted_updates = sorted(updates, key=lambda u: u.order)
    
    # Categorize by type and order
    categories = {
        'prerequisites': [],
        'critical': [],
        'cumulative': [],
        'applications': []
    }
    
    for update in sorted_updates:
        if update.order <= 50:
            categories['prerequisites'].append(update)
        elif update.order <= 99:
            categories['critical'].append(update)
        elif update.order <= 199:
            categories['cumulative'].append(update)
        else:
            categories['applications'].append(update)
    
    # Display categorization
    for category, category_updates in categories.items():
        if category_updates:
            print(f"\n📦 {category.title()} Updates:")
            for update in category_updates:
                method = "DISM" if update.update_type.value in ['msu', 'cab'] else "YUNONA"
                reboot = "🔄" if update.requires_reboot else "✅"
                print(f"   {reboot} {update.name} [{update.update_type.value.upper()}] via {method}")
                print(f"      Order: {update.order}, Version: {update.update_version}")
    
    # Show integration summary
    dism_updates = [u for u in updates if u.update_type.value in ['msu', 'cab']]
    yunona_updates = [u for u in updates if u.update_type.value in ['exe', 'msi']]
    reboot_required = [u for u in updates if u.requires_reboot]
    
    print(f"\n📊 Integration Summary:")
    print(f"   Total Updates: {len(updates)}")
    print(f"   DISM Integration (MSU/CAB): {len(dism_updates)}")
    print(f"   Yunona Staging (EXE/MSI): {len(yunona_updates)}")
    print(f"   Require Reboot: {len(reboot_required)}")

async def test_update_integration_simulation(updates):
    """Test update integration simulation."""
    
    print("\n🧪 Testing Update Integration (Simulation)...")
    print("=" * 60)
    
    if not updates:
        print("❌ No updates to test")
        return
    
    # Create mock paths
    mock_mount = Path("runtime/test_mount")
    mock_yunona = Path("assets/yunona")
    
    # Ensure test directories exist
    mock_mount.mkdir(parents=True, exist_ok=True)
    (mock_mount / "Windows").mkdir(exist_ok=True)  # Simulate mounted WIM
    
    # Initialize integrator
    integrator = UpdateIntegrator()
    manager = UpdateIntegrationManager(integrator)
    
    print(f"📦 Simulating integration of {len(updates)} updates...")
    
    # Sort updates by order (as the real system does)
    sorted_updates = sorted(updates, key=lambda u: u.order)
    
    # Simulate each update
    for i, update in enumerate(sorted_updates, 1):
        print(f"\n🔧 Update {i}/{len(updates)}: {update.name}")
        print(f"   Type: {update.update_type.value.upper()}")
        print(f"   Version: {update.update_version}")
        print(f"   Order: {update.order}")
        
        if update.update_type.value in ['msu', 'cab']:
            print(f"   📋 Method: DISM /Add-Package")
            print(f"   🎯 Target: Mounted WIM Image")
            print(f"   ⏱️  Expected: 30-120 seconds")
            
        elif update.update_type.value in ['exe', 'msi']:
            print(f"   📋 Method: Stage to Yunona")
            print(f"   🎯 Target: /Users/Public/Yunona/Updates/")
            print(f"   ⏱️  Expected: 1-5 seconds")
            
        print(f"   🔄 Reboot Required: {'Yes' if update.requires_reboot else 'No'}")
        print(f"   📄 File: {update.path.name}")
        
        # Check if file exists
        if update.path.exists():
            file_size = update.path.stat().st_size
            file_size_kb = file_size / 1024
            print(f"   📊 File Size: {file_size_kb:.1f} KB")
            print(f"   ✅ Status: Ready for integration")
        else:
            print(f"   ❌ Status: File not found")
    
    # Cleanup test directories
    try:
        import shutil
        if mock_mount.exists():
            shutil.rmtree(mock_mount)
        print("\n✅ Test cleanup completed")
    except:
        pass

async def test_script_generation():
    """Test installation script generation."""
    
    print("\n📜 Testing Installation Script Generation...")
    print("=" * 50)
    
    # Test script generation logic
    from app.core.update_integration import UpdateIntegrator
    from app.core.asset_providers import UpdateAsset, UpdateType, AssetType
    from pathlib import Path
    
    integrator = UpdateIntegrator()
    
    # Create sample update assets for testing
    sample_updates = [
        {
            'name': 'Sample EXE Update',
            'type': UpdateType.EXE,
            'path': Path('sample.exe'),
            'version': '1.0.0',
            'reboot': True
        },
        {
            'name': 'Sample MSI Update',
            'type': UpdateType.MSI,
            'path': Path('sample.msi'),
            'version': '2.0.0',
            'reboot': False
        }
    ]
    
    for sample in sample_updates:
        print(f"\n🔧 Generating script for: {sample['name']}")
        
        # Create mock update asset
        mock_update = UpdateAsset(
            name=sample['name'],
            path=sample['path'],
            asset_type=AssetType.UPDATE,
            metadata={},
            update_type=sample['type'],
            update_version=sample['version'],
            requires_reboot=sample['reboot']
        )
        
        if sample['type'] == UpdateType.EXE:
            script = integrator._create_exe_update_script(mock_update)
            print(f"   📄 EXE Installation Script Preview:")
        else:
            script = integrator._create_msi_update_script(mock_update)
            print(f"   📄 MSI Installation Script Preview:")
        
        # Show first 10 lines of script
        script_lines = script.split('\n')
        for line in script_lines[:10]:
            print(f"      {line}")
        
        if len(script_lines) > 10:
            print(f"      ... ({len(script_lines) - 10} more lines)")

def main():
    """Main test function."""
    print("Kassia Update Integration Test Suite")
    print("=" * 50)
    
    async def run_tests():
        """Run all tests."""
        try:
            # Check if updates exist
            updates_dir = Path("assets/updates")
            if not updates_dir.exists() or not any(updates_dir.rglob("*.json")):
                print("⚠️  No update configurations found.")
                print("\n💡 To create sample updates:")
                print("   python create_sample_updates.py")
                print("\nRunning with limited testing...")
                
                # Test script generation only
                await test_script_generation()
                return
            
            # Test 1: Update Discovery
            updates = await test_update_discovery()
            
            # Test 2: Update Categorization
            await test_update_categorization(updates)
            
            # Test 3: Integration Simulation
            await test_update_integration_simulation(updates)
            
            # Test 4: Script Generation
            await test_script_generation()
            
            print("\n" + "=" * 60)
            print("✅ All update integration tests completed!")
            print("\n💡 Next steps:")
            print("1. Run full CLI with update integration:")
            print("   python -m app.main --device xX-39A --os-id 10")
            print("2. Check runtime/export/ for final WIM with updates")
            print("3. Verify Yunona staging in mounted WIM")
            print("4. Replace dummy files with real updates for production")
            
        except Exception as e:
            print(f"\n❌ Test suite failed: {e}")
            import traceback
            traceback.print_exc()
            return 1
    
    return asyncio.run(run_tests()) or 0

if __name__ == "__main__":
    exit(main())