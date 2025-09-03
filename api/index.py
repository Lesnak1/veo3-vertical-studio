from flask import Flask, render_template_string, request, send_file
import subprocess
import os
import tempfile
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
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f8f9fa; }
        .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .upload-area { border: 2px dashed #007bff; padding: 40px; text-align: center; margin: 20px 0; border-radius: 10px; background: #f8f9ff; cursor: pointer; transition: all 0.3s; }
        .upload-area:hover { border-color: #0056b3; background: #e6f3ff; }
        .btn { background: linear-gradient(45deg, #ff6b6b, #4ecdc4); color: white; padding: 12px 25px; border: none; border-radius: 25px; cursor: pointer; font-weight: bold; transition: transform 0.2s; }
        .btn:hover { transform: translateY(-2px); }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .progress { width: 100%; height: 25px; background: #e9ecef; border-radius: 15px; overflow: hidden; margin: 20px 0; display: none; }
        .progress-bar { height: 100%; background: linear-gradient(45deg, #28a745, #20c997); transition: width 0.3s ease; border-radius: 15px; }
        .settings { margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 10px; }
        .slider-container { margin: 15px 0; }
        .slider { width: 100%; margin: 10px 0; }
        .footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; }
        .success { color: #28a745; font-weight: bold; }
        .error { color: #dc3545; font-weight: bold; }
        .file-info { background: #e8f5e8; padding: 15px; border-radius: 10px; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 VEO3 Vertical Studio</h1>
        <p><strong>Convert horizontal videos to stunning vertical format for YouTube Shorts, Instagram Reels & TikTok</strong></p>
        
        <div class="upload-area" id="uploadArea">
            <input type="file" id="videoFile" accept="video/mp4,video/mov" style="display: none;">
            <div onclick="document.getElementById('videoFile').click()">
                📤 <strong>Click to upload video file</strong><br>
                <small>Max: 25MB, 30 seconds • Supported: MP4, MOV</small>
            </div>
        </div>
        
        <div id="fileInfo" class="file-info" style="display: none;"></div>
        
        <div id="videoSettings" style="display: none;">
            <div class="settings">
                <div class="slider-container">
                    <label><strong>✂️ Black Bar Removal:</strong> <span id="cropValue">5%</span></label>
                    <input type="range" id="cropSlider" class="slider" min="0" max="20" value="5">
                    <small>Remove letterboxing from your video</small>
                </div>
                
                <div class="slider-container">
                    <label><strong>🔎 Zoom Level:</strong> <span id="zoomValue">1.0x</span></label>
                    <input type="range" id="zoomSlider" class="slider" min="10" max="15" value="10">
                    <small>Zoom into the center of your video</small>
                </div>
            </div>
            
            <button class="btn" id="convertBtn" onclick="convertVideo()">✨ Convert to Vertical Format</button>
            
            <div id="progress" class="progress">
                <div id="progressBar" class="progress-bar" style="width: 0%;"></div>
            </div>
            
            <div id="result" style="margin-top: 20px;"></div>
        </div>
    </div>
    
    <div class="footer">
        <p>Made with ❤️ • 🚀 <a href="https://github.com/Lesnak1" target="_blank" style="color: #007bff; text-decoration: none;">Built by Leknax</a></p>
    </div>

    <script>
        let uploadedFile = null;
        
        document.getElementById('videoFile').addEventListener('change', function(e) {
            uploadedFile = e.target.files[0];
            if (uploadedFile) {
                if (uploadedFile.size > 25 * 1024 * 1024) {
                    alert('❌ File too large! Maximum 25MB allowed.');
                    return;
                }
                
                const fileSize = (uploadedFile.size / 1024 / 1024).toFixed(1);
                document.getElementById('fileInfo').innerHTML = 
                    `📁 <strong>${uploadedFile.name}</strong> (${fileSize} MB)`;
                document.getElementById('fileInfo').style.display = 'block';
                document.getElementById('videoSettings').style.display = 'block';
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
            
            document.getElementById('convertBtn').disabled = true;
            document.getElementById('convertBtn').textContent = '🔄 Converting...';
            document.getElementById('progress').style.display = 'block';
            document.getElementById('result').innerHTML = '';
            
            // Animate progress
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += 2;
                if (progress <= 90) {
                    document.getElementById('progressBar').style.width = progress + '%';
                }
            }, 200);
            
            fetch('/api/convert', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                clearInterval(progressInterval);
                document.getElementById('progressBar').style.width = '100%';
                
                if (response.ok) {
                    return response.blob();
                } else {
                    return response.text().then(errorText => {
                        throw new Error(errorText || 'Conversion failed. Please try with a smaller file.');
                    });
                }
            })
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'vertical_video.mp4';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                document.getElementById('result').innerHTML = 
                    '<p class="success">✅ Conversion successful! Your vertical video has been downloaded.</p>';
            })
            .catch(error => {
                document.getElementById('result').innerHTML = 
                    '<p class="error">❌ ' + error.message + '</p>';
            })
            .finally(() => {
                document.getElementById('convertBtn').disabled = false;
                document.getElementById('convertBtn').textContent = '✨ Convert to Vertical Format';
                setTimeout(() => {
                    document.getElementById('progress').style.display = 'none';
                }, 2000);
            });
        }
        
        // Drag and drop functionality
        const uploadArea = document.getElementById('uploadArea');
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, unhighlight, false);
        });
        
        function highlight(e) {
            uploadArea.style.borderColor = '#0056b3';
            uploadArea.style.backgroundColor = '#e6f3ff';
        }
        
        function unhighlight(e) {
            uploadArea.style.borderColor = '#007bff';
            uploadArea.style.backgroundColor = '#f8f9ff';
        }
        
        uploadArea.addEventListener('drop', handleDrop, false);
        
        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            if (files.length > 0) {
                document.getElementById('videoFile').files = files;
                document.getElementById('videoFile').dispatchEvent(new Event('change'));
            }
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
        return False, "FFmpeg download failed"
    
    # Simplified conversion for better compatibility
    cmd = [
        '/tmp/ffmpeg', '-i', input_path,
        '-vf', f'crop=in_w:in_h*{1-2*crop_percent}:0:in_h*{crop_percent},scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '30',
        '-c:a', 'aac', '-b:a', '64k', '-ac', '2',
        '-t', '30',  # Limit to 30 seconds
        '-y', output_path
    ]
    
    try:
        result = subprocess.run(cmd, timeout=40, capture_output=True, text=True)
        if result.returncode == 0:
            return True, "Success"
        else:
            return False, f"FFmpeg error: {result.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return False, "Conversion timeout (40s limit)"
    except Exception as e:
        return False, f"System error: {str(e)}"

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/debug')
def debug():
    """Debug endpoint to check FFmpeg status."""
    ffmpeg_exists = os.path.exists('/tmp/ffmpeg')
    ffmpeg_downloaded = download_ffmpeg()
    
    debug_info = {
        'ffmpeg_exists': ffmpeg_exists,
        'ffmpeg_downloaded': ffmpeg_downloaded,
        'tmp_contents': os.listdir('/tmp') if os.path.exists('/tmp') else 'No /tmp directory'
    }
    
    return debug_info

@app.route('/convert', methods=['POST'])
def convert():
    if 'video' not in request.files:
        return 'No file uploaded', 400
    
    file = request.files['video']
    if file.filename == '':
        return 'No file selected', 400
    
    # Validate file size
    if len(file.read()) > 25 * 1024 * 1024:
        return 'File too large (max 25MB)', 400
    file.seek(0)  # Reset file pointer
    
    crop = float(request.form.get('crop', 5)) / 100.0
    zoom = float(request.form.get('zoom', 10)) / 10.0
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Save input file
            input_path = os.path.join(temp_dir, 'input.mp4')
            file.save(input_path)
            
            # Check if file was saved properly
            if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
                return 'File upload failed', 400
            
            # Convert video
            output_path = os.path.join(temp_dir, 'output.mp4')
            success, message = convert_video_file(input_path, output_path, crop, zoom)
            
            if success and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return send_file(output_path, as_attachment=True, download_name='vertical_video.mp4')
            else:
                return f'Conversion failed: {message}', 500
                
        except Exception as e:
            return f'Server error: {str(e)}', 500