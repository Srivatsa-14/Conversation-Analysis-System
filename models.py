from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import bcrypt

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

    conversations = db.relationship('Conversation', backref='user', lazy=True)

    def set_password(self, password):
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class Conversation(db.Model):
    __tablename__ = 'conversations'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Basic info
    filename = db.Column(db.String(255))
    file_size = db.Column(db.Integer)
    duration = db.Column(db.Float)
    speaker_count = db.Column(db.Integer, default=1)
    word_count = db.Column(db.Integer, default=0)

    # Speaker naming
    speaker_names_json = db.Column(db.Text)

    # Analysis results (stored as JSON)
    transcript_json = db.Column(db.Text)
    speaker_analysis_json = db.Column(db.Text)
    nlp_analysis_json = db.Column(db.Text)
    summary_json = db.Column(db.Text)
    insights_json = db.Column(db.Text)
    visualization_json = db.Column(db.Text)
    charts_json = db.Column(db.Text)

    # Metadata
    conversation_type = db.Column(db.String(50), default='general')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    is_public = db.Column(db.Boolean, default=False)

    def to_dict(self):
        import json
        return {
            'id': self.conversation_id,
            'conversation_id': self.conversation_id,
            'filename': self.filename,
            'duration': self.duration,
            'speaker_count': self.speaker_count,
            'word_count': self.word_count,
            'speaker_names': json.loads(self.speaker_names_json) if self.speaker_names_json else {},
            'conversation_type': self.conversation_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'transcript': json.loads(self.transcript_json) if self.transcript_json else {},
            'speaker_analysis': json.loads(self.speaker_analysis_json) if self.speaker_analysis_json else {},
            'nlp_analysis': json.loads(self.nlp_analysis_json) if self.nlp_analysis_json else {},
            'ai_summary': json.loads(self.summary_json) if self.summary_json else {},
            'summary': json.loads(self.summary_json) if self.summary_json else {},
            'insights': json.loads(self.insights_json) if self.insights_json else {},
            'metadata': {
                'speaker_count': self.speaker_count,
                'word_count': self.word_count,
                'total_duration': self.duration or 0,
                'duration': self.duration or 0,
                'duration_minutes': (self.duration / 60) if self.duration else 0,
                'filename': self.filename
            },
            'key_insights': json.loads(self.insights_json) if self.insights_json else {},
            'visualization_data': json.loads(self.visualization_json) if self.visualization_json else {
                'sentiment_over_time': [],
                'speaker_distribution': [],
                'topic_cloud': [],
                'speaker_timing': {}
            },
            'charts': json.loads(self.charts_json) if self.charts_json else {}
        }