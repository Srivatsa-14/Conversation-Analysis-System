import os
import json
import uuid
import logging
import traceback
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import sys

# Fix Windows encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Flask imports
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Configure logging with ASCII-only characters for Windows
class AsciiLogger:
    def __init__(self, logger):
        self.logger = logger

    def info(self, msg):
        # Replace emojis with ASCII equivalents
        msg = (msg.replace('📤', '[UPLOAD]')
                 .replace('✅', '[OK]')
                 .replace('🎙️', '[MIC]')
                 .replace('🔍', '[SEARCH]')
                 .replace('🎛️', '[AUDIO]')
                 .replace('❌', '[ERROR]')
                 .replace('🧠', '[AI]')
                 .replace('🤖', '[BOT]')
                 .replace('📊', '[CHART]')
                 .replace('📝', '[TEXT]')
                 .replace('🔧', '[TOOL]')
                 .replace('📤', '[UPLOAD]')
                 .replace('🧹', '[CLEAN]')
                 .replace('⚠️', '[WARN]'))
        self.logger.info(msg)

    def error(self, msg, exc_info=False):
        msg = (msg.replace('❌', '[ERROR]')
                 .replace('⚠️', '[WARN]'))
        self.logger.error(msg, exc_info=exc_info)

    def warning(self, msg):
        msg = msg.replace('⚠️', '[WARN]')
        self.logger.warning(msg)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = AsciiLogger(logging.getLogger(__name__))

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
app.config.update(
    MAX_CONTENT_LENGTH=200 * 1024 * 1024,  # 200MB
    UPLOAD_FOLDER='temp',
    ALLOWED_EXTENSIONS={
        'mp3', 'wav', 'm4a', 'webm', 'ogg', 'flac', 'aac',
        'mp4', 'mov', 'mpeg', 'avi', 'mkv', 'wma'
    },
    SECRET_KEY=os.getenv('FLASK_SECRET_KEY', 'conversation-analytics-secret-key-2024'),
    SQLALCHEMY_DATABASE_URI = 'sqlite:///conversations.db',
    SQLALCHEMY_TRACK_MODIFICATIONS = False
)

# Ensure directories exist
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)
Path('logs').mkdir(exist_ok=True)
Path('static/charts').mkdir(parents=True, exist_ok=True)
Path('static/reports').mkdir(parents=True, exist_ok=True)

# Initialize database
from models import db, User, Conversation
db.init_app(app)

# Create tables and migrate
with app.app_context():
    db.create_all()
    
    # Add new columns if they don't exist (for existing databases)
    try:
        from sqlalchemy import text
        conn = db.engine.connect()
        
        # Check if visualization_json column exists
        result = conn.execute(text("PRAGMA table_info(conversations)"))
        columns = [row[1] for row in result]
        
        if 'visualization_json' not in columns:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN visualization_json TEXT"))
            logger.info("Added visualization_json column")
            
        if 'charts_json' not in columns:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN charts_json TEXT"))
            logger.info("Added charts_json column")
            
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Database migration note: {e}")

# Get Deepgram API key
DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
if not DEEPGRAM_API_KEY:
    logger.error(" DEEPGRAM_API_KEY not found in environment variables")
    logger.warning("Please add DEEPGRAM_API_KEY to your .env file")

# Import modules
from auth_service import AuthService, token_required
from nlp_processor import get_nlp_processor
from ai_summarizer import get_ai_summarizer
from voice_processor import VoiceProcessor
from speaker_identifier import SpeakerIdentifier
from dashboard_analytics import DashboardAnalytics

# Initialize services
auth_service = AuthService(app)
nlp_processor = get_nlp_processor()
ai_summarizer = get_ai_summarizer()
voice_processor = VoiceProcessor()
speaker_identifier = SpeakerIdentifier()
dashboard_analytics = DashboardAnalytics()

logger.info(" All services initialized successfully")

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def validate_audio_file(file_path: str) -> bool:
    """Basic audio file validation"""
    try:
        if not os.path.exists(file_path):
            return False

        file_size = os.path.getsize(file_path)
        if file_size > 200 * 1024 * 1024:
            logger.warning(f"File too large: {file_size / (1024*1024):.1f}MB")
            return False

        if file_size == 0:
            logger.warning("File is empty")
            return False

        return True
    except Exception as e:
        logger.error(f"File validation error: {e}")
        return False

