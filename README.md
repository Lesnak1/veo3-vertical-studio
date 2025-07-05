🎬 Vertical Video Converter
A simple web app built with Streamlit to convert horizontal videos into a vertical 9:16 format, perfect for YouTube Shorts, Instagram Reels, and TikTok.

This app takes a standard video, crops out any letterbox bars, and creates a blurred background to fill the vertical frame. You can adjust the cropping and zoom level to perfectly frame your subject.

(Pro-tip: Run the app locally, take a screenshot, and upload it to a site like Imgur to get a URL for this image.)

✨ Features
Upload & Convert: Easily upload .mp4, .mov, and other common video files.

Blurred Background: Automatically generates a blurred, scaled version of your video to serve as a professional-looking background.

Adjustable Crop: Use a slider to remove horizontal black bars (letterboxing).

Adjustable Zoom: Use a slider to zoom in on the main content, cropping the sides for better framing.

Web UI: Simple interface built with Streamlit.

🚀 How to Run Locally
To run this application on your own machine, you'll need Python and FFmpeg installed.

1. Install FFmpeg:

Windows: Download from gyan.dev and add the bin folder to your system's PATH.

macOS: brew install ffmpeg

Linux (Debian/Ubuntu): sudo apt update && sudo apt install ffmpeg

2. Clone the Repository:

git clone [https://github.com/YOUR_USERNAME/vertical-video-converter.git](https://github.com/YOUR_USERNAME/vertical-video-converter.git)
cd vertical-video-converter

3. Install Python Dependencies:

pip install -r requirements.txt

4. Run the Streamlit App:

streamlit run app.py
