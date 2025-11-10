"""
VOICE AI - MAC COMPATIBLE BACKEND (gTTS + Web Audio API)

Why this approach?
- gTTS works perfectly on Mac (no objc issues)
- Speed/Pitch/Volume control done via Web Audio API (JavaScript)
- Emotions via text modification
- No pyttsx3 dependency conflicts on Mac
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pydub import AudioSegment
from gtts import gTTS
import os
import uuid
import json
import time
import io

app = Flask(__name__)
CORS(app)

os.makedirs('audio_output', exist_ok=True)
os.makedirs('events', exist_ok=True)

print("✅ Using gTTS (Google Text-to-Speech) - Mac Compatible")

# ===== ROUTE 1: SERVE FRONTEND =====
@app.route('/')
def serve_frontend():
    """Serves index.html"""
    try:
        with open('index.html', 'r') as f:
            return f.read()
    except:
        return "index.html not found", 404

# ===== EMOTION TEXT MODIFICATION =====
EMOTION_CONFIG = {
    'happy': {
        'prefix': '',
        'suffix': '! 😊',
    },
    'sad': {
        'prefix': '',
        'suffix': '... 😢',
    },
    'angry': {
        'prefix': '',
        'suffix': '!! 😠',
    },
    'calm': {
        'prefix': '',
        'suffix': '. 😌',
    }
}

def apply_emotion_to_text(text, emotion):
    """Modify text based on emotion"""
    config = EMOTION_CONFIG.get(emotion, EMOTION_CONFIG['happy'])
    enhanced = config['prefix'] + text + config['suffix']
    return enhanced

# ===== ROUTE 2: SYNTHESIZE TEXT TO SPEECH =====
@app.route('/api/v1/synthesize', methods=['POST'])
def synthesize():
    """
    Generate speech with:
    ✅ gTTS (works on Mac)
    ✅ Emotions (text modification)
    ✅ Speed/Pitch/Volume (controlled via Web Audio API on frontend)
    ✅ Multiple languages
    """
    try:
        start_time = time.time()
        data = request.get_json()
        text = data.get('text', '')
        voice = data.get('voice', 'female')
        language = data.get('language', 'en')
        emotion = data.get('emotion', 'happy')
        speed = float(data.get('speed', 1.0))
        pitch = float(data.get('pitch', 1.0))
        volume = int(data.get('volume', 100))
        
        if not text:
            return jsonify({'success': False, 'error': 'Text required'}), 400
        
        # Validate inputs
        valid_emotions = ['happy', 'sad', 'angry', 'calm']
        if emotion not in valid_emotions:
            emotion = 'happy'
        
        # Clamp values
        speed = max(0.5, min(2.0, speed))
        pitch = max(0.5, min(2.0, pitch))
        volume = max(0, min(100, volume))
        
        filename = f"tts_{uuid.uuid4().hex[:8]}"
        mp3_path = os.path.abspath(os.path.join('audio_output', f"{filename}.mp3"))
        
        print(f"\n📝 Generating: {text[:50]}...")
        print(f"   Language: {language}, Emotion: {emotion}, Speed: {speed}x, Pitch: {pitch}, Volume: {volume}%")
        
        # ===== APPLY EMOTION TO TEXT =====
        enhanced_text = apply_emotion_to_text(text, emotion)
        
        # ===== GENERATE SPEECH WITH gTTS =====
        try:
            tts = gTTS(text=enhanced_text, lang=language, slow=False)
            tts.save(mp3_path)
            print(f"✅ gTTS synthesis success")
        except Exception as gtts_err:
            print(f"❌ gTTS error: {gtts_err}")
            return jsonify({'success': False, 'error': f'Speech generation failed: {str(gtts_err)}'}), 500
        
        # Check if MP3 file was created
        if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 100:
            size_bytes = os.path.getsize(mp3_path)
            if size_bytes < 1024:
                file_size = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                file_size = f"{round(size_bytes / 1024, 2)} KB"
            else:
                file_size = f"{round(size_bytes / (1024 * 1024), 2)} MB"
            
            processing_time = round(time.time() - start_time, 3)
            
            # ===== LOG EVENT FOR SPARK STREAMING =====
            event_data = {
                "timestamp": time.time(),
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "request_id": uuid.uuid4().hex,
                "text": text,
                "length": len(text),
                "filename": filename,
                "file_size": file_size,
                "voice_provider": "Google TTS (gTTS)",
                "voice_selection": voice,
                "language_selected": language,
                "emotion_selected": emotion,
                "speed": speed,
                "pitch": pitch,
                "volume": volume,
                "processing_time": processing_time,
                "success": True
            }
            
            event_filename = f"{uuid.uuid4().hex}.json"
            event_path = os.path.join("events", event_filename)
            with open(event_path, "w") as f:
                json.dump(event_data, f)
            
            print(f"✅ Event logged successfully")
            
            return jsonify({
                'success': True,
                'audio_url': f'/download/{filename}.mp3',
                'provider': 'Google TTS (Works on Mac)',
                'voice': voice,
                'language': language,
                'emotion': emotion,
                'speed': speed,
                'pitch': pitch,
                'volume': volume,
                'cost': '$0.00'
            })
        else:
            return jsonify({'success': False, 'error': 'MP3 file not created'}), 500
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROUTE 3: DOWNLOAD AUDIO =====
@app.route('/download/<filename>')
def download(filename):
    """Download generated audio file"""
    try:
        file_path = os.path.join('audio_output', filename)
        
        if os.path.exists(file_path):
            if filename.endswith('.mp3'):
                return send_file(file_path, mimetype='audio/mpeg', as_attachment=False)
            elif filename.endswith('.wav'):
                return send_file(file_path, mimetype='audio/wav', as_attachment=False)
            else:
                return send_file(file_path, mimetype='audio/mpeg', as_attachment=False)
        
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== ROUTE 4: ANALYTICS =====
@app.route('/api/v1/analytics', methods=['GET'])
def get_analytics():
    """Get real-time analytics"""
    try:
        events_dir = 'events'
        
        if not os.path.exists(events_dir) or not os.listdir(events_dir):
            return jsonify({
                'success': True,
                'total_requests': 0,
                'avg_text_length': 0,
                'voice_breakdown': {},
                'emotion_breakdown': {},
                'events': []
            })
        
        events = []
        voice_count = {}
        emotion_count = {}
        avg_speed = 0
        avg_pitch = 0
        
        for filename in os.listdir(events_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(events_dir, filename), 'r') as f:
                        event = json.load(f)
                        events.append(event)
                        
                        voice = event.get('voice_selection', 'unknown')
                        voice_count[voice] = voice_count.get(voice, 0) + 1
                        
                        emotion = event.get('emotion_selected', 'happy')
                        emotion_count[emotion] = emotion_count.get(emotion, 0) + 1
                        
                        avg_speed += event.get('speed', 1.0)
                        avg_pitch += event.get('pitch', 1.0)
                except:
                    pass
        
        if not events:
            return jsonify({
                'success': True,
                'total_requests': 0,
                'avg_text_length': 0,
                'voice_breakdown': {},
                'emotion_breakdown': {},
                'events': []
            })
        
        events.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        avg_length = sum(e['length'] for e in events) / len(events)
        avg_speed = round(avg_speed / len(events), 2)
        avg_pitch = round(avg_pitch / len(events), 2)
        
        return jsonify({
            'success': True,
            'total_requests': len(events),
            'avg_text_length': round(avg_length, 2),
            'voice_breakdown': voice_count,
            'emotion_breakdown': emotion_count,
            'avg_speed': avg_speed,
            'avg_pitch': avg_pitch,
            'events': events[:10]
        })
    except Exception as e:
        print(f"❌ Analytics error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 Voice AI Backend - MAC COMPATIBLE (gTTS)")
    print("="*60)
    print("✅ gTTS Engine (no pyttsx3 conflicts)")
    print("✅ Speed control (0.5x - 2x) via Web Audio API")
    print("✅ Pitch control (0.5 - 2.0) via Web Audio API")
    print("✅ Emotions (happy/sad/angry/calm)")
    print("✅ Multiple languages (EN, HI, TE, ES, FR, etc)")
    print("✅ Volume control via Web Audio API")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)