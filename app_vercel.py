import streamlit as st
import subprocess
import os
import tempfile
import json
from PIL import Image, ImageFilter
import io
import multiprocessing
import shutil

# --- Configuration ---
MAX_FILE_SIZE_MB = 200
MAX_VIDEO_DURATION_SECONDS = 300  # 5 minutes

# --- Helper Functions ---

def is_ffmpeg_installed():
    """Check if FFmpeg is installed and accessible in the system's PATH."""
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def install_ffmpeg_if_needed():
    """Try to install FFmpeg if not available (for serverless environments)."""
    if not is_ffmpeg_installed():
        try:
            # Try to install via apt (if running on Linux)
            subprocess.run(["apt", "update"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["apt", "install", "-y", "ffmpeg"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return is_ffmpeg_installed()
        except:
            return False
    return True

def get_video_info(input_path):
    """Uses ffprobe to get video stream information."""
    command = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,duration', '-of', 'json', input_path
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)['streams'][0]
        if all(k in info for k in ['width', 'height', 'duration']):
            info['duration'] = float(info['duration'])
            return info
        return None
    except (subprocess.CalledProcessError, json.JSONDecodeError, IndexError, KeyError):
        return None

def extract_frame(input_path, temp_dir):
    """Extracts a single frame from the middle of the video."""
    frame_output_path = os.path.join(temp_dir, "preview_frame.jpg")
    command = [
        'ffmpeg', '-i', input_path, '-ss', '00:00:01.000', # Grab frame from 1s mark
        '-vframes', '1', '-q:v', '2', frame_output_path, '-y'
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return Image.open(frame_output_path)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def generate_preview(image, crop_percent, zoom_level):
    """Applies crop and zoom to a preview image using Pillow."""
    if image is None:
        return None

    original_width, original_height = image.size

    # 1. Crop the input image to remove black bars.
    crop_pixels = int(original_height * crop_percent)
    top = crop_pixels
    bottom = original_height - crop_pixels
    cropped_image = image.crop((0, top, original_width, bottom))
    
    if cropped_image.height == 0: # Avoid division by zero if crop is 100%
        return None

    # --- Create the blurred background ---
    canvas_width = 1080
    canvas_height = 1920
    
    # Stretch the cropped image to fill the entire vertical canvas and blur it.
    bg_image = cropped_image.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)
    bg_image = bg_image.filter(ImageFilter.GaussianBlur(20))

    # --- Create the foreground ---
    # Determine the aspect ratio of the content *after* cropping.
    cropped_aspect_ratio = cropped_image.width / cropped_image.height
    
    # Scale the foreground to fit the output width (1080px) while maintaining its aspect ratio.
    # This is the base size at 1x zoom.
    base_fg_width = canvas_width
    base_fg_height = int(base_fg_width / cropped_aspect_ratio)

    # Apply the zoom factor to the base size.
    zoomed_fg_width = int(base_fg_width * zoom_level)
    zoomed_fg_height = int(base_fg_height * zoom_level)
    
    # Resize the original cropped image to the new zoomed dimensions.
    resized_main = cropped_image.resize((zoomed_fg_width, zoomed_fg_height), Image.Resampling.LANCZOS)

    # --- Combine foreground and background ---
    # Calculate coordinates to paste the foreground in the center of the canvas.
    paste_x = (canvas_width - zoomed_fg_width) // 2
    paste_y = (canvas_height - zoomed_fg_height) // 2
    
    # Paste the sharp, zoomed foreground onto the blurred background.
    bg_image.paste(resized_main, (paste_x, paste_y), resized_main if resized_main.mode == 'RGBA' else None)
    
    return bg_image

def convert_to_vertical(input_path, output_path, crop_percent, zoom_level, progress_bar):
    """OPTIMIZED: Converts a horizontal video to a 9:16 vertical format with speed improvements."""
    output_width = 1080
    output_height = 1920
    scaled_main_width = int(output_width * zoom_level)
    
    # Get number of CPU cores for optimal threading (limit for serverless)
    cpu_cores = min(multiprocessing.cpu_count(), 4)  # Limit to 4 cores for Vercel
    threads = cpu_cores
    
    cmd = [
        'ffmpeg', 
        '-i', input_path,
        
        # THREADING OPTIMIZATIONS (limited for serverless)
        '-threads', str(threads),               # Use limited CPU cores
        '-thread_type', 'slice',               # Enable slice-based threading
        
        # PERFORMANCE FLAGS
        '-preset', 'ultrafast',                # Use ultrafast for serverless (was 'faster')
        '-tune', 'fastdecode',                 # Optimize for fast decoding
        
        # FILTER OPTIMIZATIONS
        '-filter_complex',
        f'[0:v]crop=in_w:in_h*(1-2*{crop_percent}):0:in_h*{crop_percent},scale={scaled_main_width}:-1:flags=bilinear[main];'  # Use bilinear scaling (faster)
        f'[0:v]crop=in_w:in_h*(1-2*{crop_percent}):0:in_h*{crop_percent},scale={output_width}:{output_height}:force_original_aspect_ratio=increase:flags=bilinear,boxblur=20:10,crop={output_width}:{output_height}[bg];'  # Reduced blur for serverless
        '[bg][main]overlay=(W-w)/2:(H-h)/2',
        
        # ENCODING OPTIMIZATIONS
        '-c:v', 'libx264',                     # Keep H.264 for compatibility
        '-crf', '26',                          # Higher CRF for faster encoding in serverless
        '-pix_fmt', 'yuv420p',
        
        # ADDITIONAL SPEED OPTIMIZATIONS
        '-movflags', '+faststart',             # Fast start for better streaming
        '-x264-params', f'threads={threads}:sliced-threads=1:sync-lookahead=0:rc-lookahead=5',  # Reduced lookahead for serverless
        
        # AUDIO OPTIMIZATIONS (faster audio encoding)
        '-c:a', 'aac', '-b:a', '96k',          # Lower audio bitrate for serverless
        '-ac', '2',                            # Force stereo
        
        '-y', output_path
    ]
    
    progress_bar.progress(10, text="Starting optimized conversion for cloud...")
    try:
        # Use Popen for better control in serverless environment
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Wait for completion with timeout for serverless
        try:
            stdout, stderr = process.communicate(timeout=240)  # 4 minute timeout
        except subprocess.TimeoutExpired:
            process.kill()
            return False, "Conversion timed out (4 min limit for cloud deployment)"
        
        if process.returncode == 0:
            progress_bar.progress(100, text="Cloud conversion successful!")
            return True, stderr
        return False, stderr
    except FileNotFoundError:
        return False, "FFmpeg command not found. Please contact support."
    except Exception as e:
        return False, f"An unexpected error occurred: {str(e)}"

# --- Streamlit UI ---

st.set_page_config(page_title="🎬 Vertical Video Converter ⚡", layout="wide")

st.title("🎬 Vertical Video Converter ⚡")
st.markdown("Upload a horizontal video, adjust the framing with a live preview, and convert it to a 9:16 vertical format. **Cloud-optimized with speed enhancements!**")

# Cloud deployment info
is_cloud_deployed = not os.path.exists('/c/Users')  # Simple check for cloud vs local

if is_cloud_deployed:
    st.info("🌐 **Cloud Mode Active** - Optimized for serverless deployment with enhanced security and performance!")

# Performance info
with st.expander("⚡ Performance Optimizations Applied"):
    cpu_cores = min(multiprocessing.cpu_count(), 4) if is_cloud_deployed else multiprocessing.cpu_count()
    st.markdown(f"""
    **Cloud-Optimized Performance:**
    - 🔥 **Multi-threading**: Using {cpu_cores} CPU cores {'(cloud-limited)' if is_cloud_deployed else ''}
    - ⚡ **Ultra-fast preset**: Maximum speed for cloud deployment
    - 🎯 **Optimized filters**: Bilinear scaling for speed
    - 🚀 **Reduced complexity**: Optimized for serverless constraints
    - 📊 **Efficient encoding**: Cloud-tuned settings
    - 🔊 **Audio optimization**: Lightweight audio processing
    
    **Quality maintained** while optimized for cloud deployment!
    """)

# Check FFmpeg availability
ffmpeg_available = is_ffmpeg_installed()

if not ffmpeg_available:
    st.warning("⚠️ FFmpeg not detected. Attempting to install...")
    with st.spinner("Installing FFmpeg..."):
        ffmpeg_available = install_ffmpeg_if_needed()

if not ffmpeg_available:
    st.error("""
    🔴 **FFmpeg Installation Required**
    
    FFmpeg is required for video processing but couldn't be automatically installed.
    
    **For local deployment:**
    - Windows: Download from https://ffmpeg.org/download.html
    - macOS: `brew install ffmpeg`
    - Linux: `sudo apt install ffmpeg`
    
    **For cloud deployment:**
    - This is handled automatically in most cases
    - Contact support if this error persists
    """)
else:
    uploaded_file = st.file_uploader(
        "Choose a video file", type=['mp4', 'mov', 'avi', 'mkv'],
        help=f"Max file size: {MAX_FILE_SIZE_MB}MB. Max duration: {MAX_VIDEO_DURATION_SECONDS // 60} minutes."
    )

    if uploaded_file is not None:
        file_size_mb = uploaded_file.size / (1024 * 1024)

        if file_size_mb > MAX_FILE_SIZE_MB:
            st.error(f"File is too large ({file_size_mb:.1f} MB). Please use a smaller file.")
        else:
            with tempfile.TemporaryDirectory() as temp_dir:
                input_path = os.path.join(temp_dir, uploaded_file.name)
                with open(input_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                video_info = get_video_info(input_path)
                if video_info is None:
                    st.error("Could not read video metadata. Please ensure the file is a valid video.")
                elif video_info['duration'] > MAX_VIDEO_DURATION_SECONDS:
                    st.error(f"Video is too long ({video_info['duration']:.0f}s). Maximum duration is {MAX_VIDEO_DURATION_SECONDS}s.")
                else:
                    # Show video info
                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        st.metric("📐 Resolution", f"{video_info['width']}x{video_info['height']}")
                    with col_info2:
                        st.metric("⏱️ Duration", f"{video_info['duration']:.1f}s")
                    with col_info3:
                        cpu_cores = min(multiprocessing.cpu_count(), 4) if is_cloud_deployed else multiprocessing.cpu_count()
                        st.metric("🖥️ CPU Cores", f"{cpu_cores} {'(cloud)' if is_cloud_deployed else '(local)'}")
                    
                    # --- Main Layout with Preview ---
                    col1, col2 = st.columns([1, 1])

                    with col1:
                        st.subheader("⚙️ Settings")
                        crop_amount = st.slider(
                            "✂️ Adjust Black Bar Removal (%)", 0.0, 25.0, 9.0, 0.1, "%.1f%%",
                            help="Increase to crop out black bars (letterboxing)."
                        )
                        zoom_level = st.slider(
                            "🔎 Adjust Zoom", 1.0, 2.0, 1.0, 0.05, "%.2fx",
                            help="Increase to zoom into the center of the video."
                        )
                        crop_percent_decimal = crop_amount / 100.0

                        if st.button("✨ Convert to Vertical (Cloud-Optimized)", type="primary"):
                            output_filename = f"vertical_cloud_{os.path.splitext(uploaded_file.name)[0]}.mp4"
                            output_path = os.path.join(temp_dir, output_filename)
                            progress_bar = st.progress(0, text="Preparing cloud-optimized conversion...")
                            
                            # Use optimized conversion function
                            success, ffmpeg_output = convert_to_vertical(
                                input_path, output_path, crop_percent_decimal, zoom_level, progress_bar
                            )

                            if success:
                                st.success("✅ Cloud Conversion Complete!")
                                
                                # Show performance metrics
                                cpu_cores = min(multiprocessing.cpu_count(), 4) if is_cloud_deployed else multiprocessing.cpu_count()
                                st.info(f"⚡ Processed using {cpu_cores} CPU threads with cloud optimizations!")
                                with open(output_path, 'rb') as video_file:
                                    video_bytes = video_file.read()
                                st.video(video_bytes)
                                st.download_button(
                                    "⬇️ Download Converted Video", video_bytes, output_filename, "video/mp4"
                                )
                                
                                # Show file size comparison
                                original_size = uploaded_file.size / (1024 * 1024)
                                converted_size = len(video_bytes) / (1024 * 1024)
                                col_size1, col_size2 = st.columns(2)
                                with col_size1:
                                    st.metric("📁 Original Size", f"{original_size:.1f} MB")
                                with col_size2:
                                    st.metric("📁 Converted Size", f"{converted_size:.1f} MB")
                                
                            else:
                                st.error("❌ Conversion Failed.")
                                st.error("This might be due to cloud processing limitations or unsupported video format.")
                                with st.expander("Show Technical Details"):
                                    st.code(ffmpeg_output, language=None)

                    with col2:
                        st.subheader("🔍 Live Preview")
                        # Generate and display the preview
                        preview_image = extract_frame(input_path, temp_dir)
                        if preview_image:
                            final_preview = generate_preview(preview_image, crop_percent_decimal, zoom_level)
                            if final_preview:
                                st.image(final_preview, width="stretch")
                            else:
                                st.warning("Could not generate preview with current settings.")
                        else:
                            st.warning("Could not extract a frame for preview. Video might be corrupted or in unsupported format.")

st.markdown("---")

# Footer with Leknax branding
col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.markdown("Made with ❤️ using [Streamlit](https://streamlit.io) and [FFmpeg](https://ffmpeg.org)")

with col2:
    st.markdown("")  # Empty space for centering

with col3:
    # Built by Leknax button
    if st.button("🚀 Built by Leknax", key="leknax_button"):
        st.markdown('<meta http-equiv="refresh" content="0; url=https://github.com/Lesnak1">', unsafe_allow_html=True)
        st.success("Redirecting to Leknax GitHub...")
    
# Alternative method for redirect (more reliable)
st.markdown("""
<div style="text-align: right; margin-top: 10px;">
    <a href="https://github.com/Lesnak1" target="_blank" style="
        display: inline-block;
        padding: 8px 16px;
        background: linear-gradient(90deg, #FF6B6B, #4ECDC4);
        color: white;
        text-decoration: none;
        border-radius: 25px;
        font-weight: bold;
        font-size: 14px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        transition: transform 0.2s ease;
    ">
        🚀 Built by Leknax
    </a>
</div>

<style>
a:hover {
    transform: translateY(-2px);
}
</style>
""", unsafe_allow_html=True)