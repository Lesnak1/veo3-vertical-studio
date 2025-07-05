import streamlit as st
import subprocess
import os
import tempfile
import json
from PIL import Image, ImageFilter
import io

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
    """Converts a horizontal video to a 9:16 vertical format."""
    output_width = 1080
    output_height = 1920
    scaled_main_width = int(output_width * zoom_level)

    cmd = [
        'ffmpeg', '-i', input_path, '-filter_complex',
        f'[0:v]crop=in_w:in_h*(1-2*{crop_percent}):0:in_h*{crop_percent},scale={scaled_main_width}:-1[main];'
        f'[0:v]crop=in_w:in_h*(1-2*{crop_percent}):0:in_h*{crop_percent},scale={output_width}:{output_height}:force_original_aspect_ratio=increase,boxblur=40:20,crop={output_width}:{output_height}[bg];'
        '[bg][main]overlay=(W-w)/2:(H-h)/2',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k', '-y', output_path
    ]
    
    progress_bar.progress(10, text="Starting FFmpeg conversion...")
    try:
        process = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if process.returncode == 0:
            progress_bar.progress(100, text="Conversion successful!")
            return True, process.stderr
        return False, process.stderr
    except FileNotFoundError:
        return False, "FFmpeg command not found."
    except Exception as e:
        return False, f"An unexpected error occurred: {str(e)}"

# --- Streamlit UI ---

st.set_page_config(page_title="Vertical Video Converter", layout="wide")

st.title("🎬 Vertical Video Converter")
st.markdown("Upload a horizontal video, adjust the framing with a live preview, and convert it to a 9:16 vertical format.")

if not is_ffmpeg_installed():
    st.error("🔴 FFmpeg is not installed or not found in your system's PATH.")
else:
    uploaded_file = st.file_uploader(
        "Choose a video file", type=['mp4', 'mov', 'avi', 'mkv'],
        help=f"Max file size: {MAX_FILE_SIZE_MB}MB. Max duration: {MAX_VIDEO_DURATION_SECONDS // 60} minutes."
    )

    if uploaded_file is not None:
        file_size_mb = uploaded_file.size / (1024 * 1024)

        if file_size_mb > MAX_FILE_SIZE_MB:
            st.error(f"File is too large ({file_size_mb:.1f} MB).")
        else:
            with tempfile.TemporaryDirectory() as temp_dir:
                input_path = os.path.join(temp_dir, uploaded_file.name)
                with open(input_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                video_info = get_video_info(input_path)
                if video_info is None:
                    st.error("Could not read video metadata.")
                elif video_info['duration'] > MAX_VIDEO_DURATION_SECONDS:
                    st.error(f"Video is too long ({video_info['duration']:.0f}s).")
                else:
                    # --- Main Layout with Preview ---
                    col1, col2 = st.columns([1, 1])

                    with col1:
                        st.subheader("Settings")
                        crop_amount = st.slider(
                            "✂️ Adjust Black Bar Removal (%)", 0.0, 25.0, 9.0, 0.1, "%.1f%%",
                            help="Increase to crop out black bars (letterboxing)."
                        )
                        zoom_level = st.slider(
                            "🔎 Adjust Zoom", 1.0, 2.0, 1.0, 0.05, "%.2fx",
                            help="Increase to zoom into the center of the video."
                        )
                        crop_percent_decimal = crop_amount / 100.0

                        if st.button("✨ Convert to Vertical", type="primary"):
                            output_filename = f"vertical_{os.path.splitext(uploaded_file.name)[0]}.mp4"
                            output_path = os.path.join(temp_dir, output_filename)
                            progress_bar = st.progress(0, text="Preparing...")
                            
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
                                with st.expander("Show FFmpeg Error Log"):
                                    st.code(ffmpeg_output, language=None)

                    with col2:
                        st.subheader("Live Preview")
                        # Generate and display the preview
                        preview_image = extract_frame(input_path, temp_dir)
                        if preview_image:
                            final_preview = generate_preview(preview_image, crop_percent_decimal, zoom_level)
                            st.image(final_preview, use_container_width=True)
                        else:
                            st.warning("Could not extract a frame for preview.")

st.markdown("---")
st.markdown("Made with ❤️ using [Streamlit](https://streamlit.io) and [FFmpeg](https://ffmpeg.org).")
