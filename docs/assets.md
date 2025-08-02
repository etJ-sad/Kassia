# Assets

All drivers, updates and additional scripts are stored under the `assets/` directory. The layout mirrors the example shown in `assets/updates/README.md`.

Assets are discovered by `app.core.asset_providers.LocalAssetProvider` and represented as `DriverAsset`, `UpdateAsset` or `SBIAsset` objects depending on type.
