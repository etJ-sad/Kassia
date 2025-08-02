# Architecture

The Python project is organised around a set of reusable modules located in `app/`.

```
app/
├── core/        # WIM handling and asset integration
├── models/      # Configuration models
├── utils/       # Logging and database helpers
├── cli/         # Command‑line interface (entry: main.py)
└── web/         # FastAPI based WebUI
```

High level operations such as driver or update integration are implemented in the `core` package. Runtime and build configuration models live under `models` and are loaded via `ConfigLoader`.

The WebUI is served from `web/` using FastAPI and Jinja2 templates. The CLI entry point (`app/main.py`) provides a command‑line wrapper around the same core functionality.
