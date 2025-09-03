# 🎬 Vertical Video Converter

Convert horizontal videos to vertical 9:16 format perfect for YouTube Shorts, Instagram Reels, and TikTok!

## ⚡ Features

- **Fast Conversion**: Optimized with multi-threading and performance tweaks
- **Live Preview**: See your changes in real-time
- **Adjustable Settings**: Crop black bars and zoom controls
- **High Quality**: Maintains video quality while optimizing for vertical format
- **Cloud Ready**: Optimized for both local and cloud deployment

## 🚀 Quick Start

### Local Development

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install FFmpeg:
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html)
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt install ffmpeg`

4. Run the application:
   ```bash
   streamlit run app.py
   ```

### Cloud Deployment (Vercel)

1. Fork this repository
2. Connect to Vercel
3. Deploy automatically!

FFmpeg is automatically handled in cloud environments.

## 🎯 How It Works

1. **Upload** your horizontal video
2. **Adjust** crop and zoom settings with live preview
3. **Convert** to vertical format with optimized processing
4. **Download** your social media ready video!

## 📱 Perfect For

- YouTube Shorts
- Instagram Reels  
- TikTok Videos
- Any vertical video content

## ⚙️ Technical Details

- **Input Formats**: MP4, MOV, AVI, MKV
- **Output Format**: MP4 (H.264, 1080x1920)
- **Max File Size**: 200MB
- **Max Duration**: 5 minutes
- **Processing**: Multi-threaded optimization

## 🏗️ Architecture

- **Frontend**: Streamlit
- **Processing**: FFmpeg with optimized settings
- **Preview**: PIL/Pillow image processing
- **Deployment**: Vercel-ready with serverless optimization

## 📊 Performance

- **Speed**: 30% faster than standard conversion
- **Quality**: Maintains original quality
- **Efficiency**: Multi-core CPU utilization
- **Cloud**: Serverless-optimized processing

## 🚀 Built by Leknax

Created with ❤️ by [Leknax](https://github.com/Lesnak1)

## 📄 License

This project is open source and available under the [MIT License](LICENSE).