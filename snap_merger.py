import os
import shutil
import subprocess
import threading
import json
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image
import pywintypes
import win32file
import win32con
import piexif
from datetime import datetime, timedelta

def create_gps_exif(lat, lon):
    def to_deg_min_sec(decimal_degree):
        is_positive = decimal_degree >= 0
        decimal_degree = abs(decimal_degree)
        degrees = int(decimal_degree)
        minutes = int((decimal_degree - degrees) * 60)
        seconds = round(((decimal_degree - degrees) * 60 - minutes) * 60, 4)
        return is_positive, degrees, minutes, seconds

    lat_pos, lat_deg, lat_min, lat_sec = to_deg_min_sec(lat)
    lon_pos, lon_deg, lon_min, lon_sec = to_deg_min_sec(lon)
    
    lat_ref = "N" if lat_pos else "S"
    lon_ref = "E" if lon_pos else "W"
    
    def to_rational(val):
        return (int(val * 100), 100)
    
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: lat_ref,
        piexif.GPSIFD.GPSLatitude: [(lat_deg, 1), (lat_min, 1), to_rational(lat_sec)],
        piexif.GPSIFD.GPSLongitudeRef: lon_ref,
        piexif.GPSIFD.GPSLongitude: [(lon_deg, 1), (lon_min, 1), to_rational(lon_sec)],
        piexif.GPSIFD.GPSVersionID: (2, 2, 0, 0)
    }
    return gps_ifd

def safe_dump_exif(exif_dict):
    try:
        return piexif.dump(exif_dict)
    except Exception:
        # If original EXIF is corrupted or contains incompatible types (like MakerNote),
        # fallback to dumping ONLY the new GPS data.
        fresh_exif = {"0th": {}, "Exif": {}, "GPS": exif_dict.get("GPS", {}), "1st": {}, "thumbnail": None}
        return piexif.dump(fresh_exif)

def extract_iso6709(lat, lon):
    lat_str = f"{lat:08.4f}" if lat < 0 else f"+{lat:07.4f}"
    lon_str = f"{lon:09.4f}" if lon < 0 else f"+{lon:08.4f}"
    return f"{lat_str}{lon_str}/"

def parse_location_string(loc_str):
    if not loc_str:
        return None
    match = re.search(r'(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)', loc_str)
    if match:
        return float(match.group(1)), float(match.group(2))
    return None

def parse_json_date(date_str):
    cleaned = date_str.replace(" UTC", "").strip()
    try:
        return datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None

def load_memories_json(folder, json_path_override=None):
    json_path = None
    if json_path_override and os.path.exists(json_path_override):
        json_path = json_path_override
    else:
        for root_dir, _, files in os.walk(folder):
            if "memories_history.json" in files:
                json_path = os.path.join(root_dir, "memories_history.json")
                break
                
    if not json_path:
        return []
        
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        entries = []
        saved_media = data.get("Saved Media", [])
        for entry in saved_media:
            date_str = entry.get("Date", "")
            loc_str = entry.get("Location", "")
            if date_str and loc_str:
                dt = parse_json_date(date_str)
                coords = parse_location_string(loc_str)
                if dt and coords:
                    entries.append({
                        "dt": dt,
                        "lat": coords[0],
                        "lon": coords[1]
                    })
        return entries
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return []

def get_file_datetime(filepath):
    filename = os.path.basename(filepath)
    name, _ = os.path.splitext(filename)
    match = re.search(r'(\d{4}-\d{2}-\d{2})_(\d{2})(\d{2})(\d{2})', name)
    if match:
        date_str = f"{match.group(1)} {match.group(2)}:{match.group(3)}:{match.group(4)}"
        try:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
            
    try:
        stat = os.stat(filepath)
        return datetime.fromtimestamp(stat.st_mtime)
    except Exception:
        return None

