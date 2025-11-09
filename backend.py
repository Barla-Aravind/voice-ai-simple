from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import uuid
import json
import time

app = Flask(__name__)
CORS(app)

os.makedirs('audio_output', exist_ok=True)
os.makedirs('events', exist_ok=True)

# Try gTTS (works on Mac, Linux, Railway - NO dependencies)
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
    print("✅ gTTS available")
except ImportError:
    GTTS_AVAILABLE = False
    print("⚠️ gTTS not available - install: pip install gtts")

@app.route('/')
def serve_frontend():
    try:
        with open('index.html', 'r') as f:
            return f.read()
    except:
        return "index.html not found", 404

@app.route('/api/v1/synthesize', methods=['POST'])
def synthesize():
    try:
        start_time = time.time()
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({'success': False, 'error': 'Text required'}), 400
        
        filename = f"tts_{uuid.uuid4().hex[:8]}"
        wav_path = os.path.abspath(os.path.join('audio_output', f"{filename}.wav"))
        mp3_path = os.path.abspath(os.path.join('audio_output', f"{filename}.mp3"))
        
        print(f"📝 Synthesizing: {text[:50]}...")
        
        if GTTS_AVAILABLE:
            try:
                # Use gTTS for HIGH QUALITY audio
                tts = gTTS(text=text, lang='en', slow=False)
                tts.save(mp3_path)
                
                # Convert MP3 to WAV if needed (for compatibility)
                # For now, serve MP3 directly - browsers support it
                wav_path = mp3_path.replace('.mp3', '.wav')
                
                # Actually, let's just use MP3 - it's smaller and better quality
                file_to_serve = mp3_path
                serve_ext = '.mp3'
                
                print(f"✅ gTTS success")
                
            except Exception as e:
                print(f"❌ gTTS error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        else:
            return jsonify({'success': False, 'error': 'Install: pip install gtts'}), 500
        
        if os.path.exists(file_to_serve) and os.path.getsize(file_to_serve) > 100:
            size_bytes = os.path.getsize(file_to_serve)
            if size_bytes < 1024:
                file_size = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                file_size = f"{round(size_bytes / 1024, 2)} KB"
            else:
                file_size = f"{round(size_bytes / (1024 * 1024), 2)} MB"
            
            processing_time = round(time.time() - start_time, 3)
            event_data = {
                "timestamp": time.time(),
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "request_id": uuid.uuid4().hex,
                "text": text,
                "length": len(text),
                "filename": filename,
                "file_size": file_size,
                "voice_provider": "Google TTS (gTTS)",
                "processing_time": processing_time,
                "success": True
            }
            
            event_filename = f"{uuid.uuid4().hex}.json"
            event_path = os.path.join("events", event_filename)
            with open(event_path, "w") as f:
                json.dump(event_data, f)
            
            print(f"✅ Event logged")
            
            return jsonify({
                'success': True,
                'audio_url': f'/download/{filename}{serve_ext}',
                'provider': 'Google TTS (gTTS)',
                'cost': '$0.00'
            })
        else:
            return jsonify({'success': False, 'error': 'Audio synthesis failed'}), 500
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/download/<filename>')
def download(filename):
    try:
        # Support both .wav and .mp3
        file_path = os.path.join('audio_output', filename)
        
        if os.path.exists(file_path):
            if filename.endswith('.mp3'):
                return send_file(file_path, mimetype='audio/mpeg', as_attachment=False)
            else:
                return send_file(file_path, mimetype='audio/wav', as_attachment=False)
        
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/analytics', methods=['GET'])
def get_analytics():
    try:
        events_dir = 'events'
        
        if not os.path.exists(events_dir) or not os.listdir(events_dir):
            return jsonify({'success': True, 'total_requests': 0, 'avg_text_length': 0, 'events': []})
        
        events = []
        for filename in os.listdir(events_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(events_dir, filename), 'r') as f:
                        events.append(json.load(f))
                except:
                    pass
        
        if not events:
            return jsonify({'success': True, 'total_requests': 0, 'avg_text_length': 0, 'events': []})
        
        events.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        avg_length = sum(e['length'] for e in events) / len(events)
        
        return jsonify({
            'success': True,
            'total_requests': len(events),
            'avg_text_length': round(avg_length, 2),
            'events': events[:10]
        })
    except Exception as e:
        print(f"❌ Analytics error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Voice AI Backend on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)