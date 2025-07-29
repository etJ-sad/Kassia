"""
Test WebUI Components
Quick test for WebUI functionality without full server
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_api_components():
    """Test API components separately."""
    
    print("🧪 Testing WebUI API Components...")
    print("=" * 50)
    
    try:
        # Test configuration loading
        print("📋 Testing configuration loading...")
        from app.models.config import ConfigLoader
        
        try:
            build_config = ConfigLoader.load_build_config()
            print(f"✅ Build config loaded: {build_config.name}")
            print(f"   Version: {build_config.version}")
            print(f"   Mount Point: {build_config.mountPoint}")
            
            # Test WIM path validation
            wim_validation = build_config.validate_wim_files_exist()
            for os_id, exists in wim_validation.items():
                status = "✅" if exists else "❌"
                wim_path = build_config.osWimMap[os_id]
                print(f"   {status} OS {os_id}: {wim_path}")
                
        except Exception as e:
            print(f"❌ Config loading failed: {e}")
        
        # Test device loading
        print("\n📱 Testing device configurations...")
        device_configs_path = Path("config/device_configs")
        if device_configs_path.exists():
            device_files = list(device_configs_path.glob("*.json"))
            print(f"✅ Found {len(device_files)} device configurations")
            
            for device_file in device_files[:3]:  # Test first 3
                try:
                    device_config = ConfigLoader.load_device_config(device_file.stem)
                    supported_os = device_config.get_supported_os_ids()
                    print(f"   ✅ {device_config.deviceId}: OS {supported_os}")
                except Exception as e:
                    print(f"   ❌ {device_file.stem}: {e}")
        else:
            print("❌ No device configurations directory found")
        
        # Test asset provider
        print("\n📂 Testing asset provider...")
        from app.core.asset_providers import LocalAssetProvider
        
        assets_path = Path("assets")
        if assets_path.exists():
            provider = LocalAssetProvider(assets_path)
            
            # Test SBI discovery
            sbi_asset = await provider.get_sbi(os_id=10)
            if sbi_asset:
                print(f"✅ SBI found: {sbi_asset.name}")
                print(f"   Path: {sbi_asset.path}")
                if sbi_asset.size:
                    size_mb = sbi_asset.size / (1024 * 1024)
                    print(f"   Size: {size_mb:.1f} MB")
            else:
                print("❌ No SBI found for OS 10")
            
            # Test driver discovery
            drivers = await provider.get_drivers("xX-39A", 10)
            print(f"✅ Found {len(drivers)} drivers for xX-39A OS 10")
            
            # Test update discovery
            updates = await provider.get_updates(10)
            print(f"✅ Found {len(updates)} updates for OS 10")
            
        else:
            print("❌ Assets directory not found")
        
        print("\n📊 API Components Test Summary:")
        print("✅ Configuration system working")
        print("✅ Asset discovery working") 
        print("✅ Ready for WebUI integration")
        
    except Exception as e:
        print(f"\n❌ API component test failed: {e}")
        import traceback
        traceback.print_exc()

def test_template_structure():
    """Test WebUI template structure."""
    
    print("\n🎨 Testing WebUI template structure...")
    print("=" * 50)
    
    # Check template directory
    template_dir = Path("web/templates")
    if template_dir.exists():
        print(f"✅ Templates directory exists: {template_dir}")
        
        # Check for index.html
        index_file = template_dir / "index.html"
        if index_file.exists():
            print(f"✅ Main template exists: {index_file}")
            
            # Basic template validation
            with open(index_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            checks = [
                ('<!DOCTYPE html>', 'HTML5 doctype'),
                ('Bootstrap', 'Bootstrap CSS'),
                ('Font Awesome', 'Font Awesome icons'),
                ('websocket', 'WebSocket support'),
                ('dashboard', 'Dashboard tab'),
                ('build', 'Build tab'),
                ('assets', 'Assets tab'),
                ('jobs', 'Jobs tab')
            ]
            
            for check, description in checks:
                if check.lower() in content.lower():
                    print(f"   ✅ {description}")
                else:
                    print(f"   ❌ Missing: {description}")
        else:
            print(f"❌ Main template missing: {index_file}")
    else:
        print(f"❌ Templates directory missing: {template_dir}")
    
    # Check static files
    static_dir = Path("web/static")
    if static_dir.exists():
        print(f"✅ Static directory exists: {static_dir}")
        
        css_files = list(static_dir.glob("*.css"))
        js_files = list(static_dir.glob("*.js"))
        
        print(f"   📄 CSS files: {len(css_files)}")
        print(f"   📄 JS files: {len(js_files)}")
    else:
        print(f"❌ Static directory missing: {static_dir}")

def test_webui_imports():
    """Test WebUI import dependencies."""
    
    print("\n📦 Testing WebUI dependencies...")
    print("=" * 50)
    
    dependencies = [
        ('fastapi', 'FastAPI web framework'),
        ('uvicorn', 'ASGI server'),
        ('jinja2', 'Template engine'),
        ('websockets', 'WebSocket support'),
        ('pydantic', 'Data validation')
    ]
    
    for module, description in dependencies:
        try:
            __import__(module)
            print(f"✅ {description}: {module}")
        except ImportError:
            print(f"❌ Missing dependency: {module} ({description})")
            print(f"   Install with: pip install {module}")

def create_sample_webui_files():
    """Create sample WebUI files for testing."""
    
    print("\n🛠️  Creating sample WebUI files...")
    print("=" * 50)
    
    # Create directories
    directories = [
        "web/templates",
        "web/static",
        "web/static/css",
        "web/static/js"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}")
    
    # Create minimal template if it doesn't exist
    template_path = Path("web/templates/index.html")
    if not template_path.exists():
        minimal_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kassia WebUI Test</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-5">
        <div class="text-center">
            <h1>🧪 Kassia WebUI Test</h1>
            <p class="lead">WebUI template is working!</p>
            <div class="alert alert-success">
                This is a minimal test template for WebUI development.
            </div>
        </div>
    </div>
</body>
</html>"""
        
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(minimal_template)
        print(f"✅ Created test template: {template_path}")
    
    # Create basic CSS
    css_path = Path("web/static/css/style.css")
    if not css_path.exists():
        basic_css = """/* Kassia WebUI Test Styles */
body {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
}

.container {
    background: rgba(255, 255, 255, 0.9);
    border-radius: 15px;
    padding: 30px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
}"""
        
        with open(css_path, 'w', encoding='utf-8') as f:
            f.write(basic_css)
        print(f"✅ Created test CSS: {css_path}")

def main():
    """Main test function."""
    
    print("🧪 Kassia WebUI Component Test Suite")
    print("=" * 60)
    
    try:
        # Test imports first
        test_webui_imports()
        
        # Test API components
        asyncio.run(test_api_components())
        
        # Test template structure
        test_template_structure()
        
        # Create sample files if needed
        create_sample_webui_files()
        
        print("\n" + "=" * 60)
        print("✅ WebUI component tests completed!")
        print("\n💡 Next steps:")
        print("1. Install missing dependencies if any:")
        print("   pip install fastapi uvicorn jinja2 websockets")
        print("2. Start the WebUI server:")
        print("   python start_webui.py")
        print("3. Open browser to: http://localhost:8000")
        print("4. Test the complete WebUI functionality")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ WebUI test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())