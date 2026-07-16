import subprocess

# Create fake video (2 seconds, red background)
subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=red:s=720x1280:d=2', '-c:v', 'libx264', 'test-main.mp4'])

# Create fake overlay (transparent with some text or color)
subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=black@0.5:s=720x1280,format=rgba', '-frames:v', '1', 'test-overlay.png'])

# Run the command from snap_merger.py
cmd = [
    'ffmpeg', '-y', '-i', 'test-main.mp4', '-i', 'test-overlay.png',
    '-filter_complex', '[1:v][0:v]scale2ref[ovrl][base];[base][ovrl]overlay=0:0[v]',
    '-map', '[v]',
    '-map', '0:a?',
    '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p',
    '-c:a', 'copy',
    'test_out.mp4'
]

result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
print("Return Code:", result.returncode)
print("FFMPEG STDERR:")
print(result.stderr)

