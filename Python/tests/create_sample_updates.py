"""
Create Sample Update Configurations for Testing
"""

import json
from pathlib import Path
from datetime import datetime

def create_sample_updates():
    """Create sample update configurations for testing."""
    
    print("🔧 Creating sample update configurations...")
    
    # Create updates directory structure
    updates_base = Path("assets/updates")
    
    # Sample updates for different types
    sample_updates = [
        {
            "name": "2025-01 Cumulative Update for Windows 10",
            "version": "KB5034441",
            "type": "msu",
            "filename": "windows10.0-kb5034441-x64.msu",
            "os_support": [10, 21652],
            "reboot": True,
            "order": 100,
            "description": "January 2025 Security and Quality Update"
        },
        {
            "name": "2025-01 Servicing Stack Update", 
            "version": "KB5034440",
            "type": "msu",
            "filename": "windows10.0-kb5034440-x64.msu",
            "os_support": [10, 21652],
            "reboot": False,
            "order": 50,  # Install before cumulative updates
            "description": "Servicing Stack Update - Install First"
        },
        {
            "name": "Visual C++ 2022 Redistributable",
            "version": "14.38.33135",
            "type": "exe",
            "filename": "VC_redist.x64.exe",
            "os_support": [10, 21652, 21656],
            "reboot": False,
            "order": 200,
            "description": "Microsoft Visual C++ 2022 Redistributable Package"
        },
        {
            "name": "Microsoft .NET Framework 4.8.1",
            "version": "4.8.1",
            "type": "exe", 
            "filename": "ndp481-x86-x64-allos-enu.exe",
            "os_support": [10],
            "reboot": True,
            "order": 150,
            "description": ".NET Framework 4.8.1 Final Release"
        }
    ]
    
    created_configs = []
    
    for update_info in sample_updates:
        # Create directory for this update
        update_dir = updates_base / f"2025-01" / f"{update_info['version']}"
        update_dir.mkdir(parents=True, exist_ok=True)
        
        # Create update configuration JSON
        config = {
            "updateName": update_info["name"],
            "updateVersion": update_info["version"],
            "updateType": update_info["type"],
            "downloadFileName": update_info["filename"],
            "supportedOperatingSystems": update_info["os_support"],
            "rebootRequired": update_info["reboot"],
            "order": update_info["order"],
            "description": update_info["description"],
            "downloadDate": datetime.now().isoformat(),
            "size": 0,  # Will be updated when real file is present
            "manufacturer": "Microsoft Corporation"
        }
        
        # Write configuration file
        config_file = update_dir / f"{update_info['version']}.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        # Create dummy update file for testing
        dummy_file = update_dir / update_info["filename"]
        dummy_content = f"""
This is a dummy {update_info['type'].upper()} file for testing purposes.
Update: {update_info['name']}
Version: {update_info['version']}
Type: {update_info['type']}

In a real scenario, this would be the actual update file downloaded from Microsoft.
For testing, this dummy file allows the update integration system to function.

Created: {datetime.now().isoformat()}
""".strip()
        
        with open(dummy_file, 'w', encoding='utf-8') as f:
            f.write(dummy_content)
        
        created_configs.append({
            'config': config_file,
            'file': dummy_file,
            'info': update_info
        })
        
        print(f"✅ Created: {update_info['name']} [{update_info['type'].upper()}]")
        print(f"   📁 Config: {config_file}")
        print(f"   📄 File: {dummy_file}")
    
    print(f"\n📊 Summary:")
    print(f"   Total Updates: {len(created_configs)}")
    print(f"   MSU Updates: {sum(1 for u in sample_updates if u['type'] == 'msu')}")
    print(f"   EXE Installers: {sum(1 for u in sample_updates if u['type'] == 'exe')}")
    print(f"   High Priority (order < 100): {sum(1 for u in sample_updates if u['order'] < 100)}")
    print(f"   Require Reboot: {sum(1 for u in sample_updates if u['reboot'])}")
    
    return created_configs

def create_readme():
    """Create README for updates directory."""
    
    readme_content = """# Kassia Updates Directory

This directory contains Windows Updates and software packages for integration into WIM images.

## Directory Structure

```
assets/updates/
├── 2025-01/                    # Year-Month grouping
│   ├── KB5034441/              # Update KB number
│   │   ├── KB5034441.json      # Update configuration
│   │   └── windows10.0-kb5034441-x64.msu  # Update file
│   └── KB5034440/
│       ├── KB5034440.json
│       └── windows10.0-kb5034440-x64.msu
└── README.md                   # This file
```

## Update Types

### MSU/CAB Updates (DISM Integration)
- **MSU**: Microsoft Update files (.msu)
- **CAB**: Cabinet files (.cab)
- **Integration**: Directly integrated into WIM via DISM
- **When**: Applied during WIM modification

### EXE/MSI Updates (Yunona Staging)
- **EXE**: Executable installers (.exe)
- **MSI**: Microsoft Installer packages (.msi)
- **Integration**: Staged to Yunona for post-deployment
- **When**: Applied after Windows first boot

## Configuration Format

Each update requires a JSON configuration file:

```json
{
  "updateName": "2025-01 Cumulative Update for Windows 10",
  "updateVersion": "KB5034441",
  "updateType": "msu",
  "downloadFileName": "windows10.0-kb5034441-x64.msu",
  "supportedOperatingSystems": [10, 21652],
  "rebootRequired": true,
  "order": 100,
  "description": "January 2025 Security and Quality Update"
}
```

## Installation Order

Updates are processed by `order` value:
- **1-50**: Prerequisites (Servicing Stack Updates)
- **51-99**: Critical Updates
- **100-199**: Cumulative Updates
- **200+**: Applications and Redistributables

## Testing with Dummy Files

The sample updates created by `create_sample_updates.py` use dummy files for testing.
In production, replace these with real update files from Microsoft Update Catalog.

## Real Update Sources

1. **Microsoft Update Catalog**: https://catalog.update.microsoft.com
2. **Windows Update**: Use WSUS Offline Update
3. **Software Vendors**: Download latest redistributables

## Usage

The update integration system will:
1. Discover all `.json` files in subdirectories
2. Validate OS compatibility
3. Sort by `order` for proper sequence
4. Apply MSU/CAB via DISM to mounted WIM
5. Stage EXE/MSI to Yunona for post-deployment
"""
    
    readme_path = Path("assets/updates/README.md")
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"📚 Created: {readme_path}")

def main():
    """Main function to create sample updates."""
    print("Kassia Update Configuration Creator")
    print("=" * 40)
    
    # Create sample updates
    created_configs = create_sample_updates()
    
    # Create documentation
    create_readme()
    
    print("\n" + "=" * 60)
    print("✅ Sample update configurations created successfully!")
    print("\n💡 Next steps:")
    print("1. Test update discovery:")
    print("   python test_update_integration.py")
    print("2. Run full CLI with updates:")
    print("   python -m app.main --device xX-39A --os-id 10")
    print("3. Replace dummy files with real updates when ready")
    print("\n⚠️  Note: These are dummy files for testing.")
    print("   In production, use real update files from Microsoft.")

if __name__ == "__main__":
    main()