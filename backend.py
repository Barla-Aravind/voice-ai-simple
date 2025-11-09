from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import os
import uuid
import json
import time
from google.cloud import texttospeech

app = Flask(__name__)
CORS(app)

os.makedirs('audio_output', exist_ok=True)
os.makedirs('events', exist_ok=True)

# Initialize Google TTS client
try:
    client = texttospeech.TextToSpeechClient()
    GOOGLE_TTS_AVAILABLE = True
except:
    GOOGLE_TTS_AVAILABLE = False
    print("⚠️ Google TTS not available - using fallback")

@app.route('/')
def serve_frontend():
    """Serve the index.html file"""
    try:
        with open('index.html', 'r') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
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
        
        if not GOOGLE_TTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'TTS service not available'}), 500
        
        # Google Text-to-Speech synthesis
        print(f"Synthesizing with Google TTS: {text[:50]}...")
        
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )
        
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        # Write audio to file
        with open(wav_path, 'wb') as out:
            out.write(response.audio_content)
        
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
                "text": text,
                "length": len(text),
                "filename": filename,
                "file_size": file_size,
                "voice_provider": "Google Cloud TTS",
                "processing_time": processing_time,
                "success": True
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
                'provider': 'Google Cloud TTS',
                'cost': '$0.00'
            })
        else:
            return jsonify({'success': False, 'error': 'Audio synthesis failed'}), 500
    
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
            {'id': 'google', 'name': 'Google Cloud TTS', 'provider': 'Google', 'cost': '$0.00'}
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