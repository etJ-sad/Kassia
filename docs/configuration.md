# Configuration

Configuration files are stored in the `config/` directory. The main build configuration is `config.json` which maps operating system IDs to WIM files and defines paths used by the build process.

Device specific settings reside in `config/device_configs/*.json`. These describe what OS versions a device supports and which driver families are required.

Configuration models are defined in `app.models.config` using Pydantic. They provide validation helpers like `ConfigLoader.load_build_config()` and `ConfigLoader.load_device_config()`.