def detect_timezone_offset(media_files, json_entries):
    from collections import Counter
    offsets = []
    for filepath in media_files[:50]:
        file_dt = get_file_datetime(filepath)
        if not file_dt:
            continue
        for entry in json_entries:
            json_dt = entry["dt"]
            diff_sec = (file_dt - json_dt).total_seconds()
            offset_hours = round(diff_sec / 3600.0)
            if -12 <= offset_hours <= 14:
                corrected_diff = abs(diff_sec - (offset_hours * 3600.0))
                if corrected_diff < 15:
                    offsets.append(offset_hours)
                    
    if offsets:
        return Counter(offsets).most_common(1)[0][0]
        
    try:
        system_offset = round((datetime.now() - datetime.utcnow()).total_seconds() / 3600.0)
        return system_offset
    except Exception:
        return 0

def find_matching_coords(filepath, json_entries, timezone_offset):
    file_dt = get_file_datetime(filepath)
    if not file_dt or not json_entries:
        return None
        
    best_entry = None
    best_diff = 999999
    
    for entry in json_entries:
        json_dt = entry["dt"]
        shifted_json_dt = json_dt + timedelta(hours=timezone_offset)
        diff_sec = abs((file_dt - shifted_json_dt).total_seconds())
        if diff_sec < 15:
            if diff_sec < best_diff:
                best_diff = diff_sec
                best_entry = entry
                
    if best_entry:
        return best_entry["lat"], best_entry["lon"]
    return None

def copy_timestamps(src, dst):
    """
    Copies access, modification, and creation timestamps from src to dst.
    """
    shutil.copystat(src, dst)
    try:
        handle_src = win32file.CreateFile(
            src,
            win32file.GENERIC_READ,
            win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE | win32file.FILE_SHARE_DELETE,
            None,
            win32file.OPEN_EXISTING,
            win32file.FILE_ATTRIBUTE_NORMAL,
            None
        )
        ctime, atime, mtime = win32file.GetFileTime(handle_src)
        handle_src.Close()

        handle_dst = win32file.CreateFile(
            dst,
            win32file.GENERIC_WRITE,
            win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE | win32file.FILE_SHARE_DELETE,
            None,
            win32file.OPEN_EXISTING,
            win32file.FILE_ATTRIBUTE_NORMAL,
            None
        )
        win32file.SetFileTime(handle_dst, ctime, None, None)
        handle_dst.Close()
    except Exception as e:
        print(f"Failed to copy creation time for {src}: {e}")

class SnapMergerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Snapchat Memory Merger")
        self.root.geometry("650x570")
        self.root.minimum_size = (550, 480)

        # Variables
        self.folder_path = tk.StringVar()
        self.output_folder_path = tk.StringVar()
        self.custom_output_enabled = tk.BooleanVar(value=False)
        self.recursive_scan_enabled = tk.BooleanVar(value=True)
        self.location_enabled = tk.BooleanVar(value=True)
        self.json_file_path = tk.StringVar()
        
        self.progress_var = tk.DoubleVar()
        self.settings_file = "settings.json"
        self.last_input_dir = "/"
        self.last_output_dir = "/"
        self.last_json_dir = "/"
        self.load_settings()

        # Custom Styling
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure custom colors/fonts
        self.style.configure('.', font=('Segoe UI', 10))
        self.style.configure('TButton', font=('Segoe UI', 10, 'bold'), padding=6)
        self.style.configure('Header.TLabel', font=('Segoe UI', 12, 'bold'))
        self.style.configure('Success.TLabel', font=('Segoe UI', 10, 'bold'), foreground='#2e7d32')
        self.style.configure('Error.TLabel', font=('Segoe UI', 10, 'bold'), foreground='#c62828')
        
        # Build GUI
        self._build_ui()

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r") as f:
                    settings = json.load(f)
                    self.last_input_dir = settings.get("last_input_dir", "/")
                    self.last_output_dir = settings.get("last_output_dir", "/")
                    self.last_json_dir = settings.get("last_json_dir", "/")
                    self.recursive_scan_enabled.set(settings.get("recursive_scan_enabled", True))
                    self.location_enabled.set(settings.get("location_enabled", True))
                    self.json_file_path.set(settings.get("json_file_path", ""))
        except Exception:
            pass

    def save_settings(self):
        try:
            settings = {
                "last_input_dir": self.last_input_dir,
                "last_output_dir": self.last_output_dir,
                "last_json_dir": self.last_json_dir,
                "recursive_scan_enabled": self.recursive_scan_enabled.get(),
                "location_enabled": self.location_enabled.get(),
                "json_file_path": self.json_file_path.get()
            }
            with open(self.settings_file, "w") as f:
                json.dump(settings, f)
        except Exception:
            pass

    def _build_ui(self):
        # Main Frame
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title Label
        ttk.Label(frame, text="Snapchat Memory Merger", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 15))

        # Folder Selection Frame (Input)
        path_label_frame = ttk.Frame(frame)
        path_label_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(path_label_frame, text="Select Folder containing Extracted Memories:").pack(side=tk.LEFT)

        path_frame = ttk.Frame(frame)
        path_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.entry_path = ttk.Entry(path_frame, textvariable=self.folder_path, state='readonly')
        self.entry_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.browse_btn = ttk.Button(path_frame, text="Browse Folder", command=self.browse_folder)
        self.browse_btn.pack(side=tk.RIGHT)

        # Recursive Checkbox
        recursive_frame = ttk.Frame(frame)
        recursive_frame.pack(fill=tk.X, pady=(0, 10))
        self.recursive_check = ttk.Checkbutton(
            recursive_frame,
            text="Scan Subfolders Recursively (Finds memories in all child folders)",
            variable=self.recursive_scan_enabled,
            command=self.save_settings
        )
        self.recursive_check.pack(side=tk.LEFT)

        # Output Folder Selection Frame
        output_option_frame = ttk.Frame(frame)
        output_option_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.output_check = ttk.Checkbutton(
            output_option_frame, 
            text="Customize Output Folder (Default: 'Final_Export' inside input folder)", 
            variable=self.custom_output_enabled,
            command=self.toggle_custom_output
        )
        self.output_check.pack(side=tk.LEFT)

        self.output_frame = ttk.Frame(frame)
        self.output_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.entry_output = ttk.Entry(self.output_frame, textvariable=self.output_folder_path, state='readonly')
        self.entry_output.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.browse_output_btn = ttk.Button(self.output_frame, text="Browse Output", command=self.browse_output_folder, state=tk.DISABLED)
        self.browse_output_btn.pack(side=tk.RIGHT)

        # GPS Location Feature Frame
        gps_option_frame = ttk.Frame(frame)
        gps_option_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.gps_check = ttk.Checkbutton(
            gps_option_frame,
            text="Inject GPS Location EXIF (Requires memories_history.json)",
            variable=self.location_enabled,
            command=self.toggle_location_feature
        )
        self.gps_check.pack(side=tk.LEFT)

        self.gps_frame = ttk.Frame(frame)
        self.gps_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.entry_json = ttk.Entry(self.gps_frame, textvariable=self.json_file_path, state='readonly')
        self.entry_json.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.browse_json_btn = ttk.Button(self.gps_frame, text="Select JSON (Optional)", command=self.browse_json_file)
        if not self.location_enabled.get():
            self.browse_json_btn.config(state=tk.DISABLED)
        self.browse_json_btn.pack(side=tk.RIGHT)

        # Action Buttons and Status
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill=tk.X, pady=(0, 15))

        self.start_button = ttk.Button(action_frame, text="Start Processing", command=self.start_processing)
        self.start_button.pack(side=tk.LEFT)

        # Progress Bar and Status Label Frame
        progress_frame = ttk.Frame(frame)
        progress_frame.pack(fill=tk.X, pady=(0, 15))

        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))

        self.status_label = ttk.Label(progress_frame, text="Ready to merge.")
        self.status_label.pack(anchor=tk.W)

        # Terminal / Log Output Area
        terminal_frame = ttk.LabelFrame(frame, text=" Execution Log / Terminal Output ", padding=10)
        terminal_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbar for Text widget
        scrollbar = ttk.Scrollbar(terminal_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(
            terminal_frame, 
            wrap=tk.WORD, 
            background="#1e1e1e", 
            foreground="#e0e0e0", 
            insertbackground="white",
            font=("Consolas", 10), 
            yscrollcommand=scrollbar.set,
            borderwidth=0,
            highlightthickness=0
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)

        # Log tags for coloring
        self.log_text.tag_config("info", foreground="#61afef")
        self.log_text.tag_config("success", foreground="#98c379")
        self.log_text.tag_config("warning", foreground="#e5c07b")
        self.log_text.tag_config("error", foreground="#e06c75")
        
        # Initial message
        self.log("System initialized. Select memories directory and click Start.", "info")

    def log(self, message, tag="info"):
        self.root.after(0, self._safe_log, message, tag)

    def _safe_log(self, message, tag):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{tag.upper()}] {message}\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def toggle_custom_output(self):
        if self.custom_output_enabled.get():
            self.browse_output_btn.config(state=tk.NORMAL)
            self.log("Custom output folder enabled.", "info")
        else:
            self.browse_output_btn.config(state=tk.DISABLED)
            self.output_folder_path.set("")
            self.log("Custom output folder disabled. Using default 'Final_Export' inside input folder.", "info")

    def toggle_location_feature(self):
        if self.location_enabled.get():
            self.browse_json_btn.config(state=tk.NORMAL)
            self.log("GPS Location injection enabled.", "info")
        else:
            self.browse_json_btn.config(state=tk.DISABLED)
            self.log("GPS Location injection disabled.", "info")
        self.save_settings()

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select Snapchat Memories Folder", initialdir=self.last_input_dir)
        if folder:
            self.folder_path.set(folder)
            self.last_input_dir = folder
            self.save_settings()
            self.log(f"Selected input directory: {folder}", "info")

    def browse_output_folder(self):
        folder = filedialog.askdirectory(title="Select Custom Output Folder", initialdir=self.last_output_dir)
        if folder:
            self.output_folder_path.set(folder)
            self.last_output_dir = folder
            self.save_settings()
            self.log(f"Selected custom output directory: {folder}", "info")

    def browse_json_file(self):
        file_path = filedialog.askopenfilename(
            title="Select memories_history.json",
            initialdir=self.last_json_dir,
            filetypes=[("JSON files", "*.json")]
        )
        if file_path:
            self.json_file_path.set(file_path)
            self.last_json_dir = os.path.dirname(file_path)
            self.save_settings()
            self.log(f"Selected JSON file: {file_path}", "info")

    def start_processing(self):
        folder = self.folder_path.get()
        if not folder:
            messagebox.showerror("Error", "Please select an input folder first.")
            return

        if self.custom_output_enabled.get() and not self.output_folder_path.get():
            messagebox.showerror("Error", "Please select a custom output folder or disable custom output.")
            return

        self.start_button.config(state=tk.DISABLED)
        self.browse_btn.config(state=tk.DISABLED)
        self.output_check.config(state=tk.DISABLED)
        self.recursive_check.config(state=tk.DISABLED)
        self.browse_output_btn.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.status_label.config(text="Scanning directory...")
        self.log("Starting Snapchat memories scan...", "info")

        # Clear previous logs
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        self.log(f"Target Input Folder: {folder}", "info")
        if self.custom_output_enabled.get():
            self.log(f"Target Output Folder: {self.output_folder_path.get()}", "info")
        else:
            self.log("Target Output Folder: Default 'Final_Export' in Input Folder", "info")

        # Run process in a daemon thread to prevent UI freezing
        thread = threading.Thread(target=self.process_files, args=(folder,), daemon=True)
        thread.start()

    def process_files(self, folder):
        try:
            if self.custom_output_enabled.get():
                output_folder = self.output_folder_path.get()
            else:
                output_folder = os.path.join(folder, "Final_Export")

            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
                self.log(f"Created output folder: {output_folder}", "success")

            json_entries = []
            if self.location_enabled.get():
                self.log("Location injection enabled. Loading memories_history.json...", "info")
                json_entries = load_memories_json(folder, self.json_file_path.get())
                if json_entries:
                    self.log(f"Loaded {len(json_entries)} location entries from memories_history.json.", "success")
                else:
                    self.log("No valid location data found in memories_history.json. Proceeding without GPS data.", "warning")

            # 1. Directory Scanning
            media_files = []
            if self.recursive_scan_enabled.get():
                for root_dir, dirs, files in os.walk(folder):
                    if os.path.abspath(output_folder) == os.path.abspath(root_dir):
                        continue
                    if "Final_Export" in dirs:
                        dirs.remove("Final_Export")
                        
                    for f in files:
                        if f.lower().endswith(('.jpg', '.jpeg', '.mp4')):
                            media_files.append(os.path.join(root_dir, f))
            else:
                media_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.jpeg', '.mp4'))]
                
            total_files = len(media_files)
            
            if total_files == 0:
                self.root.after(0, self.finish_processing, 0, 0, "No media files found.")
                return

            self.log(f"Found {total_files} media files to process.", "info")
            
            # Detect Timezone Offset
            timezone_offset = 0
            if self.location_enabled.get() and json_entries:
                self.log("Detecting timezone offset between files and JSON timestamps...", "info")
                timezone_offset = detect_timezone_offset(media_files, json_entries)
                self.log(f"Detected timezone offset: {timezone_offset:+d} hours", "info")

            merged_count = 0
            copied_count = 0

            for i, filepath in enumerate(media_files):
                self.root.after(0, self.update_status, i + 1, total_files)
                
                dir_name = os.path.dirname(filepath)
                filename = os.path.basename(filepath)
                name, ext = os.path.splitext(filename)
                
                has_overlay = False
                overlay_path = None
                is_main = name.endswith('-main')
                base_name = name[:-5] if is_main else name
                
                if is_main:
                    overlay_filename = f"{base_name}-overlay.png"
                    overlay_path = os.path.join(dir_name, overlay_filename)
                    if os.path.exists(overlay_path):
                        has_overlay = True

                loc_coords = None
                if self.location_enabled.get() and json_entries:
                    loc_coords = find_matching_coords(filepath, json_entries, timezone_offset)
                    if loc_coords:
                        self.log(f"[GPS SUCCESS] Injected ({loc_coords[0]}, {loc_coords[1]}) into {filename}", "success")
                    else:
                        self.log(f"[GPS SKIPPED] No location entry found in JSON for {filename}", "warning")

                out_filename = f"{base_name}{ext}" if (is_main and has_overlay) else filename
                out_filepath = os.path.join(output_folder, out_filename)

                # 2. Merging Pairs
                if has_overlay:
                    if ext.lower() in ('.jpg', '.jpeg'):
                        try:
                            self.log(f"Merging image overlay: {filename} + {overlay_filename}", "info")
                            with Image.open(filepath) as base_img:
                                exif = base_img.info.get('exif')
                                base_img = base_img.convert("RGBA")
                                
                                with Image.open(overlay_path) as overlay_img:
                                    overlay_img = overlay_img.resize(base_img.size, Image.Resampling.LANCZOS)
                                    overlay_img = overlay_img.convert("RGBA")
                                    
                                    merged = Image.alpha_composite(base_img, overlay_img)
                                    merged = merged.convert("RGB")
                                    
                                    exif_bytes = b""
                                    try:
                                        if exif:
                                            exif_dict = piexif.load(exif)
                                        else:
                                            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
                                            
                                        if loc_coords:
                                            exif_dict["GPS"] = create_gps_exif(loc_coords[0], loc_coords[1])
                                            
                                        exif_bytes = safe_dump_exif(exif_dict)
                                    except Exception as e:
                                        self.log(f"EXIF parsing error for {filename}: {e}", "warning")
                                        
                                    if exif_bytes:
                                        merged.save(out_filepath, "JPEG", exif=exif_bytes)
                                    else:
                                        merged.save(out_filepath, "JPEG")
                                        
                            copy_timestamps(filepath, out_filepath)
                            merged_count += 1
                            self.log(f"Successfully merged image: {out_filename}", "success")
                        except Exception as e:
                            self.log(f"Failed to merge image {filename}: {e}", "error")
                            shutil.copy2(filepath, out_filepath)
                            copy_timestamps(filepath, out_filepath)
                            copied_count += 1
                            
                    elif ext.lower() == '.mp4':
                        try:
                            self.log(f"Merging video overlay with FFmpeg: {filename} + {overlay_filename}", "info")
                            cmd = [
                                'ffmpeg', '-y', '-i', filepath, '-i', overlay_path,
                                '-filter_complex', '[1:v][0:v]scale2ref[ovrl][base];[base][ovrl]overlay=0:0[v]',
                                '-map', '[v]',
                                '-map', '0:a?',
                                '-c:v', 'libx264',
                                '-pix_fmt', 'yuv420p',
                                '-c:a', 'copy'
                            ]
                            
                            if loc_coords:
                                iso_loc = extract_iso6709(loc_coords[0], loc_coords[1])
                                cmd.extend(['-metadata', f'location={iso_loc}'])
                                
                            cmd.append(out_filepath)
                            
                            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                            if result.returncode != 0:
                                error_msg = result.stderr.strip()
                                last_lines = '\n'.join(error_msg.split('\n')[-5:])
                                raise Exception(f"FFmpeg Error: {last_lines}")
                                
                            copy_timestamps(filepath, out_filepath)
                            merged_count += 1
                            self.log(f"Successfully merged video: {out_filename}", "success")
                        except Exception as e:
                            self.log(f"Failed to merge video {filename}: {e}", "error")
                            shutil.copy2(filepath, out_filepath)
                            copy_timestamps(filepath, out_filepath)
                            copied_count += 1
                else:
                    # 3. Copying/Saving Standalone Files
                    try:
                        if loc_coords and self.location_enabled.get():
                            if ext.lower() in ('.jpg', '.jpeg'):
                                try:
                                    with Image.open(filepath) as img:
                                        exif_raw = img.info.get('exif')
                                        if exif_raw:
                                            exif_dict = piexif.load(exif_raw)
                                        else:
                                            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
                                            
                                        exif_dict["GPS"] = create_gps_exif(loc_coords[0], loc_coords[1])
                                        exif_bytes = safe_dump_exif(exif_dict)
                                        img.save(out_filepath, "JPEG", exif=exif_bytes)
                                except Exception as e:
                                    self.log(f"EXIF injection error for {filename}: {e}", "warning")
                                    shutil.copy2(filepath, out_filepath)
                            elif ext.lower() == '.mp4':
                                iso_loc = extract_iso6709(loc_coords[0], loc_coords[1])
                                cmd = [
                                    'ffmpeg', '-y', '-i', filepath,
                                    '-c', 'copy',
                                    '-metadata', f'location={iso_loc}',
                                    out_filepath
                                ]
                                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                                if result.returncode != 0:
                                    raise Exception("FFmpeg copy failed")
                            else:
                                shutil.copy2(filepath, out_filepath)
                        else:
                            shutil.copy2(filepath, out_filepath)
                            
                        copy_timestamps(filepath, out_filepath)
                        copied_count += 1
                        self.log(f"Processed standalone file: {filename}", "info")
                    except Exception as e:
                        self.log(f"Error copying file {filename}: {e}", "error")

            self.root.after(0, self.finish_processing, merged_count, copied_count, None)

        except Exception as e:
            self.root.after(0, self.finish_processing, 0, 0, str(e))

    def update_status(self, current, total):
        self.progress_var.set((current / total) * 100)
        self.status_label.config(text=f"Processing {current}/{total}...")

    def finish_processing(self, merged, copied, error_msg):
        self.start_button.config(state=tk.NORMAL)
        self.browse_btn.config(state=tk.NORMAL)
        self.output_check.config(state=tk.NORMAL)
        self.recursive_check.config(state=tk.NORMAL)
        if self.custom_output_enabled.get():
            self.browse_output_btn.config(state=tk.NORMAL)
        self.progress_var.set(100)
        if error_msg:
            self.status_label.config(text="Error occurred.")
            self.log(f"Processing finished with error: {error_msg}", "error")
            messagebox.showerror("Error", f"An error occurred:\n{error_msg}")
        else:
            self.status_label.config(text="Complete!")
            self.log(f"Processing complete! Merged: {merged}, Copied: {copied}", "success")
            messagebox.showinfo(
                "Success", 
                f"Processing complete!\n\nMerged pairs: {merged}\nCopied standalone: {copied}\n\nFiles saved to the output folder."
            )

if __name__ == "__main__":
    root = tk.Tk()
    app = SnapMergerApp(root)
    root.mainloop()
