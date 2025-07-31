# test_webui_simple.py
"""
Minimal Kassia WebUI for testing
"""

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

app = FastAPI(title="Kassia WebUI Test", version="2.0.0")
templates = Jinja2Templates(directory="web/templates")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy", 
        "message": "Kassia WebUI Test is running",
        "version": "2.0.0"
    }

@app.get("/api/devices")
async def list_devices():
    """Mock device list."""
    return [
        {"device_id": "xX-39A", "supported_os": [10, 21656]},
        {"device_id": "xX-32A", "supported_os": [10, 21656]}
    ]

if __name__ == "__main__":
    import uvicorn
    print("🌐 Starting Kassia WebUI Test...")
    print("📊 Dashboard: http://localhost:8000")
    print("📋 API Health: http://localhost:8000/api/health")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