# Authentication Routes
@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register new user"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        email = data.get('email')
        password = data.get('password')
        name = data.get('name')

        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password required'}), 400

        result = auth_service.register_user(email, password, name)

        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password required'}), 400

        result = auth_service.login_user(email, password)

        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 401

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/verify', methods=['GET'])
@token_required
def verify():
    """Verify token and get user info"""
    user = auth_service.get_user_from_token(request.headers.get('Authorization', '').split(' ')[-1])
    if user:
        return jsonify({'success': True, 'user': user.to_dict()})
    return jsonify({'success': False, 'error': 'Invalid token'}), 401

# Main Routes
@app.route('/')
def index():
    """Serve the login page"""
    return send_from_directory('frontend', 'login.html')

@app.route('/dashboard')
def dashboard():
    """Serve the dashboard"""
    return send_from_directory('frontend', 'dashboard.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'Conversation Analytics API',
        'version': '2.0.0',
        'features': {
            'speech_recognition': bool(DEEPGRAM_API_KEY),
            'nlp_processing': True,
            'ai_summarization': True,
            'speaker_diarization': True,
            'sentiment_analysis': True,
            'voice_activity_detection': True,
            'speaker_identification': True,
            'pos_tagging': True,
            'timing_analysis': True
        },
        'system': {
            'upload_folder': app.config['UPLOAD_FOLDER'],
            'max_file_size': f"{app.config['MAX_CONTENT_LENGTH'] // (1024*1024)}MB",
            'supported_formats': list(app.config['ALLOWED_EXTENSIONS'])
        }
    })

@app.route('/api/upload', methods=['POST', 'OPTIONS'])
@token_required
def upload_media():
    """File upload endpoint with validation"""
    if request.method == 'OPTIONS':
        return '', 200

    logger.info(" Received file upload request")

    if 'audio' not in request.files:
        logger.warning("No audio file in request")
        return jsonify({
            'success': False,
            'error': 'No audio file provided. Please select a file to upload.'
        }), 400

    file = request.files['audio']

    if file.filename == '':
        logger.warning("Empty filename in upload")
        return jsonify({
            'success': False,
            'error': 'No file selected. Please choose an audio file.'
        }), 400

    if not allowed_file(file.filename):
        logger.warning(f"Invalid file type: {file.filename}")
        return jsonify({
            'success': False,
            'error': f'File type not allowed. Supported formats: {", ".join(sorted(app.config["ALLOWED_EXTENSIONS"]))}'
        }), 400

    try:
        ext = Path(file.filename).suffix.lower()
        unique_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"audio_{timestamp}_{unique_id}{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))

        file.save(filepath)
        logger.info(f" File saved: {filepath} ({os.path.getsize(filepath) / (1024*1024):.2f} MB)")

        if not validate_audio_file(filepath):
            os.remove(filepath)
            return jsonify({
                'success': False,
                'error': 'Invalid audio file. Please check the file and try again.'
            }), 400

        conversation_id = f"conv_{timestamp}_{unique_id}"

        return jsonify({
            'success': True,
            'data': {
                'url': filepath,
                'filename': filename,
                'conversation_id': conversation_id,
                'file_size': os.path.getsize(filepath),
                'upload_time': datetime.now().isoformat()
            },
            'message': 'File uploaded successfully. Ready for analysis.'
        })

    except Exception as e:
        logger.error(f" Upload error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Upload failed: {str(e)}'
        }), 500

