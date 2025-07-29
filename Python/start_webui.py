"""
Kassia WebUI Starter
Enhanced startup script for the web interface
"""

import sys
import os
import asyncio
import uvicorn
import webbrowser
from pathlib import Path
from datetime import datetime
import argparse

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_prerequisites():
    """Check if system meets requirements for WebUI."""
    print("🔍 Checking WebUI prerequisites...")
    
    # Check Python version
    if sys.version_info < (3, 11):
        print(f"⚠️  Python 3.11+ recommended. Current: {sys.version}")
    else:
        print(f"✅ Python version: {sys.version}")
    
    # Check if running on Windows
    if os.name != 'nt':
        print("⚠️  This tool is designed for Windows systems")
    else:
        print("✅ Windows system detected")
    
    # Check admin privileges
    try:
        is_admin = os.access(os.sep, os.W_OK)
        if is_admin:
            print("✅ Administrator privileges detected")
        else:
            print("⚠️  Administrator privileges recommended for WIM operations")
    except:
        print("⚠️  Could not check administrator privileges")
    
    # Check required directories
    required_dirs = [
        "config",
        "config/device_configs", 
        "assets",
        "assets/sbi",
        "assets/drivers",
        "assets/updates",
        "assets/yunona",
        "runtime",
        "web/templates",
        "web/static"
    ]
    
    missing_dirs = []
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            missing_dirs.append(dir_path)
        else:
            print(f"✅ Directory exists: {dir_path}")
    
    if missing_dirs:
        print("⚠️  Missing directories:")
        for dir_path in missing_dirs:
            print(f"   - {dir_path}")
        
        create_dirs = input("Create missing directories? (y/N): ").lower() == 'y'
        if create_dirs:
            for dir_path in missing_dirs:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
                print(f"✅ Created: {dir_path}")
    
    # Check configuration files
    config_files = [
        "config/config.json",
        "web/templates/index.html"
    ]
    
    for config_file in config_files:
        if Path(config_file).exists():
            print(f"✅ Configuration file exists: {config_file}")
        else:
            print(f"❌ Missing configuration file: {config_file}")
    
    print()

def create_basic_template():
    """Create basic HTML template if missing."""
    template_path = Path("web/templates/index.html")
    
    if template_path.exists():
        return
    
    print("📄 Creating basic HTML template...")
    template_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Use the complete WebUI HTML we created above
    basic_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kassia - Windows Image Preparation System</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <div class="container-fluid p-4">
        <div class="text-center">
            <h1><i class="fas fa-cogs"></i> Kassia WebUI</h1>
            <p>Windows Image Preparation System - Web Edition</p>
            <div class="alert alert-info">
                WebUI is starting up... Please wait.
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>'''
    
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(basic_template)
    
    print(f"✅ Created basic template: {template_path}")

def setup_static_files():
    """Setup static files directory."""
    static_dir = Path("web/static")
    static_dir.mkdir(parents=True, exist_ok=True)
    
    # Create basic CSS file
    css_file = static_dir / "style.css"
    if not css_file.exists():
        css_content = """/* Kassia WebUI Custom Styles */
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .main-container { background: rgba(255,255,255,0.95); border-radius: 20px; }
        """
        with open(css_file, 'w') as f:
            f.write(css_content)
        print(f"✅ Created CSS file: {css_file}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Kassia WebUI Starter')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    parser.add_argument('--no-browser', action='store_true', help='Don\'t open browser automatically')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    print("🌐 Kassia WebUI Starter")
    print("=" * 50)
    print(f"🕒 Startup time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check prerequisites
    check_prerequisites()
    
    # Setup files
    create_basic_template()
    setup_static_files()
    
    print("🚀 Starting WebUI Server...")
    print("=" * 50)
    print(f"📊 Dashboard: http://{args.host}:{args.port}")
    print(f"📋 API Docs: http://{args.host}:{args.port}/docs")
    print(f"🔧 Debug Mode: {'Enabled' if args.debug else 'Disabled'}")
    print(f"🔄 Auto-reload: {'Enabled' if args.reload else 'Disabled'}")
    print("=" * 50)
    
    # Open browser
    if not args.no_browser:
        def open_browser():
            import time
            time.sleep(2)  # Wait for server to start
            webbrowser.open(f"http://localhost:{args.port}")
        
        import threading
        threading.Thread(target=open_browser, daemon=True).start()
    
    # Import and start the web application
    try:
        from web.app import app
        
        # Configure uvicorn
        config = uvicorn.Config(
            app,
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="debug" if args.debug else "info",
            access_log=args.debug
        )
        
        server = uvicorn.Server(config)
        server.run()
        
    except KeyboardInterrupt:
        print("\n🛑 WebUI stopped by user")
    except Exception as e:
        print(f"\n❌ WebUI failed to start: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())