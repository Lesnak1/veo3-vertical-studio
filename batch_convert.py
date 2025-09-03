#!/usr/bin/env python3
"""
Batch video conversion script for testing multiple video processing
"""
import os
import subprocess
import sys
from pathlib import Path

def convert_to_vertical(input_path, output_path, crop_percent=0.09, zoom_level=1.0):
    """Convert a horizontal video to vertical format."""
    output_width = 1080
    output_height = 1920
    scaled_main_width = int(output_width * zoom_level)

    cmd = [
        'ffmpeg', '-i', input_path, '-filter_complex',
        f'[0:v]crop=in_w:in_h*(1-2*{crop_percent}):0:in_h*{crop_percent},scale={scaled_main_width}:-1[main];'
        f'[0:v]crop=in_w:in_h*(1-2*{crop_percent}):0:in_h*{crop_percent},scale={output_width}:{output_height}:force_original_aspect_ratio=increase,boxblur=40:20,crop={output_width}:{output_height}[bg];'
        '[bg][main]overlay=(W-w)/2:(H-h)/2',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-pix_fmt', 'yuv420p',
        '-y', output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.returncode == 0, result.stderr
    except FileNotFoundError:
        return False, "FFmpeg command not found."
    except Exception as e:
        return False, f"An unexpected error occurred: {str(e)}"

def main():
    # Find all test horizontal videos
    input_files = [f for f in os.listdir('.') if f.startswith('test_horizontal') and f.endswith('.mp4')]
    
    if not input_files:
        print("No test horizontal videos found!")
        return
    
    print(f"Found {len(input_files)} videos to convert:")
    for f in input_files:
        print(f"  - {f}")
    
    print("\nStarting batch conversion...")
    
    success_count = 0
    for i, input_file in enumerate(input_files, 1):
        output_file = f"vertical_batch_{i}.mp4"
        print(f"\n[{i}/{len(input_files)}] Converting {input_file} -> {output_file}")
        
        success, error_msg = convert_to_vertical(input_file, output_file)
        
        if success:
            print(f"[OK] Successfully converted {input_file}")
            success_count += 1
        else:
            print(f"[FAIL] Failed to convert {input_file}: {error_msg}")
    
    print(f"\n[DONE] Batch conversion complete!")
    print(f"[OK] Successfully converted: {success_count}/{len(input_files)} videos")
    
    if success_count < len(input_files):
        print(f"[FAIL] Failed: {len(input_files) - success_count} videos")
        sys.exit(1)

if __name__ == "__main__":
    main()