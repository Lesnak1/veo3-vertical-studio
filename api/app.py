import streamlit as st
import subprocess
import os
import tempfile
import json
from PIL import Image, ImageFilter
import io
import urllib.request

# --- Configuration ---
MAX_FILE_SIZE_MB = 50   # Further reduced for Hobby plan
MAX_VIDEO_DURATION_SECONDS = 60  # 1 minute for Hobby plan limits

# FFmpeg static binary URL for serverless deployment
FFMPEG_URL = "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/linux-x64"
FFPROBE_URL = "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/ffprobe-linux-x64"

def download_ffmpeg():
    """Download FFmpeg static binary for serverless deployment."""
    if not os.path.exists("/tmp/ffmpeg"):
        try:
            st.info("🔄 Initializing video processor...")
            urllib.request.urlretrieve(FFMPEG_URL, "/tmp/ffmpeg")
            urllib.request.urlretrieve(FFPROBE_URL, "/tmp/ffprobe")
            os.chmod("/tmp/ffmpeg", 0o755)
            os.chmod("/tmp/ffprobe", 0o755)
            return True
        except Exception as e:
            st.error(f"Failed to initialize video processor: {str(e)}")
            return False
    return True

def get_video_info(input_path):
    """Uses ffprobe to get video stream information."""
    if not download_ffmpeg():
        return None
        
    command = [
        '/tmp/ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,duration', '-of', 'json', input_path
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
        info = json.loads(result.stdout)['streams'][0]
        if all(k in info for k in ['width', 'height', 'duration']):
            info['duration'] = float(info['duration'])
            return info
        return None
    except Exception:
        return None

def extract_frame(input_path, temp_dir):
    """Extracts a single frame from the middle of the video."""
    if not download_ffmpeg():
        return None
        
    frame_output_path = os.path.join(temp_dir, "preview_frame.jpg")
    command = [
        '/tmp/ffmpeg', '-i', input_path, '-ss', '00:00:01.000',
        '-vframes', '1', '-q:v', '2', frame_output_path, '-y'
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        return Image.open(frame_output_path)
    except Exception:
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
    
    if cropped_image.height == 0:
        return None

    # --- Create the blurred background ---
    canvas_width = 1080
    canvas_height = 1920
    
    bg_image = cropped_image.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)
    bg_image = bg_image.filter(ImageFilter.GaussianBlur(20))

    # --- Create the foreground ---
    cropped_aspect_ratio = cropped_image.width / cropped_image.height
    base_fg_width = canvas_width
    base_fg_height = int(base_fg_width / cropped_aspect_ratio)

    zoomed_fg_width = int(base_fg_width * zoom_level)
    zoomed_fg_height = int(base_fg_height * zoom_level)
    
    resized_main = cropped_image.resize((zoomed_fg_width, zoomed_fg_height), Image.Resampling.LANCZOS)

    # --- Combine foreground and background ---
    paste_x = (canvas_width - zoomed_fg_width) // 2
    paste_y = (canvas_height - zoomed_fg_height) // 2
    
    bg_image.paste(resized_main, (paste_x, paste_y), resized_main if resized_main.mode == 'RGBA' else None)
    
    return bg_image

def convert_to_vertical(input_path, output_path, crop_percent, zoom_level, progress_bar):
    """Converts a horizontal video to a 9:16 vertical format (Serverless optimized)."""
    if not download_ffmpeg():
        return False, "Failed to initialize video processor"
        
    output_width = 1080
    output_height = 1920
    scaled_main_width = int(output_width * zoom_level)
    
    cmd = [
        '/tmp/ffmpeg', 
        '-i', input_path,
        '-threads', '2',  # Limited threads for serverless
        '-preset', 'ultrafast',
        '-filter_complex',
        f'[0:v]crop=in_w:in_h*(1-2*{crop_percent}):0:in_h*{crop_percent},scale={scaled_main_width}:-1:flags=fast_bilinear[main];'
        f'[0:v]crop=in_w:in_h*(1-2*{crop_percent}):0:in_h*{crop_percent},scale={output_width}:{output_height}:force_original_aspect_ratio=increase:flags=fast_bilinear,boxblur=15:5,crop={output_width}:{output_height}[bg];'
        '[bg][main]overlay=(W-w)/2:(H-h)/2',
        '-c:v', 'libx264',
        '-crf', '28',  # Higher CRF for faster encoding
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '64k',  # Lower audio bitrate
        '-ac', '2',
        '-movflags', '+faststart',
        '-y', output_path
    ]
    
    progress_bar.progress(10, text="Processing video in cloud...")
    try:
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=50)  # 50 second timeout for Hobby plan
        if process.returncode == 0:
            progress_bar.progress(100, text="Cloud processing complete!")
            return True, process.stderr
        return False, process.stderr
    except subprocess.TimeoutExpired:
        return False, "Processing timed out (Hobby plan 1 min limit)"
    except Exception as e:
        return False, f"Processing error: {str(e)}"

