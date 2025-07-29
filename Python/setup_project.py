"""
Kassia Project Quick Setup - Windows Edition
"""
import os
from pathlib import Path

def create_structure():
    dirs = [
        "app", "app/core", "app/models", "app/utils", "app/cli", "app/exceptions",
        "web", "web/api", "web/api/v1", "web/static", "web/templates", "web/websocket", 
        "assets", "assets/drivers", "assets/updates", "assets/yunona", "assets/sbi",
        "config", "config/device_configs", "config/ids",
        "runtime", "runtime/temp", "runtime/mount", "runtime/export", "runtime/cache", "runtime/logs",
        "tests", "tests/unit", "tests/integration", "scripts", "docs"
    ]
    
    print("🚀 Creating Kassia project structure...")
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        print(f"✅ {d}/")
    
    # Create __init__.py files
    init_files = [
        "app/__init__.py", "app/core/__init__.py", "app/models/__init__.py", 
        "app/utils/__init__.py", "app/cli/__init__.py", "app/exceptions/__init__.py"
    ]
    
    for f in init_files:
        Path(f).touch()
        print(f"📄 {f}")
    
    print("✅ Project structure created!")

if __name__ == "__main__":
    create_structure()