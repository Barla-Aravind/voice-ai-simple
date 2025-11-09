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
os.makedirs('events', exist_ok=True)

@app.route('/api/v1/synthesize', methods=['POST'])
def synthesize():
    try:
        start_time = time.time()
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({'success': False, 'error': 'Text required'}), 400
        
        filename = f"tts_{uuid.uuid4().hex[:8]}"
        aiff_path = os.path.abspath(os.path.join('audio_output', f"{filename}.aiff"))
        wav_path = os.path.abspath(os.path.join('audio_output', f"{filename}.wav"))
        
        # Step 1: Generate AIFF
        print(f"Generating AIFF: {aiff_path}")
        subprocess.run(['say', text, '-o', aiff_path], check=True, capture_output=True)
        
        # Step 2: Convert AIFF to WAV
        print(f"Converting to WAV: {wav_path}")
        subprocess.run(['ffmpeg', '-i', aiff_path, '-q:a', '9', '-n', wav_path], 
                      capture_output=True, check=True)
        
        # Step 3: Clean up AIFF
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
            
            # LOG EVENT
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
            }
            
            # Write to events folder
            event_filename = f"{uuid.uuid4().hex}.json"
            event_path = os.path.join("events", event_filename)
            with open(event_path, "w") as f:
                json.dump(event_data, f)
            
            print(f"✅ Event logged: {event_path}")
            
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

@app.route('/api/v1/analytics', methods=['GET'])
def get_analytics():
    """Return current analytics from events folder"""
    try:
        events_dir = 'events'
        
        if not os.path.exists(events_dir) or not os.listdir(events_dir):
            return jsonify({
                'success': True,
                'total_requests': 0,
                'avg_text_length': 0,
                'events': []
            })
        
        # Read all JSON files from events folder
        events = []
        for filename in os.listdir(events_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(events_dir, filename)
                with open(filepath, 'r') as f:
                    event = json.load(f)
                    events.append(event)
        
        if not events:
            return jsonify({
                'success': True,
                'total_requests': 0,
                'avg_text_length': 0,
                'events': []
            })
        
        # Sort by timestamp (newest first)
        events.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        # Calculate average text length
        avg_length = sum(e['length'] for e in events) / len(events)
        
        return jsonify({
            'success': True,
            'total_requests': len(events),
            'avg_text_length': round(avg_length, 2),
            'events': events[:10]  # Last 10 events
        })
    except Exception as e:
        print(f"Analytics error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Voice AI Backend Running on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)