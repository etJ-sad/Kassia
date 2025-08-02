# Workflow Overview

This page describes how a build request flows through the Kassia system and which libraries are involved.

## High level diagram

```
[Client] -(HTTP)--> [FastAPI WebUI] -(Background Task)-> [Core Modules]
       <-(WebSocket)--                |                |
          Job updates               [WimHandler]     [Integrators]
```

1. **Client** (browser or CLI) sends a build request to `/api/build`.
2. **FastAPI WebUI** creates a job entry in the SQLite database and schedules `execute_build_job_with_logging` as a background task.
3. **Core Modules** perform WIM mounting, driver and update integration using DISM and local assets.
4. Progress and log messages are saved via `app.utils.logging` and streamed back to the client over WebSocket.
5. When the workflow completes, the resulting WIM is exported to `runtime/export` and the job is marked finished in the database.

## Sequence diagram

```
Client -> WebUI (/api/build)
WebUI -> Database : create job
WebUI -> Background Task : execute_build_job_with_logging
Background Task -> WimHandler : mount_wim
Background Task -> DriverIntegrator / UpdateIntegrator : integrate assets
Background Task -> Logging : write logs
Background Task -> Database : update job status
Logging -> WebSocket : send updates
```

## API entry points

- `GET /api/assets` – discover drivers, updates and SBI images for a device
- `POST /api/build` – start a build job
- `GET /api/jobs` – list stored jobs
- `GET /api/jobs/{id}` – retrieve a specific job
- `WebSocket /ws/jobs` – real‑time status updates

## Key Python libraries

- **FastAPI** – HTTP API and WebSocket handling
- **Uvicorn** – ASGI server used by `start_webui.py`
- **Pydantic** – configuration models and validation
- **Click** – command‑line interface in `app/main.py`
- **sqlite3** – persistent job database
- **Jinja2** – HTML templating for the WebUI

