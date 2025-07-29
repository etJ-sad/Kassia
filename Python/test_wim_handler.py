"""
WIM Handler Test Script
Test DISM integration and WIM operations
"""

import asyncio
import sys
from pathlib import Path
import logging

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.wim_handler import WimHandler, WimWorkflow, DismError

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_wim_handler():
    """Test WIM Handler functionality."""
    
    print("🚀 Testing WIM Handler with DISM Integration...")
    print("=" * 60)
    
    # Initialize WIM Handler
    try:
        wim_handler = WimHandler()
        print("✅ WIM Handler initialized successfully")
    except DismError as e:
        print(f"❌ WIM Handler initialization failed: {e}")
        if "not found" in str(e).lower():
            print("   💡 Solution: Ensure DISM is available (run as Administrator)")
        return False
    
    # Find test WIM
    sbi_path = Path("assets/sbi")
    test_wim = None
    
    if sbi_path.exists():
        wim_files = list(sbi_path.glob("*.wim"))
        if wim_files:
            test_wim = wim_files[0]
            print(f"📀 Found test WIM: {test_wim}")
        else:
            print("❌ No WIM files found in assets/sbi/")
            return False
    else:
        print("❌ assets/sbi directory not found")
        return False
    
    # Test 1: Get WIM Info
    print("\n🔍 Test 1: Getting WIM Information...")
    try:
        wim_info = await wim_handler.get_wim_info(test_wim)
        print(f"✅ WIM Info retrieved:")
        print(f"   Name: {wim_info.name}")
        print(f"   Index: {wim_info.index}")
        print(f"   Architecture: {wim_info.architecture}")
        print(f"   Description: {wim_info.description}")
        print(f"   Size: {wim_info.size / (1024*1024):.1f} MB" if wim_info.size else "   Size: Unknown")
    except DismError as e:
        print(f"❌ WIM Info failed: {e}")
        return False
    
    # Test 2: Copy WIM to Temp
    print("\n📁 Test 2: Copying WIM to temporary location...")
    temp_dir = Path("runtime/temp")
    try:
        temp_wim = await wim_handler.copy_wim_to_temp(test_wim, temp_dir)
        print(f"✅ WIM copied successfully to: {temp_wim}")
        
        # Verify copy
        if temp_wim.exists():
            temp_size = temp_wim.stat().st_size
            orig_size = test_wim.stat().st_size
            if temp_size == orig_size:
                print(f"   ✅ Copy verified: {temp_size / (1024*1024):.1f} MB")
            else:
                print(f"   ❌ Copy size mismatch: {temp_size} != {orig_size}")
        
    except DismError as e:
        print(f"❌ WIM copy failed: {e}")
        return False
    
    # Test 3: Mount WIM (if running as admin)
    print("\n🔧 Test 3: Testing WIM Mount (requires admin privileges)...")
    mount_point = Path("runtime/mount")
    mount_info = None
    
    try:
        mount_info = await wim_handler.mount_wim(temp_wim, mount_point)
        print(f"✅ WIM mounted successfully at: {mount_point}")
        print(f"   Mount time: {mount_info.mount_time}")
        print(f"   Read-write: {mount_info.read_write}")
        
        # Verify mount
        windows_dir = mount_point / "Windows"
        if windows_dir.exists():
            print(f"   ✅ Mount verified: Windows directory found")
            
            # List some directories
            try:
                dirs = [d.name for d in mount_point.iterdir() if d.is_dir()][:5]
                print(f"   📁 Mounted directories: {', '.join(dirs)}")
            except:
                pass
        else:
            print(f"   ❌ Mount verification failed: No Windows directory")
            
    except DismError as e:
        print(f"❌ WIM mount failed: {e}")
        if "access" in str(e).lower() or "privilege" in str(e).lower():
            print("   💡 Solution: Run as Administrator for mount operations")
        mount_info = None
    
    # Test 4: Unmount WIM (if mounted)
    if mount_info and mount_info.is_mounted:
        print("\n🔓 Test 4: Unmounting WIM...")
        try:
            success = await wim_handler.unmount_wim(mount_point, commit=False, discard=True)
            if success:
                print("✅ WIM unmounted successfully")
            else:
                print("❌ WIM unmount failed")
        except DismError as e:
            print(f"❌ WIM unmount error: {e}")
    
    # Test 5: Workflow Test (if we have admin)
    print("\n🔄 Test 5: Testing WIM Workflow...")
    workflow = WimWorkflow(wim_handler)
    
    try:
        # Just test the preparation step (doesn't need admin)
        temp_wim_2 = await workflow.prepare_wim_for_modification(test_wim, temp_dir / "workflow")
        print(f"✅ Workflow preparation successful: {temp_wim_2}")
        
        # Cleanup workflow
        await workflow.cleanup_workflow(keep_export=False)
        print("✅ Workflow cleanup completed")
        
    except DismError as e:
        print(f"❌ Workflow test failed: {e}")
    
    # Cleanup
    print("\n🧹 Cleaning up test files...")
    try:
        if temp_wim.exists():
            temp_wim.unlink()
            print("✅ Temporary WIM removed")
        
        # Cleanup any remaining mounts
        cleanup_results = await wim_handler.cleanup_all_mounts(force=True)
        if cleanup_results:
            print(f"✅ Mount cleanup: {cleanup_results}")
        
    except Exception as e:
        print(f"⚠️  Cleanup warning: {e}")
    
    return True

