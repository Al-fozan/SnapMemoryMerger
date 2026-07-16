import os
import shutil
import subprocess
import threading
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image
import pywintypes
import win32file
import win32con

def copy_timestamps(src, dst):
    """
    Copies access, modification, and creation timestamps from src to dst.
    """
    # Copy permission bits, last access time, last modification time, and flags
    shutil.copystat(src, dst)
    
    # Copy creation time (Windows specific) using pywin32
    try:
        # Get source file creation time
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

        # Set destination file creation time
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
        self.progress_var = tk.DoubleVar()
        self.settings_file = "settings.json"
        self.last_input_dir = "/"
        self.last_output_dir = "/"
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
                    self.recursive_scan_enabled.set(settings.get("recursive_scan_enabled", True))
        except Exception:
            pass

    def save_settings(self):
        try:
            settings = {
                "last_input_dir": self.last_input_dir,
                "last_output_dir": self.last_output_dir,
                "recursive_scan_enabled": self.recursive_scan_enabled.get()
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

            # 1. Directory Scanning
            media_files = []
            if self.recursive_scan_enabled.get():
                for root_dir, dirs, files in os.walk(folder):
                    # Skip the output folder if it is within the scanned directory
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

                out_filename = f"{base_name}{ext}" if (is_main and has_overlay) else filename
                out_filepath = os.path.join(output_folder, out_filename)

                # 2. Merging Pairs
                if has_overlay:
                    if ext.lower() in ('.jpg', '.jpeg'):
                        try:
                            self.log(f"Merging image overlay: {filename} + {overlay_filename}", "info")
                            # Pillow for Image merging
                            with Image.open(filepath) as base_img:
                                exif = base_img.info.get('exif')
                                base_img = base_img.convert("RGBA")
                                
                                with Image.open(overlay_path) as overlay_img:
                                    # Resize overlay to match base image (LANCZOS)
                                    overlay_img = overlay_img.resize(base_img.size, Image.Resampling.LANCZOS)
                                    overlay_img = overlay_img.convert("RGBA")
                                    
                                    merged = Image.alpha_composite(base_img, overlay_img)
                                    merged = merged.convert("RGB")
                                    
                                    # Preserve EXIF data
                                    if exif:
                                        merged.save(out_filepath, "JPEG", exif=exif)
                                    else:
                                        merged.save(out_filepath, "JPEG")
                                        
                            copy_timestamps(filepath, out_filepath)
                            merged_count += 1
                            self.log(f"Successfully merged image: {out_filename}", "success")
                        except Exception as e:
                            self.log(f"Failed to merge image {filename}: {e}", "error")
                            # Fallback: copy base if merge fails
                            shutil.copy2(filepath, out_filepath)
                            copy_timestamps(filepath, out_filepath)
                            copied_count += 1
                            
                    elif ext.lower() == '.mp4':
                        try:
                            self.log(f"Merging video overlay with FFmpeg: {filename} + {overlay_filename}", "info")
                            # FFmpeg for Video merging
                            cmd = [
                                'ffmpeg', '-y', '-i', filepath, '-i', overlay_path,
                                '-filter_complex', '[1:v][0:v]scale2ref[ovrl][base];[base][ovrl]overlay=0:0[v]',
                                '-map', '[v]',
                                '-map', '0:a?',
                                '-c:v', 'libx264',
                                '-pix_fmt', 'yuv420p',
                                '-c:a', 'copy',
                                out_filepath
                            ]
                            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                            if result.returncode != 0:
                                error_msg = result.stderr.strip()
                                # Only keep the last 5 lines to avoid blowing up the UI logs
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
                    # 3. Copying Standalone Files
                    try:
                        shutil.copy2(filepath, out_filepath)
                        copy_timestamps(filepath, out_filepath)
                        copied_count += 1
                        self.log(f"Copied standalone file: {filename}", "info")
                    except Exception as e:
                        self.log(f"Error copying file {filename}: {e}", "error")

            # Notify success
            self.root.after(0, self.finish_processing, merged_count, copied_count, None)

        except Exception as e:
            # Notify error
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

