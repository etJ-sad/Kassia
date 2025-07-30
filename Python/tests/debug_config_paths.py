"""
Debug Kassia Configuration Paths
Diagnose and fix path configuration issues
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def debug_config_paths():
    """Debug configuration path issues."""
    
    print("🔍 Kassia Configuration Path Debugger")
    print("=" * 60)
    
    # 1. Check config file existence
    config_path = Path("config/config.json")
    print(f"📄 Config file: {config_path}")
    print(f"   Exists: {config_path.exists()}")
    print(f"   Absolute path: {config_path.absolute()}")
    
    if not config_path.exists():
        print("❌ Configuration file not found!")
        return
    
    # 2. Load and display config
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    print(f"\n📋 Configuration loaded:")
    print(f"   Name: {config_data.get('name')}")
    print(f"   Version: {config_data.get('version')}")
    
    # 3. Check OS WIM mapping
    print(f"\n🖥️  OS WIM Mapping:")
    os_wim_map = config_data.get('osWimMap', {})
    
    for os_id, wim_path in os_wim_map.items():
        print(f"   OS {os_id}: {wim_path}")
        
        # Check if path exists
        wim_file = Path(wim_path)
        print(f"      Raw path: {wim_path}")
        print(f"      Resolved path: {wim_file.resolve()}")
        print(f"      Exists: {wim_file.exists()}")
        print(f"      Is file: {wim_file.is_file() if wim_file.exists() else 'N/A'}")
        
        if wim_file.exists():
            size_mb = wim_file.stat().st_size / (1024 * 1024)
            print(f"      Size: {size_mb:.1f} MB")
        else:
            print(f"      ❌ FILE NOT FOUND!")
            
            # Check if directory exists
            parent_dir = wim_file.parent
            print(f"      Parent directory: {parent_dir}")
            print(f"      Parent exists: {parent_dir.exists()}")
            
            if parent_dir.exists():
                print(f"      Files in parent directory:")
                try:
                    for file in parent_dir.iterdir():
                        if file.is_file():
                            print(f"         - {file.name}")
                except Exception as e:
                    print(f"         Error listing files: {e}")
    
    # 4. Check SBI root configuration
    print(f"\n📁 SBI Root Configuration:")
    sbi_root = config_data.get('sbiRoot', 'assets/sbi')
    sbi_path = Path(sbi_root)
    print(f"   Configured: {sbi_root}")
    print(f"   Resolved: {sbi_path.resolve()}")
    print(f"   Exists: {sbi_path.exists()}")
    
    if sbi_path.exists():
        print(f"   Contents:")
        try:
            for item in sbi_path.iterdir():
                if item.is_file():
                    size_mb = item.stat().st_size / (1024 * 1024)
                    print(f"      📄 {item.name} ({size_mb:.1f} MB)")
                elif item.is_dir():
                    print(f"      📁 {item.name}/")
        except Exception as e:
            print(f"      Error listing contents: {e}")
    
    # 5. Test with our fixed configuration loader
    print(f"\n🧪 Testing with Kassia ConfigLoader:")
    try:
        from app.models.config import ConfigLoader
        
        # Test build config loading
        build_config = ConfigLoader.load_build_config()
        print(f"✅ Build config loaded successfully")
        
        # Test WIM path resolution
        for os_id in ['10', '21656']:
            wim_path = build_config.get_wim_path(int(os_id))
            if wim_path:
                print(f"   OS {os_id}: {wim_path}")
                print(f"      Exists: {wim_path.exists()}")
            else:
                print(f"   OS {os_id}: No WIM configured")
        
        # Test WIM file validation
        wim_validation = build_config.validate_wim_files_exist()
        print(f"\n📊 WIM Validation Results:")
        for os_id, exists in wim_validation.items():
            status = "✅" if exists else "❌"
            print(f"   {status} OS {os_id}")
        
    except Exception as e:
        print(f"❌ ConfigLoader test failed: {e}")
        import traceback
        traceback.print_exc()

def suggest_fixes():
    """Suggest fixes for common path issues."""
    
    print(f"\n🛠️  Suggested Fixes:")
    print("=" * 40)
    
    print("1. 📁 Check file location:")
    print("   - Verify WIM file actually exists at D:\\assets\\sbi\\w10_enterprise.wim")
    print("   - Check file permissions (not read-only, accessible)")
    print("   - Ensure no typos in filename")
    
    print("\n2. 🔧 Configuration options:")
    print("   a) Use relative paths (recommended):")
    print("      Change to: \".\\assets\\sbi\\w10_enterprise.wim\"")
    print("   b) Use double backslashes for Windows:")
    print("      Change to: \"D:\\\\assets\\\\sbi\\\\w10_enterprise.wim\"")
    print("   c) Use forward slashes:")
    print("      Change to: \"D:/assets/sbi/w10_enterprise.wim\"")
    
    print("\n3. 📂 Alternative directory structure:")
    print("   - Move WIM files to project directory: .\\assets\\sbi\\")
    print("   - Update config to use relative paths")
    
    print("\n4. 🚀 Quick test commands:")
    print("   # Check if file exists from Python:")
    print("   python -c \"from pathlib import Path; print(Path('D:/assets/sbi/w10_enterprise.wim').exists())\"")
    print("   ")
    print("   # List files in directory:")
    print("   python -c \"from pathlib import Path; [print(f) for f in Path('D:/assets/sbi/').iterdir()]\"")

def create_sample_config():
    """Create a sample configuration with both relative and absolute path examples."""
    
    print(f"\n📝 Creating sample configuration files...")
    
    # Sample config with relative paths
    relative_config = {
        "name": "Kassia Python",
        "version": "2.0.0",
        "mountPoint": ".\\runtime\\mount",
        "tempPath": ".\\runtime\\temp", 
        "exportPath": ".\\runtime\\export",
        "driverRoot": ".\\assets\\drivers",
        "updateRoot": ".\\assets\\updates",
        "yunonaPath": ".\\assets\\yunona",
        "sbiRoot": ".\\assets\\sbi",
        "osWimMap": {
            "10": ".\\assets\\sbi\\w10_enterprise.wim",
            "21656": ".\\assets\\sbi\\w11_enterprise.wim"
        },
        "windowsTools": {
            "dismPath": "C:\\Windows\\System32\\dism.exe",
            "powershellPath": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
        }
    }
    
    # Sample config with absolute paths (Windows)
    absolute_config = {
        "name": "Kassia Python",
        "version": "2.0.0",
        "mountPoint": ".\\runtime\\mount",
        "tempPath": ".\\runtime\\temp", 
        "exportPath": ".\\runtime\\export",
        "driverRoot": ".\\assets\\drivers",
        "updateRoot": ".\\assets\\updates",
        "yunonaPath": ".\\assets\\yunona",
        "sbiRoot": "D:\\assets\\sbi",
        "osWimMap": {
            "10": "D:/assets/sbi/w10_enterprise.wim",
            "21656": "D:/assets/sbi/w11_enterprise.wim"
        },
        "windowsTools": {
            "dismPath": "C:\\Windows\\System32\\dism.exe",
            "powershellPath": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
        }
    }
    
    # Save sample configs
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    # Relative paths version
    relative_path = config_dir / "config_relative_paths.json"
    with open(relative_path, 'w', encoding='utf-8') as f:
        json.dump(relative_config, f, indent=2)
    print(f"✅ Created: {relative_path}")
    
    # Absolute paths version  
    absolute_path = config_dir / "config_absolute_paths.json"
    with open(absolute_path, 'w', encoding='utf-8') as f:
        json.dump(absolute_config, f, indent=2)
    print(f"✅ Created: {absolute_path}")
    
    print(f"\n💡 Usage:")
    print(f"   # Copy your preferred version to config.json:")
    print(f"   copy config\\config_relative_paths.json config\\config.json")
    print(f"   # OR")
    print(f"   copy config\\config_absolute_paths.json config\\config.json")

def interactive_path_fixer():
    """Interactive path configuration fixer."""
    
    print(f"\n🔧 Interactive Path Configuration Fixer")
    print("=" * 50)
    
    # Ask user about their WIM files
    print("Let's find your WIM files...")
    
    # Common locations to check
    common_locations = [
        "D:\\assets\\sbi",
        "C:\\assets\\sbi", 
        ".\\assets\\sbi",
        "D:\\WIM",
        "C:\\WIM"
    ]
    
    found_wims = []
    
    for location in common_locations:
        path = Path(location)
        if path.exists():
            wim_files = list(path.glob("*.wim"))
            if wim_files:
                print(f"📁 Found WIM files in {location}:")
                for wim_file in wim_files:
                    size_mb = wim_file.stat().st_size / (1024 * 1024)
                    print(f"   📄 {wim_file.name} ({size_mb:.1f} MB)")
                    found_wims.append(str(wim_file))
    
    if not found_wims:
        print("❌ No WIM files found in common locations")
        custom_path = input("Enter custom path to search for WIM files: ")
        if custom_path:
            path = Path(custom_path)
            if path.exists():
                wim_files = list(path.glob("*.wim"))
                found_wims.extend([str(f) for f in wim_files])
    
    if found_wims:
        print(f"\n✅ Found {len(found_wims)} WIM files:")
        for i, wim_path in enumerate(found_wims):
            print(f"   [{i}] {wim_path}")
        
        # Ask user to select WIMs for OS mapping
        print(f"\nSelect WIM files for OS mapping:")
        
        try:
            os_10_idx = input("Enter index for OS 10 WIM (or skip): ")
            os_11_idx = input("Enter index for OS 21656 WIM (or skip): ")
            
            new_config = {
                "name": "Kassia Python",
                "version": "2.0.0",
                "mountPoint": ".\\runtime\\mount",
                "tempPath": ".\\runtime\\temp", 
                "exportPath": ".\\runtime\\export",
                "driverRoot": ".\\assets\\drivers",
                "updateRoot": ".\\assets\\updates",
                "yunonaPath": ".\\assets\\yunona",
                "sbiRoot": ".\\assets\\sbi",
                "osWimMap": {},
                "windowsTools": {
                    "dismPath": "C:\\Windows\\System32\\dism.exe",
                    "powershellPath": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
                }
            }
            
            if os_10_idx.isdigit() and 0 <= int(os_10_idx) < len(found_wims):
                new_config["osWimMap"]["10"] = found_wims[int(os_10_idx)].replace("\\", "/")
            
            if os_11_idx.isdigit() and 0 <= int(os_11_idx) < len(found_wims):
                new_config["osWimMap"]["21656"] = found_wims[int(os_11_idx)].replace("\\", "/")
            
            # Save new config
            if new_config["osWimMap"]:
                config_path = Path("config/config.json")
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(new_config, f, indent=2)
                print(f"✅ Updated configuration saved to: {config_path}")
                
                # Test the new configuration
                print(f"\n🧪 Testing new configuration...")
                debug_config_paths()
            else:
                print("❌ No valid WIM files selected")
                
        except Exception as e:
            print(f"❌ Configuration update failed: {e}")
    else:
        print("❌ No WIM files found. Please:")
        print("   1. Ensure WIM files exist")
        print("   2. Check file permissions")
        print("   3. Verify paths are correct")

def main():
    """Main debugging function."""
    
    try:
        debug_config_paths()
        suggest_fixes()
        create_sample_config()
        
        print(f"\n" + "=" * 60)
        
        # Ask if user wants interactive fix
        if input("Run interactive path fixer? (y/N): ").lower() == 'y':
            interactive_path_fixer()
        
        print(f"\n✅ Path debugging completed!")
        
    except Exception as e:
        print(f"❌ Debug script failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())