async def test_wim_integration():
    """Test WIM integration with existing assets."""
    
    print("\n" + "=" * 60)
    print("🎯 Testing WIM Integration with Assets...")
    
    # Load our existing asset configuration
    try:
        from app.models.config import ConfigLoader
        from app.core.asset_providers import LocalAssetProvider
        
        # Load config for xX-39A with OS 10
        kassia_config = ConfigLoader.create_kassia_config("xX-39A", 10)
        print(f"✅ Configuration loaded: {kassia_config.device.deviceId}")
        
        # Get SBI asset
        assets_path = Path("assets")
        provider = LocalAssetProvider(assets_path)
        sbi_asset = await provider.get_sbi(10)
        
        if sbi_asset:
            print(f"✅ SBI Asset found: {sbi_asset.name}")
            
            # Test WIM info on real asset
            wim_handler = WimHandler()
            wim_info = await wim_handler.get_wim_info(sbi_asset.path)
            
            print(f"📀 Real Asset WIM Info:")
            print(f"   Name: {wim_info.name}")
            print(f"   Architecture: {wim_info.architecture}")
            print(f"   Size: {wim_info.size / (1024*1024):.1f} MB" if wim_info.size else "   Size: Unknown")
            
            print("✅ WIM Handler successfully integrated with assets!")
            
        else:
            print("❌ No SBI asset found for testing")
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")

def main():
    """Main test function."""
    print("Kassia WIM Handler Test Suite")
    print("=" * 40)
    
    # Check admin privileges
    try:
        import os
        is_admin = os.access(os.sep, os.W_OK)
        print(f"🔐 Administrator privileges: {'✅ Yes' if is_admin else '❌ No'}")
        if not is_admin:
            print("   ⚠️  Some tests may fail without admin privileges")
    except:
        print("🔐 Could not check admin privileges")
    
    # Run tests
    success = True
    
    try:
        # Test basic WIM handler
        success &= asyncio.run(test_wim_handler())
        
        # Test integration with assets
        asyncio.run(test_wim_integration())
        
    except KeyboardInterrupt:
        print("\n❌ Tests cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        return 1
    
    # Summary
    print("\n" + "=" * 60)
    if success:
        print("✅ WIM Handler test suite completed successfully!")
        print("\n💡 Next steps:")
        print("   1. Integrate WIM Handler into CLI")
        print("   2. Add driver integration to mounted WIM")
        print("   3. Add update integration to mounted WIM")
    else:
        print("❌ Some tests failed. Check output above.")
        print("\n💡 Common issues:")
        print("   - Run as Administrator for mount operations")
        print("   - Ensure DISM is available")
        print("   - Check WIM file integrity")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())