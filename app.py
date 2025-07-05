import streamlit as st
import subprocess
import os
import tempfile
import json
import shutil

# --- Configuration ---
MAX_FILE_SIZE_MB = 20
MAX_VIDEO_DURATION_SECONDS = 30  # 30 seconds

# --- Helper Functions ---

def is_ffmpeg_installed():
    """Check if FFmpeg is installed and accessible in the system's PATH."""
    try:
        # The 'nul' or '/dev/null' is used to discard the output
        subprocess.run(
            ["ffmpeg", "-version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def get_video_info(input_path):
    """
    Uses ffprobe to get video stream information (width, height, duration).
    Returns a dictionary with info or None if an error occurs.
    """
    command = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,duration',
        '-of', 'json',
        input_path
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)['streams'][0]
        # Ensure all required keys are present
        if all(k in info for k in ['width', 'height', 'duration']):
            info['duration'] = float(info['duration'])
            return info
        else:
            return None
    except (subprocess.CalledProcessError, json.JSONDecodeError, IndexError, KeyError):
        return None

def convert_to_vertical(input_path, output_path, crop_percent, zoom_level, progress_bar):
    """
    Converts a horizontal video to a 9:16 vertical format with a blurred background.
    
    Args:
        input_path (str): Path to the input video file.
        output_path (str): Path to save the converted video file.
        crop_percent (float): Percentage of the height to crop from top and bottom.
        zoom_level (float): The zoom factor for the main content (1.0 is no zoom).
        progress_bar (st.progress): Streamlit progress bar to update.
        
    Returns:
        bool: True if conversion was successful, False otherwise.
        str: The stderr output from FFmpeg for debugging.
    """
    # Using a more standard 1080x1920 for higher quality output
    output_width = 1080
    output_height = 1920
    
    # Calculate the scaled width for the main content based on the zoom level
    scaled_main_width = int(output_width * zoom_level)

    # FFmpeg command using filter_complex for efficiency
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-filter_complex',
        # Step 1: Create the main content stream [main]
        # Crop the top/bottom, then scale it based on the zoom level.
        f'[0:v]crop=in_w:in_h*(1-2*{crop_percent}):0:in_h*{crop_percent},scale={scaled_main_width}:-1[main];'
        
        # Step 2: Create the blurred background stream [bg]
        # This part is unchanged and creates the full-frame blurred background.
        f'[0:v]crop=in_w:in_h*(1-2*{crop_percent}):0:in_h*{crop_percent},scale={output_width}:{output_height}:force_original_aspect_ratio=increase,boxblur=40:20,crop={output_width}:{output_height}[bg];'
        
        # Step 3: Overlay the (potentially zoomed) main content on top of the background
        '[bg][main]overlay=(W-w)/2:(H-h)/2',
        
        # Video encoding settings
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        
        # Audio settings
        '-c:a', 'aac',
        '-b:a', '192k',
        
        # Overwrite output file
        '-y',
        output_path
    ]
    
    progress_bar.progress(10, text="Starting FFmpeg conversion...")
    
    try:
        process = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if process.returncode == 0:
            progress_bar.progress(100, text="Conversion successful!")
            return True, process.stderr
        else:
            return False, process.stderr
            
    except FileNotFoundError:
        return False, "FFmpeg command not found. Make sure it's installed and in your system's PATH."
    except Exception as e:
        return False, f"An unexpected error occurred: {str(e)}"

# --- Streamlit UI ---

st.set_page_config(page_title="Vertical Video Converter", layout="centered")

st.title("🎬 Vertical Video Converter")
st.markdown("Upload a horizontal video to convert it into a 9:16 vertical format. Adjust cropping and zoom to frame your subject perfectly.")

if not is_ffmpeg_installed():
    st.error("🔴 FFmpeg is not installed or not found in your system's PATH.")
    st.markdown("""
        **Please install FFmpeg to use this app.**
        - **On Windows:** Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add the `bin` folder to your system's PATH.
        - **On macOS (using Homebrew):** `brew install ffmpeg`
        - **On Linux (Debian/Ubuntu):** `sudo apt update && sudo apt install ffmpeg`
    """)
else:
    uploaded_file = st.file_uploader(
        "Choose a video file",
        type=['mp4', 'mov', 'avi', 'mkv'],
        help=f"Max file size: {MAX_FILE_SIZE_MB}MB. Max duration: {MAX_VIDEO_DURATION_SECONDS // 60} minutes."
    )

    st.markdown("---")
    st.subheader("Conversion Settings")

    col1, col2 = st.columns(2)

    with col1:
        crop_amount = st.slider(
            "✂️ Adjust Black Bar Removal (%)",
            min_value=0.0,
            max_value=25.0,
            value=9.0,
            step=0.1,
            format="%.1f%%",
            help="If your video has black bars (letterboxing), increase this to crop them out."
        )

    with col2:
        zoom_level = st.slider(
            "🔎 Adjust Zoom",
            min_value=1.0,  # 1.0 means no zoom
            max_value=2.0,  # 2.0 means 200% zoom
            value=1.0,
            step=0.05,
            format="%.2fx",
            help="Increase to zoom into the center of the video, cropping the sides."
        )
    
    crop_percent_decimal = crop_amount / 100.0

    st.markdown("---")

    if uploaded_file is not None:
        file_size_mb = uploaded_file.size / (1024 * 1024)

        if file_size_mb > MAX_FILE_SIZE_MB:
            st.error(f"File is too large ({file_size_mb:.1f} MB). Maximum size is {MAX_FILE_SIZE_MB} MB.")
        else:
            with tempfile.TemporaryDirectory() as temp_dir:
                input_path = os.path.join(temp_dir, uploaded_file.name)
                output_filename = f"vertical_{os.path.splitext(uploaded_file.name)[0]}.mp4"
                output_path = os.path.join(temp_dir, output_filename)

                with open(input_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                video_info = get_video_info(input_path)

                if video_info is None:
                    st.error("Could not read video metadata. The file might be corrupt or not a valid video.")
                elif video_info['duration'] > MAX_VIDEO_DURATION_SECONDS:
                    st.error(f"Video is too long ({video_info['duration']:.0f}s). Maximum duration is {MAX_VIDEO_DURATION_SECONDS}s.")
                elif video_info['width'] < video_info['height']:
                    st.warning("This video already appears to be in a vertical format. The conversion might produce unexpected results.")
                
                if st.button("✨ Convert to Vertical", type="primary"):
                    progress_bar = st.progress(0, text="Preparing for conversion...")
                    
                    success, ffmpeg_output = convert_to_vertical(
                        input_path, 
                        output_path, 
                        crop_percent_decimal,
                        zoom_level,
                        progress_bar
                    )

                    if success:
                        st.success("✅ Conversion Complete!")
                        
                        with open(output_path, 'rb') as video_file:
                            video_bytes = video_file.read()
                        
                        st.video(video_bytes)
                        
                        st.download_button(
                            label="⬇️ Download Converted Video",
                            data=video_bytes,
                            file_name=output_filename,
                            mime="video/mp4"
                        )
                    else:
                        st.error("❌ Conversion Failed. See details below.")
                        with st.expander("Show FFmpeg Error Log"):
                            st.code(ffmpeg_output, language=None)

# --- Footer ---
st.markdown("---")
st.markdown("Made with ❤️ using [Streamlit](https://streamlit.io) and [FFmpeg](https://ffmpeg.org).")
