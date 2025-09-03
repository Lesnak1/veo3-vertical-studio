import streamlit as st
import subprocess
import os
import tempfile
import json
from PIL import Image, ImageFilter
import urllib.request
import time

# --- Configuration ---
MAX_FILE_SIZE_MB = 25   # Very conservative for Vercel
MAX_VIDEO_DURATION_SECONDS = 30  # Very short for quick processing

def download_ffmpeg():
    """Download FFmpeg binary if not exists."""
    ffmpeg_path = "/tmp/ffmpeg"
    ffprobe_path = "/tmp/ffprobe"
    
    if os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path):
        return True
        
    try:
        # Download FFmpeg static binaries
        urllib.request.urlretrieve(
            "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/linux-x64", 
            ffmpeg_path
        )
        urllib.request.urlretrieve(
            "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/ffprobe-linux-x64", 
            ffprobe_path
        )
        
        os.chmod(ffmpeg_path, 0o755)
        os.chmod(ffprobe_path, 0o755)
        return True
    except Exception as e:
        st.error(f"Failed to setup video processor: {str(e)}")
        return False

def get_video_info(input_path):
    """Get video information using ffprobe."""
    if not download_ffmpeg():
        return None
        
    cmd = ['/tmp/ffprobe', '-v', 'error', '-select_streams', 'v:0',
           '-show_entries', 'stream=width,height,duration', '-of', 'json', input_path]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        info = json.loads(result.stdout)['streams'][0]
        info['duration'] = float(info['duration'])
        return info
    except:
        return None

def convert_video(input_path, output_path, crop_percent, zoom_level):
    """Convert video to vertical format."""
    if not download_ffmpeg():
        return False, "FFmpeg setup failed"
    
    # Simplified conversion command
    scaled_width = int(1080 * zoom_level)
    
    cmd = [
        '/tmp/ffmpeg', '-i', input_path,
        '-filter_complex',
        f'[0:v]crop=in_w:in_h*(1-2*{crop_percent}):0:in_h*{crop_percent},'
        f'scale={scaled_width}:-1[main];'
        f'[0:v]crop=in_w:in_h*(1-2*{crop_percent}):0:in_h*{crop_percent},'
        f'scale=1080:1920:force_original_aspect_ratio=increase,'
        f'boxblur=10:3,crop=1080:1920[bg];'
        f'[bg][main]overlay=(W-w)/2:(H-h)/2',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '30',
        '-c:a', 'aac', '-b:a', '32k', '-ac', '1',
        '-t', '30',  # Max 30 seconds
        '-y', output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        return result.returncode == 0, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Conversion timeout"
    except Exception as e:
        return False, str(e)

# Streamlit App
st.set_page_config(page_title="VEO3 Vertical Studio", layout="centered")

st.title("🎬 VEO3 Vertical Studio")
st.markdown("**Quick vertical video converter for social media**")

# File uploader
uploaded_file = st.file_uploader(
    "Upload video file", 
    type=['mp4', 'mov'],
    help=f"Max: {MAX_FILE_SIZE_MB}MB, {MAX_VIDEO_DURATION_SECONDS}s"
)

if uploaded_file:
    file_size_mb = uploaded_file.size / (1024 * 1024)
    
    if file_size_mb > MAX_FILE_SIZE_MB:
        st.error(f"File too large: {file_size_mb:.1f}MB")
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save uploaded file
            input_path = os.path.join(temp_dir, "input.mp4")
            with open(input_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Get video info
            info = get_video_info(input_path)
            if not info:
                st.error("Invalid video file")
            elif info['duration'] > MAX_VIDEO_DURATION_SECONDS:
                st.error(f"Video too long: {info['duration']:.0f}s")
            else:
                # Show info
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Resolution", f"{info['width']}x{info['height']}")
                with col2:
                    st.metric("Duration", f"{info['duration']:.1f}s")
                
                # Settings
                crop = st.slider("Crop %", 0.0, 20.0, 5.0, 1.0) / 100.0
                zoom = st.slider("Zoom", 1.0, 1.5, 1.0, 0.1)
                
                # Convert button
                if st.button("Convert to Vertical", type="primary"):
                    output_path = os.path.join(temp_dir, "output.mp4")
                    
                    progress = st.progress(0)
                    progress.progress(20, "Starting conversion...")
                    
                    success, message = convert_video(input_path, output_path, crop, zoom)
                    
                    if success and os.path.exists(output_path):
                        progress.progress(100, "Complete!")
                        
                        # Show result
                        with open(output_path, 'rb') as f:
                            video_bytes = f.read()
                        
                        st.success("✅ Conversion complete!")
                        st.video(video_bytes)
                        st.download_button(
                            "Download Video",
                            video_bytes,
                            "vertical_video.mp4",
                            "video/mp4"
                        )
                    else:
                        st.error(f"Conversion failed: {message}")

# Footer
st.markdown("---")
st.markdown("🚀 [Built by Leknax](https://github.com/Lesnak1)")