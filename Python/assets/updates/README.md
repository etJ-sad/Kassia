# Kassia Updates Directory

This directory contains Windows Updates and software packages for integration into WIM images.

## Setup

Install the required Python dependencies:

```bash
pip install -r requirements.txt
```

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
