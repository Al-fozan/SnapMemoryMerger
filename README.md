# Snapchat Memory Merger

A desktop GUI application to process, match, and merge exported Snapchat memories (overlays and base files) while preserving creation/modification timestamps and injecting GPS location data.

[![Download Windows Executable](https://img.shields.io/badge/Download-SnapMemoryMerger_v1.0_(Windows)-brightgreen?style=for-the-badge&logo=windows)](https://github.com/Al-fozan/SnapMemoryMerger/releases/latest/download/SnapMemoryMerger-v1.0-Windows.zip)

> **📥 Direct Download (Windows Portable Package):**  
> **[Download Latest Release (SnapMemoryMerger-v1.0-Windows.zip)](https://github.com/Al-fozan/SnapMemoryMerger/releases/latest/download/SnapMemoryMerger-v1.0-Windows.zip)**  
> *(No Python or extra installation required - simply extract the ZIP and run `SnapMerger.exe`)*

![Merge Process](Merge-Process.png)
![Application Preview](app-preview.png)

## Features

- **Overlay Merging:** Combines base photos (`Pillow`) and videos (`FFmpeg`) with their transparent overlays.
- **GPS Location Injection:** Timezone-aware matching of files to `memories_history.json` to inject GPS metadata.
- **Smart Directory Memory:** Remembers your input, output, and JSON directories.
- **Recursive Scan:** Batch process multiple Snapchat export folders recursively.
- **Metadata Preservation:** Retains original creation/modification timestamps.

## Prerequisites

- **Python 3.x**
- **FFmpeg** (Required for videos). Install quickly via:
  - **Windows:** `winget install ffmpeg` (Restart terminal/IDE after)
  - **macOS:** `brew install ffmpeg`
  - **Linux:** `sudo apt install ffmpeg`

## Installation & Usage

1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Run:
   ```bash
   python snap_merger.py
   ```
3. Select your input folder, customize options (Output folder & optional GPS JSON location), and click **Start Processing**.

## Building Standalone Executable (.exe)

To build a standalone Windows `.exe` application without needing Python installed at runtime:

1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Package into a standalone executable:
   ```bash
   python -m PyInstaller --noconsole --onefile --name SnapMerger snap_merger.py
   ```
3. The compiled application will be created at `dist/SnapMerger.exe`.
