# Web UI

The Web user interface is built with FastAPI and lives in `web/`. It provides translation support, WebSocket based job updates and a dashboard for monitoring build jobs.

Start the server using:

```bash
python start_webui.py
```

By default it listens on port `8000`. The FastAPI Swagger documentation is available at `/docs` once the server is running.