# --- Streamlit UI ---
st.set_page_config(page_title="🎬 VEO3 Vertical Studio", layout="wide")

st.title("🎬 VEO3 Vertical Studio")
st.markdown("**Cloud-powered vertical video converter for YouTube Shorts, Instagram Reels & TikTok**")

st.info("🌐 **Serverless Mode** - Optimized for fast cloud processing with automatic FFmpeg initialization!")

uploaded_file = st.file_uploader(
    "Choose a video file", type=['mp4', 'mov', 'avi', 'mkv'],
    help=f"Max file size: {MAX_FILE_SIZE_MB}MB. Max duration: {MAX_VIDEO_DURATION_SECONDS} seconds."
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
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.metric("📐 Resolution", f"{video_info['width']}x{video_info['height']}")
                with col_info2:
                    st.metric("⏱️ Duration", f"{video_info['duration']:.1f}s")
                
                # --- Main Layout ---
                col1, col2 = st.columns([1, 1])

                with col1:
                    st.subheader("⚙️ Settings")
                    crop_amount = st.slider(
                        "✂️ Black Bar Removal (%)", 0.0, 25.0, 9.0, 0.1, "%.1f%%",
                        help="Remove black bars from video"
                    )
                    zoom_level = st.slider(
                        "🔎 Zoom Level", 1.0, 2.0, 1.0, 0.05, "%.2fx",
                        help="Zoom into the center"
                    )
                    crop_percent_decimal = crop_amount / 100.0

                    if st.button("✨ Convert to Vertical", type="primary"):
                        output_filename = f"vertical_{os.path.splitext(uploaded_file.name)[0]}.mp4"
                        output_path = os.path.join(temp_dir, output_filename)
                        progress_bar = st.progress(0, text="Initializing cloud processor...")
                        
                        success, ffmpeg_output = convert_to_vertical(
                            input_path, output_path, crop_percent_decimal, zoom_level, progress_bar
                        )

                        if success:
                            st.success("✅ Conversion Complete!")
                            with open(output_path, 'rb') as video_file:
                                video_bytes = video_file.read()
                            st.video(video_bytes)
                            st.download_button(
                                "⬇️ Download Converted Video", video_bytes, output_filename, "video/mp4"
                            )
                        else:
                            st.error("❌ Conversion Failed.")
                            with st.expander("Technical Details"):
                                st.code(ffmpeg_output, language=None)

                with col2:
                    st.subheader("🔍 Live Preview")
                    preview_image = extract_frame(input_path, temp_dir)
                    if preview_image:
                        final_preview = generate_preview(preview_image, crop_percent_decimal, zoom_level)
                        if final_preview:
                            st.image(final_preview, width=300)
                        else:
                            st.warning("Could not generate preview.")
                    else:
                        st.warning("Could not extract preview frame.")

st.markdown("---")

# Footer
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    st.markdown("Made with ❤️ using Streamlit")
with col3:
    st.markdown("🚀 [Built by Leknax](https://github.com/Lesnak1)")