@app.route('/api/transcribe', methods=['POST', 'OPTIONS'])
@token_required
def transcribe():
    """Complete transcription and analysis endpoint"""
    if request.method == 'OPTIONS':
        return '', 200

    logger.info(" Starting transcription request")
    start_time = datetime.now()

    try:
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Request must be JSON'
            }), 400

        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: url'
            }), 400

        audio_url = data['url']
        conversation_id = data.get('conversation_id', f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

        if not DEEPGRAM_API_KEY:
            logger.error("Deepgram API key not configured")
            return jsonify({
                'success': False,
                'error': 'Speech recognition service not configured. Please contact administrator.'
            }), 500

        is_local_file = os.path.exists(audio_url)

        logger.info(f" Processing {'local file' if is_local_file else 'URL'}: {audio_url}")

        # Skip local preprocessing - send directly to Deepgram
        # Deepgram handles audio decoding internally

        params = {
            "model": "nova-2",
            "language": "en",
            "summarize": "v2",
            "topics": "true",
            "intents": "true",
            "detect_entities": "true",
            "sentiment": "true",
            "smart_format": "true",
            "diarize": "true",
            "paragraphs": "true",
            "utterances": "true",
            "detect_language": "true",
            "profanity_filter": "false"
        }

        headers = {
            'Authorization': f'Token {DEEPGRAM_API_KEY}',
            'Content-Type': 'audio/*' if is_local_file else 'application/json'
        }

        deepgram_url = 'https://api.deepgram.com/v1/listen'

        if is_local_file:
            if not os.path.isfile(audio_url):
                return jsonify({
                    'success': False,
                    'error': 'File not found'
                }), 404

            with open(audio_url, 'rb') as audio_file:
                response = requests.post(
                    deepgram_url,
                    headers=headers,
                    params=params,
                    data=audio_file.read(),
                    timeout=300
                )

        else:
            request_data = {"url": audio_url}
            response = requests.post(
                deepgram_url,
                headers=headers,
                params=params,
                json=request_data,
                timeout=300
            )

        if response.status_code != 200:
            error_text = response.text[:500]
            logger.error(f" Deepgram API error {response.status_code}: {error_text}")
            return jsonify({
                'success': False,
                'error': f'Speech recognition failed: {error_text}'
            }), 500

        deepgram_data = response.json()
        logger.info(" Deepgram processing complete")

        enhanced_result = process_and_enhance_data(deepgram_data, conversation_id, audio_url if is_local_file else None)

        # Clean up temporary file
        if is_local_file:
            try:
                os.remove(audio_url)
                logger.info(f" Removed temporary file: {audio_url}")
            except Exception as cleanup_error:
                logger.warning(f"Could not remove temporary file: {cleanup_error}")

        total_time = (datetime.now() - start_time).total_seconds()
        enhanced_result['processing_metadata']['total_processing_time'] = round(total_time, 2)

        # Save to database
        try:
            user_id = request.user_id

            conversation = Conversation(
                conversation_id=conversation_id,
                user_id=user_id,
                filename=data.get('filename', 'recording.wav'),
                file_size=enhanced_result.get('metadata', {}).get('size', 0),
                duration=enhanced_result.get('metadata', {}).get('total_duration', 0),
                speaker_count=enhanced_result.get('metadata', {}).get('speaker_count', 1),
                word_count=enhanced_result.get('metadata', {}).get('word_count', 0),
                speaker_names_json=json.dumps({}),
                transcript_json=json.dumps(enhanced_result.get('transcript', {})),
                speaker_analysis_json=json.dumps(enhanced_result.get('speaker_analysis', {})),
                nlp_analysis_json=json.dumps(enhanced_result.get('nlp_analysis', {})),
                summary_json=json.dumps(enhanced_result.get('ai_summary', {})),
                insights_json=json.dumps(enhanced_result.get('key_insights', {})),
                visualization_json=json.dumps(enhanced_result.get('visualization_data', {})),
                charts_json=json.dumps(enhanced_result.get('charts', {})),
                conversation_type=enhanced_result.get('ai_summary', {}).get('conversation_type', 'general'),
                processed_at=datetime.now()
            )

            db.session.add(conversation)
            db.session.commit()
            logger.info(f" Conversation saved to database: {conversation_id}")

        except Exception as e:
            logger.error(f"Database save error: {e}")
            db.session.rollback()

        try:
            if enhanced_result.get('metadata'):
                logger.info(f" Complete analysis finished in {total_time:.2f}s")
                logger.info(f"   Speakers: {enhanced_result['metadata'].get('speaker_count', 'N/A')}")
                logger.info(f"   Words: {enhanced_result['metadata'].get('word_count', 'N/A')}")

                if enhanced_result.get('nlp_analysis', {}).get('sentiment'):
                    logger.info(f"   Sentiment: {enhanced_result['nlp_analysis']['sentiment'].get('label', 'N/A')}")
        except Exception as log_error:
            logger.warning(f"Could not log all details: {log_error}")

        return jsonify({
            'success': True,
            'data': enhanced_result,
            'conversation_id': conversation_id,
            'processing_time': round(total_time, 2),
            'message': 'Conversation analysis completed successfully'
        })

    except requests.exceptions.Timeout:
        logger.error(" Deepgram API timeout")
        return jsonify({
            'success': False,
            'error': 'Speech recognition timeout. Please try a shorter audio file.'
        }), 504

    except Exception as e:
        logger.error(f" Transcription error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Analysis failed: {str(e)}'
        }), 500

