import jwt
import datetime
import logging
from functools import wraps
from flask import request, jsonify, current_app
from models import User, db

logger = logging.getLogger(__name__)

class AuthService:
    """Handles user authentication and authorization"""

    def __init__(self, app=None):
        self.app = app
        self.secret_key = app.config.get('SECRET_KEY', 'conversation-analytics-secret-key-2024')
        if app:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        self.secret_key = app.config.get('SECRET_KEY', 'conversation-analytics-secret-key-2024')

    def generate_token(self, user_id):
        """Generate JWT token for user"""
        payload = {
            'user_id': user_id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7),
            'iat': datetime.datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')

    def verify_token(self, token):
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload['user_id']
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def register_user(self, email, password, name=None):
        """Register a new user"""
        try:
            # Check if user exists
            if User.query.filter_by(email=email).first():
                return {'success': False, 'error': 'Email already registered'}

            # Create new user
            user = User(
                email=email,
                name=name,
                created_at=datetime.datetime.utcnow()
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            # Generate token
            token = self.generate_token(user.id)

            return {
                'success': True,
                'user': user.to_dict(),
                'token': token
            }

        except Exception as e:
            logger.error(f"Registration error: {e}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}

    def login_user(self, email, password):
        """Login user"""
        try:
            user = User.query.filter_by(email=email).first()

            if not user or not user.check_password(password):
                return {'success': False, 'error': 'Invalid email or password'}

            # Update last login
            user.last_login = datetime.datetime.utcnow()
            db.session.commit()

            # Generate token
            token = self.generate_token(user.id)

            return {
                'success': True,
                'user': user.to_dict(),
                'token': token
            }

        except Exception as e:
            logger.error(f"Login error: {e}")
            return {'success': False, 'error': str(e)}

    def get_user_from_token(self, token):
        """Get user from token"""
        user_id = self.verify_token(token)
        if not user_id:
            return None
        return User.query.get(user_id)

def token_required(f):
    """Decorator to require valid token for routes"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Get token from header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'success': False, 'error': 'Token is missing'}), 401

        auth_service = AuthService(current_app)
        user_id = auth_service.verify_token(token)

        if not user_id:
            return jsonify({'success': False, 'error': 'Invalid or expired token'}), 401

        # Add user_id to request context
        request.user_id = user_id

        return f(*args, **kwargs)

    return decorated