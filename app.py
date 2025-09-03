from flask import Flask, render_template_string, request, send_file, jsonify
import subprocess
import os
import tempfile
import json
import urllib.request
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25MB limit

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🎬 VEO3 Vertical Studio</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .upload-area { border: 2px dashed #ccc; padding: 40px; text-align: center; margin: 20px 0; }
        .btn { background: #ff4b4b; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        .btn:hover { background: #ff3333; }
        .progress { width: 100%; height: 20px; background: #f0f0f0; border-radius: 10px; overflow: hidden; margin: 20px 0; }
        .progress-bar { height: 100%; background: #00cc88; transition: width 0.3s ease; }
        .settings { margin: 20px 0; }
        .slider { width: 100%; margin: 10px 0; }
        .footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <h1>🎬 VEO3 Vertical Studio</h1>
    <p><strong>Quick vertical video converter for YouTube Shorts, Instagram Reels & TikTok</strong></p>
    
    <div class="upload-area">
        <input type="file" id="videoFile" accept="video/mp4,video/mov" style="display: none;">
        <div onclick="document.getElementById('videoFile').click()">
            📤 Click to upload video file<br>
            <small>Max: 25MB, 30 seconds</small>
        </div>
    </div>
    
    <div id="videoInfo" style="display: none;">
        <div class="settings">
            <label>✂️ Black Bar Removal: <span id="cropValue">5%</span></label>
            <input type="range" id="cropSlider" class="slider" min="0" max="20" value="5">
            
            <label>🔎 Zoom Level: <span id="zoomValue">1.0x</span></label>
            <input type="range" id="zoomSlider" class="slider" min="10" max="15" value="10">
        </div>
        
        <button class="btn" onclick="convertVideo()">✨ Convert to Vertical</button>
        
        <div id="progress" class="progress" style="display: none;">
            <div id="progressBar" class="progress-bar" style="width: 0%;"></div>
        </div>
        
        <div id="result" style="margin-top: 20px;"></div>
    </div>
    
    <div class="footer">
        🚀 <a href="https://github.com/Lesnak1" target="_blank">Built by Leknax</a>
    </div>

    <script>
        let uploadedFile = null;
        
        document.getElementById('videoFile').addEventListener('change', function(e) {
            uploadedFile = e.target.files[0];
            if (uploadedFile) {
                if (uploadedFile.size > 25 * 1024 * 1024) {
                    alert('File too large! Max 25MB');
                    return;
                }
                document.getElementById('videoInfo').style.display = 'block';
            }
        });
        
        document.getElementById('cropSlider').addEventListener('input', function(e) {
            document.getElementById('cropValue').textContent = e.target.value + '%';
        });
        
        document.getElementById('zoomSlider').addEventListener('input', function(e) {
            document.getElementById('zoomValue').textContent = (e.target.value / 10).toFixed(1) + 'x';
        });
        
        function convertVideo() {
            if (!uploadedFile) return;
            
            const formData = new FormData();
            formData.append('video', uploadedFile);
            formData.append('crop', document.getElementById('cropSlider').value);
            formData.append('zoom', document.getElementById('zoomSlider').value);
            
            document.getElementById('progress').style.display = 'block';
            document.getElementById('progressBar').style.width = '20%';
            
            fetch('/convert', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                document.getElementById('progressBar').style.width = '100%';
                if (response.ok) {
                    return response.blob();
                }
                throw new Error('Conversion failed');
            })
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'vertical_video.mp4';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.getElementById('result').innerHTML = '<p style="color: green;">✅ Conversion complete! Download started.</p>';
            })
            .catch(error => {
                document.getElementById('result').innerHTML = '<p style="color: red;">❌ ' + error.message + '</p>';
            });
        }
    </script>
</body>
</html>
'''

def download_ffmpeg():
    """Download FFmpeg binary."""
    ffmpeg_path = "/tmp/ffmpeg"
    if os.path.exists(ffmpeg_path):
        return True
    
    try:
        urllib.request.urlretrieve(
            "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/linux-x64",
            ffmpeg_path
        )
        os.chmod(ffmpeg_path, 0o755)
        return True
    except:
        return False

def convert_video_file(input_path, output_path, crop_percent, zoom_level):
    """Convert video to vertical format."""
    if not download_ffmpeg():
        return False
    
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
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
        '-c:a', 'aac', '-b:a', '32k', '-t', '30',
        '-y', output_path
    ]
    
    try:
        result = subprocess.run(cmd, timeout=40, capture_output=True)
        return result.returncode == 0
    except:
        return False

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/convert', methods=['POST'])
def convert():
    if 'video' not in request.files:
        return 'No file', 400
    
    file = request.files['video']
    if file.filename == '':
        return 'No file selected', 400
    
    crop = float(request.form.get('crop', 5)) / 100.0
    zoom = float(request.form.get('zoom', 10)) / 10.0
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save input
        input_path = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(input_path)
        
        # Convert
        output_path = os.path.join(temp_dir, 'output.mp4')
        if convert_video_file(input_path, output_path, crop, zoom):
            return send_file(output_path, as_attachment=True, download_name='vertical_video.mp4')
        else:
            return 'Conversion failed', 500

if __name__ == '__main__':
    app.run(debug=True)