def process_and_enhance_data(deepgram_data: Dict, conversation_id: str, audio_path: str = None) -> Dict[str, Any]:
    """Process Deepgram data and enhance with NLP analysis"""
    logger.info(" Processing and enhancing data...")

    try:
        results = deepgram_data.get('results', {})
        channels = results.get('channels', [{}])
        channel = channels[0] if channels else {}
        alternatives = channel.get('alternatives', [{}])
        alternative = alternatives[0] if alternatives else {}
        metadata = deepgram_data.get('metadata', {})

        transcript = alternative.get('transcript', '')
        words = alternative.get('words', [])
        paragraphs_data = alternative.get('paragraphs', {}).get('paragraphs', [])

        # Convert Deepgram paragraphs to our format
        paragraphs = []
        for p in paragraphs_data:
            sentences = p.get('sentences', [])
            text = ' '.join([s.get('text', '') for s in sentences])
            paragraphs.append({
                'speaker': p.get('speaker', 0),
                'text': text,
                'start': p.get('start', 0),
                'end': p.get('end', 0),
                'sentences': sentences
            })

        # Extract speaker information
        speaker_set = set()
        speaker_segments = []

        for word in words:
            speaker = word.get('speaker')
            if speaker is not None:
                speaker_set.add(speaker)
                speaker_segments.append({
                    'speaker': speaker,
                    'word': word.get('word', ''),
                    'start': word.get('start', 0),
                    'end': word.get('end', 0),
                    'confidence': word.get('confidence', 0)
                })

        speaker_count = len(speaker_set)

        logger.info(" Running NLP analysis...")
        nlp_results = nlp_processor.process_conversation(transcript, paragraphs)

        # Analyze each speaker individually
        speaker_analysis = {}
        for speaker_id in speaker_set:
            speaker_text_segments = [p for p in paragraphs if p.get('speaker') == speaker_id]
            speaker_text = ' '.join([p.get('text', '') for p in speaker_text_segments])

            speaker_nlp = nlp_processor.process_conversation(speaker_text, speaker_text_segments)

            speaker_paras = [p for p in paragraphs if p.get('speaker') == speaker_id]
            speaker_word_list = [w for w in words if w.get('speaker') == speaker_id]

            total_duration = sum(p.get('end', 0) - p.get('start', 0) for p in speaker_paras) if speaker_paras else 0
            word_count = len(speaker_word_list)

            speaking_rate = (word_count / total_duration * 60) if total_duration > 0 else 0

            total_words_all = len(words)
            contribution_pct = (word_count / total_words_all * 100) if total_words_all > 0 else 0

            # Extract key phrases for this speaker
            key_phrases = []
            if speaker_text:
                words_sp = speaker_text.lower().split()
                from collections import Counter
                word_freq = Counter(words_sp)
                key_phrases = [w for w, c in word_freq.most_common(5) if len(w) > 3 and c > 1][:5]

            if speaker_word_list:
                avg_confidence = np.mean([w.get('confidence', 0) for w in speaker_word_list])
            else:
                avg_confidence = 0

            speaker_analysis[str(speaker_id)] = {
                'id': speaker_id,
                'word_count': word_count,
                'duration': round(total_duration, 2),
                'speaking_rate': round(speaking_rate, 1),
                'contribution_percentage': round(contribution_pct, 1),
                'paragraph_count': len(speaker_paras),
                'sentiment': speaker_nlp.get('sentiment', {'label': 'Neutral', 'score': 0}),
                'topics': speaker_nlp.get('topics', [])[:3],
                'key_phrases': key_phrases[:3],
                'avg_word_confidence': round(avg_confidence, 3),
                'pos_tags': speaker_nlp.get('pos_tags', {})
            }

        # Format paragraphs with enhanced data
        formatted_paragraphs = []
        for para in paragraphs:
            text = para.get('text', '')

            para_sentiment = nlp_processor.analyze_sentiment(text)
            para_intents = nlp_processor.detect_intents(text)

            formatted_paragraphs.append({
                'speaker': para.get('speaker', 0),
                'text': text,
                'start': para.get('start', 0),
                'end': para.get('end', 0),
                'sentiment': para_sentiment,
                'intents': para_intents[:2],
                'sentence_count': len(para.get('sentences', [])),
                'word_count': len(text.split()),
                'duration': para.get('end', 0) - para.get('start', 0)
            })

        # Create timeline segments
        timeline_segments = []
        for i, para in enumerate(formatted_paragraphs):
            segment = {
                'time': para['start'],
                'speaker': para['speaker'],
                'sentiment': para['sentiment'].get('score', 0),
                'text_preview': para['text'][:50] + ('...' if len(para['text']) > 50 else '')
            }
            timeline_segments.append(segment)

        # Calculate metadata
        total_duration = metadata.get('duration', 0)
        word_count = len(words)

        # FIX 1: Ensure timing analysis is properly populated
        timing_analysis = nlp_results.get('timing_analysis', {})
        if not timing_analysis and paragraphs:
            # Manually calculate if NLP processor didn't
            exchanges = 0
            interruptions = 0
            gaps = []
            last_speaker = None
            last_end = 0

            for para in paragraphs:
                speaker = para.get('speaker', 0)
                start = para.get('start', 0)
                end = para.get('end', 0)

                if last_speaker is not None and speaker != last_speaker:
                    exchanges += 1
                    gap = start - last_end
                    gaps.append(gap)
                    if gap < 0.5:
                        interruptions += 1

                last_speaker = speaker
                last_end = end

            timing_analysis = {
                'num_exchanges': exchanges,
                'interruptions': interruptions,
                'avg_gap': np.mean(gaps) if gaps else 0,
                'conversation_pace': len(paragraphs) / total_duration if total_duration > 0 else 0
            }

        enhanced_metadata = {
            **metadata,
            'conversation_id': conversation_id,
            'speaker_count': speaker_count,
            'speakers': list(speaker_set),
            'word_count': word_count,
            'paragraph_count': len(paragraphs),
            'sentence_count': sum(len(p.get('sentences', [])) for p in paragraphs),
            'total_duration': total_duration,
            'duration_minutes': total_duration / 60,
            'processing_timestamp': datetime.now().isoformat(),
            'audio_quality': {
                'confidence': alternative.get('confidence', 0),
                'channels': metadata.get('channels', 1),
                'sample_rate': metadata.get('sample_rate', 0)
            }
        }

        # Generate AI summary with speaker analysis
        logger.info(" Generating AI summary with speaker analysis...")
        summary_data = ai_summarizer.generate_summary(
            transcript,
            nlp_results,
            speaker_analysis,
            enhanced_metadata
        )

        # Create key insights
        key_insights = {
            'conversation_overview': {
                'type': summary_data.get('conversation_type', 'general'),
                'duration_minutes': round(total_duration / 60, 1),
                'speaker_distribution': speaker_analysis,
                'word_density': round(word_count / (total_duration / 60), 1) if total_duration > 0 else 0
            },
            'emotional_analysis': {
                'overall_sentiment': nlp_results.get('sentiment', {}),
                'sentiment_trend': nlp_results.get('conversation_flow', {}).get('sentiment_trend', {}),
                'emotional_shifts': nlp_results.get('conversation_flow', {}).get('sentiment_shifts', 0),
                'per_speaker_sentiment': {
                    s: speaker_analysis[s].get('sentiment', {}) for s in speaker_analysis
                }
            },
            'content_analysis': {
                'main_topics': nlp_results.get('topics', [])[:5],
                'key_entities': nlp_results.get('entities', [])[:10],
                'primary_intents': nlp_results.get('intents', [])[:5],
                'language_style': nlp_results.get('pos_tags', {}).get('category_counts', {})
            },
            'interaction_patterns': {
                'turn_taking': timing_analysis.get('num_exchanges', 0),
                'interruptions': timing_analysis.get('interruptions', 0),
                'avg_gap': timing_analysis.get('avg_gap', 0),
                'conversation_pace': timing_analysis.get('conversation_pace', 0)
            },
            'speaker_summaries': summary_data.get('speaker_analysis', {})
        }

        # Prepare visualization data
        visualization_data = {
            'sentiment_over_time': [
                {'time': s['start'], 'sentiment': s['sentiment'].get('score', 0), 'speaker': s['speaker']}
                for s in formatted_paragraphs[:100]
            ],
            'speaker_distribution': [
                {'speaker': str(k), 'word_count': v['word_count'], 'percentage': v['contribution_percentage']}
                for k, v in speaker_analysis.items()
            ],
            'topic_cloud': [
                {'text': t.get('topic', ''), 'value': t.get('confidence', 0.5) * 100}
                for t in nlp_results.get('topics', [])[:15]
            ],
            'speaker_timing': timing_analysis
        }

        # Generate dashboard charts
        logger.info(" Generating visualizations...")
        charts = dashboard_analytics.generate_comprehensive_report(
            {
                'visualization_data': visualization_data,
                'speaker_analysis': speaker_analysis,
                'nlp_analysis': nlp_results,
                'ai_summary': summary_data,
                'metadata': enhanced_metadata
            },
            conversation_id
        )

        # Add timing_analysis to nlp_results for proper storage
        nlp_results['timing_analysis'] = timing_analysis

        enhanced_result = {
            'conversation_id': conversation_id,
            'metadata': enhanced_metadata,
            'transcript': {
                'full_text': transcript,
                'words': words[:500],  # Limit for response size
                'paragraphs': formatted_paragraphs,
                'speaker_timeline': timeline_segments[:50]
            },
            'speaker_analysis': speaker_analysis,
            'nlp_analysis': nlp_results,
            'ai_summary': summary_data,
            'key_insights': key_insights,
            'visualization_data': visualization_data,
            'charts': charts,  # Paths to generated charts
            'processing_metadata': {
                'deepgram_processing': True,
                'nlp_processing': True,
                'summary_generation': True,
                'enhancement_complete': True,
                'timestamp': datetime.now().isoformat()
            }
        }

        logger.info(" Data enhancement complete")
        return enhanced_result

    except Exception as e:
        logger.error(f" Data enhancement error: {e}", exc_info=True)
        return {
            'conversation_id': conversation_id,
            'metadata': deepgram_data.get('metadata', {}),
            'transcript': transcript if 'transcript' in locals() else '',
            'error': f'Enhancement failed: {str(e)}',
            'processing_metadata': {
                'enhancement_complete': False,
                'error': str(e)
            }
        }

