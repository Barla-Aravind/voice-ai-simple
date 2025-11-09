from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import subprocess
import os
import uuid
import json
import time

app = Flask(__name__)
CORS(app)

os.makedirs('audio_output', exist_ok=True)

@app.route('/api/v1/synthesize', methods=['POST'])
def synthesize():
    try:
        start_time = time.time()   # <-- define start_time at the very beginning

        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({'success': False, 'error': 'Text required'}), 400
        
        filename = f"tts_{uuid.uuid4().hex[:8]}"
        aiff_path = os.path.abspath(os.path.join('audio_output', f"{filename}.aiff"))
        wav_path = os.path.abspath(os.path.join('audio_output', f"{filename}.wav"))
        
        # Step 1: Generate AIFF (this always works on Mac)
        print(f"Generating AIFF: {aiff_path}")
        subprocess.run(['say', text, '-o', aiff_path], check=True, capture_output=True)
        
        # Step 2: Convert AIFF to WAV using ffmpeg
        print(f"Converting to WAV: {wav_path}")
        subprocess.run(['ffmpeg', '-i', aiff_path, '-q:a', '9', '-n', wav_path], 
                      capture_output=True, check=True)
        
        # Step 3: Clean up AIFF file
        if os.path.exists(aiff_path):
            os.remove(aiff_path)
        
        if os.path.exists(wav_path) and os.path.getsize(wav_path) > 100:
            print(f"✅ File created: {wav_path}")
        
            size_bytes = os.path.getsize(wav_path)
            if size_bytes < 1024:
                file_size = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                file_size = f"{round(size_bytes / 1024, 2)} KB"
            else:
                file_size = f"{round(size_bytes / (1024 * 1024), 2)} MB"

            # ============ NEW: LOG EVENT FOR SPARK STREAMING ============
            processing_time = round(time.time() - start_time, 3)
            event_data = {
                     "timestamp": time.time(),
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "request_id": uuid.uuid4().hex,
                "service": "voice-ai-backend",
                "version": "1.0.0",
                "method": request.method,
                "endpoint": request.path,
                "client_ip": request.remote_addr,
                "user_agent": request.headers.get("User-Agent"),
                "text": text,
                "length": len(text),
                "filename": filename,
                "output_format": "wav",
                "file_size": file_size,   # <-- use human-readable size
                "voice_provider": "macOS Voice",
                "conversion_tool": "ffmpeg",
                "processing_time": processing_time,
                "success": True,
                "hostname": os.uname().nodename,
                "platform": os.uname().sysname
            }
            
            # Create events directory if not exists
            os.makedirs("events", exist_ok=True)
            # Write each event as a separate JSON file
            event_filename = f"{uuid.uuid4().hex}.json"
            event_path = os.path.join("events", event_filename)

            with open(event_path, "w") as f:
                json.dump(event_data, f)

            print(f"✅ Event logged for Spark Streaming: {event_path}")
            # ============ END: LOG EVENT ============
            
            return jsonify({
                'success': True,
                'audio_url': f'/download/{filename}.wav',
                'provider': 'macOS Voice',
                'cost': '$0.00'
            })
        else:
            return jsonify({'success': False, 'error': 'Audio conversion failed'}), 500
    
    except Exception as e:
        print(f"Synthesis error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/download/<filename>')
def download(filename):
    try:
        file_path = os.path.join('audio_output', filename)
        
        if os.path.exists(file_path):
            return send_file(file_path, mimetype='audio/wav', as_attachment=False)
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/voices', methods=['GET'])
def get_voices():
    return jsonify({
        'success': True,
        'voices': [
            {'id': 'macos', 'name': 'macOS Voice', 'provider': 'macOS', 'cost': '$0.00'}
        ]
    })

# ============ NEW: API ENDPOINT FOR SPARK ANALYTICS ============
@app.route('/api/v1/analytics', methods=['GET'])
def get_analytics():
    """Return current analytics from tts_events.log"""
    try:
        if not os.path.exists('tts_events.log'):
            return jsonify({
                'success': True,
                'total_requests': 0,
                'avg_text_length': 0,
                'events': []
            })
        
        with open('tts_events.log', 'r') as f:
            events = [json.loads(line) for line in f if line.strip()]
        
        if not events:
            return jsonify({
                'success': True,
                'total_requests': 0,
                'avg_text_length': 0,
                'events': []
            })
        
        avg_length = sum(e['length'] for e in events) / len(events)
        
        return jsonify({
            'success': True,
            'total_requests': len(events),
            'avg_text_length': round(avg_length, 2),
            'events': events[-10:]  # Last 10 events
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
# ============ END: NEW API ENDPOINT ============

if __name__ == '__main__':
    print("🚀 Voice AI Backend Running on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
