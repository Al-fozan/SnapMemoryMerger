# Snapchat Memory Merger

A simple desktop GUI application built in Python to process and merge exported Snapchat memories. 

When you export memories from Snapchat, overlays (like text, drawings, and stickers) are often saved as separate transparent PNG files alongside their main images or videos. This tool merges these overlays back onto the main files (either images or videos) and saves them in a separate folder, all while preserving the original file metadata (creation, modification, and access times).

![Application Preview](app-preview.png)

## Features

- **Automatic Pair Matching:** Automatically matches main images (`*-main.jpg`/`*-main.mp4`) with their overlay files (`*-overlay.png`).
- **Image Merging:** Combines base images and overlays using `Pillow` while preserving EXIF metadata.
- **Video Merging:** Overlays drawings and text on videos using `FFmpeg`. Handles silent videos cleanly and scales overlays to fit perfectly.
- **Timestamp Preservation:** Retains file access, modification, and creation timestamps (Windows-specific using `pywin32`) from the original files on the merged results.
- **Recursive Scanning:** Easily process multiple split Snapchat export folders at once by selecting their parent folder and scanning all subfolders automatically.
- **Customizable Output:** Choose exactly where you want the merged files to be saved, or use the default `Final_Export` folder.
- **Smart Directory Memory:** The app remembers your last used input and output directories independently across sessions for a faster workflow.
- **Graphical User Interface:** Simple Tkinter-based GUI with progress tracking and an interactive terminal log.

## Prerequisites

- **Python 3.x**
- **FFmpeg** (Required for video merging). You can install it quickly using:
  - **Windows (PowerShell as Admin):** `winget install ffmpeg` (Restart your terminal/IDE after)
  - **macOS:** `brew install ffmpeg`
  - **Linux:** `sudo apt install ffmpeg`

## Installation

1. Clone or download this repository.
2. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```bash
   python snap_merger.py
   ```
2. Click **Browse Folder** and select the folder containing your extracted Snapchat memories (or a parent folder containing multiple export parts).
3. Optionally, check **Scan Subfolders Recursively** to process all child directories at once.
4. Optionally, check **Customize Output Folder** to choose a specific destination for the merged memories.
5. Click **Start Processing**.
6. Monitor the process in the terminal log output at the bottom.
7. The merged and processed files will be output to your specified destination or a `Final_Export` folder by default.