@app.route('/api/conversations', methods=['GET'])
@token_required
def get_conversations():
    """Get conversation history for user"""
    try:
        user_id = request.user_id
        conversations = Conversation.query.filter_by(user_id=user_id).order_by(Conversation.created_at.desc()).all()

        return jsonify({
            'success': True,
            'data': [c.to_dict() for c in conversations]
        })

    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/conversations/<conversation_id>', methods=['GET'])
@token_required
def get_conversation(conversation_id):
    """Get specific conversation"""
    try:
        user_id = request.user_id
        conversation = Conversation.query.filter_by(conversation_id=conversation_id, user_id=user_id).first()

        if not conversation:
            return jsonify({
                'success': False,
                'error': 'Conversation not found'
            }), 404

        return jsonify({
            'success': True,
            'data': conversation.to_dict()
        })

    except Exception as e:
        logger.error(f"Error fetching conversation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/export/<conversation_id>', methods=['GET'])
@token_required
def export_conversation(conversation_id):
    """Export conversation analysis as HTML report"""
    try:
        user_id = request.user_id
        conversation = Conversation.query.filter_by(conversation_id=conversation_id, user_id=user_id).first()

        if not conversation:
            return jsonify({
                'success': False,
                'error': 'Conversation not found'
            }), 404

        # Generate comprehensive report with metadata
        analysis_result = conversation.to_dict()
        
        # Add metadata to the result
        analysis_result['metadata'] = {
            'conversation_id': conversation.conversation_id,
            'speaker_count': conversation.speaker_count,
            'word_count': conversation.word_count,
            'total_duration': conversation.duration or 0,
            'duration': conversation.duration or 0,
            'filename': conversation.filename
        }
        
        # Add speaker names if available
        if conversation.speaker_names_json:
            import json
            analysis_result['speaker_names'] = json.loads(conversation.speaker_names_json)
        else:
            analysis_result['speaker_names'] = {}

        # Generate charts
        charts = dashboard_analytics.generate_comprehensive_report(
            analysis_result,
            conversation_id
        )

        # Generate HTML report
        report_path = dashboard_analytics.export_to_html(
            analysis_result,
            charts,
            conversation_id
        )

        if report_path and os.path.exists(report_path):
            return send_from_directory(
                'static/reports',
                f'report_{conversation_id}.html',
                as_attachment=True,
                download_name=f'conversation_report_{conversation_id}.html'
            )
        else:
            logger.error(f"Report path not found: {report_path}")
            return jsonify({
                'success': False,
                'error': 'Report generation failed'
            }), 500

    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/conversations/<conversation_id>/speakers', methods=['PUT'])
@token_required
def update_speaker_names(conversation_id):
    """Update speaker names for a conversation"""
    try:
        user_id = request.user_id
        conversation = Conversation.query.filter_by(conversation_id=conversation_id, user_id=user_id).first()

        if not conversation:
            return jsonify({
                'success': False,
                'error': 'Conversation not found'
            }), 404

        data = request.get_json()
        if not data or 'speaker_names' not in data:
            return jsonify({
                'success': False,
                'error': 'speaker_names is required'
            }), 400

        speaker_names = data['speaker_names']
        
        # Validate speaker_names is a dict
        if not isinstance(speaker_names, dict):
            return jsonify({
                'success': False,
                'error': 'speaker_names must be a dictionary'
            }), 400

        # Save to database
        conversation.speaker_names_json = json.dumps(speaker_names)
        db.session.commit()

        logger.info(f"Updated speaker names for conversation {conversation_id}: {speaker_names}")

        return jsonify({
            'success': True,
            'message': 'Speaker names updated successfully',
            'speaker_names': speaker_names
        })

    except Exception as e:
        logger.error(f"Error updating speaker names: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/export/<conversation_id>/pdf', methods=['GET'])
@token_required
def export_conversation_pdf(conversation_id):
    """Export conversation analysis as PDF report"""
    try:
        user_id = request.user_id
        conversation = Conversation.query.filter_by(conversation_id=conversation_id, user_id=user_id).first()

        if not conversation:
            return jsonify({
                'success': False,
                'error': 'Conversation not found'
            }), 404

        # Ensure reports directory exists
        os.makedirs('static/reports', exist_ok=True)

        # Generate comprehensive report with metadata
        analysis_result = conversation.to_dict()
        
        # Add metadata to the result
        analysis_result['metadata'] = {
            'conversation_id': conversation.conversation_id,
            'speaker_count': conversation.speaker_count,
            'word_count': conversation.word_count,
            'total_duration': conversation.duration or 0,
            'duration': conversation.duration or 0,
            'filename': conversation.filename
        }
        
        # Add speaker names if available
        if conversation.speaker_names_json:
            analysis_result['speaker_names'] = json.loads(conversation.speaker_names_json)
        else:
            analysis_result['speaker_names'] = {}

        # Generate PDF report
        try:
            pdf_path = dashboard_analytics.export_to_pdf(
                analysis_result,
                conversation_id
            )
        except Exception as pdf_error:
            logger.error(f"PDF generation error: {pdf_error}")
            return jsonify({
                'success': False,
                'error': f'PDF generation error: {str(pdf_error)}'
            }), 500

        if pdf_path and os.path.exists(pdf_path):
            return send_from_directory(
                'static/reports',
                f'report_{conversation_id}.pdf',
                as_attachment=True,
                download_name=f'conversation_report_{conversation_id}.pdf'
            )
        else:
            logger.error(f"PDF report path not found: {pdf_path}")
            return jsonify({
                'success': False,
                'error': 'PDF report generation failed - please try again'
            }), 500

    except Exception as e:
        logger.error(f"PDF Export error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stream/start', methods=['POST'])
@token_required
def start_stream():
    """Start a live streaming session"""
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id') or f"live_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        return jsonify({
            'success': True,
            'session_id': session_id,
            'websocket_url': f"wss://api.deepgram.com/v1/listen",
            'token': DEEPGRAM_API_KEY,
            'message': 'Live streaming session created'
        })
    except Exception as e:
        logger.error(f" Stream start error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/features', methods=['GET'])
def get_features():
    """Get available features and capabilities"""
    return jsonify({
        'success': True,
        'features': {
            'speech_processing': [
                'voice_activity_detection',
                'speaker_diarization',
                'automatic_speech_recognition',
                'noise_reduction',
                'multi_speaker_support',
                'speaker_identification'
            ],
            'nlp_analysis': [
                'sentiment_analysis',
                'named_entity_recognition',
                'topic_detection',
                'intent_detection',
                'key_phrase_extraction',
                'conversation_flow_analysis',
                'text_statistics',
                'pos_tagging',
                'timing_analysis'
            ],
            'ai_capabilities': [
                'ai_summary_generation',
                'speaker_wise_summary',
                'insight_extraction',
                'trend_analysis',
                'pattern_recognition',
                'action_item_detection'
            ],
            'visualization': [
                'sentiment_timeline',
                'speaker_distribution',
                'topic_cloud',
                'interaction_network',
                'conversation_flow',
                'speaker_timing',
                'export_reports'
            ]
        },
        'workflow': [
            'Audio Upload & Validation',
            'Voice Activity Detection',
            'Speaker Diarization',
            'Speech Recognition',
            'NLP Processing',
            'POS Tagging',
            'Timing Analysis',
            'AI Summary Generation',
            'Speaker-wise Analysis',
            'Insight Extraction',
            'Report Generation',
            'Dashboard Visualization'
        ],
        'supported_formats': list(app.config['ALLOWED_EXTENSIONS']),
        'max_file_size': f"{app.config['MAX_CONTENT_LENGTH'] // (1024*1024)}MB"
    })

# Serve frontend files
@app.route('/<path:path>')
def serve_frontend(path):
    """Serve frontend static files"""
    try:
        return send_from_directory('frontend', path)
    except:
        return jsonify({
            'success': False,
            'error': 'File not found'
        }), 404

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'success': False,
        'error': 'Method not allowed'
    }), 405

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        'success': False,
        'error': f'File too large. Maximum size is {app.config["MAX_CONTENT_LENGTH"] // (1024*1024)}MB'
    }), 413

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('FLASK_DEBUG', '1').lower() in ['1', 'true', 'yes']

    banner = f"""
    {'='*70}
    CONVERSATION ANALYTICS PLATFORM v2.0
    {'='*70}

    Configuration:
    * Port: {port}
    * Debug Mode: {'Enabled' if debug else 'Disabled'}
    * Upload Folder: {app.config['UPLOAD_FOLDER']}
    * Max File Size: {app.config['MAX_CONTENT_LENGTH'] // (1024*1024)}MB
    * Database: SQLite

    Features Enabled:
    * Voice Activity Detection: YES
    * Speaker Diarization: YES
    * Speech Recognition: YES
    * Sentiment Analysis: YES
    * Named Entity Recognition: YES
    * Topic Detection: YES
    * Intent Detection: YES
    * POS Tagging: YES
    * Timing Analysis: YES
    * AI Summary Generation: YES
    * Speaker-wise Summaries: YES
    * Interactive Dashboard: YES

    API Status:
    * Deepgram API: {'CONFIGURED' if DEEPGRAM_API_KEY else 'NOT CONFIGURED'}
    * NLP Processor: READY
    * AI Summarizer: READY
    * Voice Processor: READY
    * Speaker Identifier: READY
    * Dashboard Analytics: READY

    Available Endpoints:
    * /api/auth/register   (POST) - Register user
    * /api/auth/login      (POST) - Login
    * /api/auth/verify     (GET)  - Verify token
    * /api/upload          (POST) - Upload audio file
    * /api/transcribe      (POST) - Complete analysis
    * /api/stream/start    (POST) - Start live streaming
    * /api/conversations   (GET)  - List conversations
    * /api/export/<id>     (GET)  - Export report
    * /api/features        (GET)  - Available features
    * /api/health          (GET)  - Health check
    * /                    (GET)  - Login page
    * /dashboard           (GET)  - Dashboard

    {'='*70}
    """

    print(banner)

    if not DEEPGRAM_API_KEY:
        print(" WARNING: DEEPGRAM_API_KEY not configured!")
        print("   Add to .env file: DEEPGRAM_API_KEY=your_api_key_here")
        print("   Get API key from: https://console.deepgram.com/signup")
        print("   Speech recognition will not work without this key.\n")

    print(f" Server starting on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=False)