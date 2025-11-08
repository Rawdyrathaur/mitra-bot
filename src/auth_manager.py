#!/usr/bin/env python3
"""
Authentication Manager for Mitra Bot
Handles user registration, login, JWT tokens, and session management
"""
import jwt
import bcrypt
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict
import logging
from functools import wraps
from flask import request, jsonify
import os

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24 * 7  # 7 days


class AuthManager:
    """Manages user authentication and authorization"""

    def __init__(self, db_path: str = "mitra_bot.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize the database with users table"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Create users table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT UNIQUE NOT NULL,
                        username TEXT NOT NULL,
                        password_hash TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_login DATETIME,
                        is_active BOOLEAN DEFAULT 1,
                        avatar_url TEXT
                    )
                ''')

                # Create sessions table for tracking active sessions
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        session_token TEXT UNIQUE NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        expires_at DATETIME NOT NULL,
                        user_agent TEXT,
                        ip_address TEXT,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                ''')

                conn.commit()
                logger.info("Auth database initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing auth database: {e}")
            raise

    def register_user(self, email: str, username: str, password: str) -> Dict:
        """Register a new user"""
        try:
            # Validate input
            if not email or not username or not password:
                return {'success': False, 'error': 'All fields are required'}

            if len(password) < 8:
                return {'success': False, 'error': 'Password must be at least 8 characters'}

            # Hash password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Check if email already exists
                cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
                if cursor.fetchone():
                    return {'success': False, 'error': 'Email already registered'}

                # Insert new user
                cursor.execute(
                    "INSERT INTO users (email, username, password_hash) VALUES (?, ?, ?)",
                    (email, username, password_hash)
                )
                user_id = cursor.lastrowid
                conn.commit()

                # Generate JWT token
                token = self.generate_token(user_id, email, username)

                logger.info(f"User registered successfully: {email}")
                return {
                    'success': True,
                    'access_token': token,
                    'user': {
                        'id': user_id,
                        'email': email,
                        'name': username
                    }
                }

        except Exception as e:
            logger.error(f"Error registering user: {e}")
            return {'success': False, 'error': 'Registration failed'}

    def login_user(self, email: str, password: str) -> Dict:
        """Authenticate user and return JWT token"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get user from database
                cursor.execute(
                    "SELECT id, email, username, password_hash, is_active FROM users WHERE email = ?",
                    (email,)
                )
                user = cursor.fetchone()

                if not user:
                    return {'success': False, 'error': 'Invalid email or password'}

                user_id, email, username, password_hash, is_active = user

                # Check if user is active
                if not is_active:
                    return {'success': False, 'error': 'Account is disabled'}

                # Verify password
                if not bcrypt.checkpw(password.encode('utf-8'), password_hash):
                    return {'success': False, 'error': 'Invalid email or password'}

                # Update last login
                cursor.execute(
                    "UPDATE users SET last_login = ? WHERE id = ?",
                    (datetime.now(), user_id)
                )
                conn.commit()

                # Generate JWT token
                token = self.generate_token(user_id, email, username)

                logger.info(f"User logged in successfully: {email}")
                return {
                    'success': True,
                    'access_token': token,
                    'user': {
                        'id': user_id,
                        'email': email,
                        'name': username
                    }
                }

        except Exception as e:
            logger.error(f"Error logging in user: {e}")
            return {'success': False, 'error': 'Login failed'}

    def generate_token(self, user_id: int, email: str, username: str) -> str:
        """Generate JWT token for user"""
        payload = {
            'user_id': user_id,
            'sub': user_id,  # Standard JWT claim
            'email': email,
            'name': username,
            'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            'iat': datetime.utcnow()
        }

        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return token

    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user information by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, email, username, created_at, last_login, avatar_url FROM users WHERE id = ?",
                    (user_id,)
                )
                user = cursor.fetchone()

                if user:
                    return {
                        'id': user[0],
                        'email': user[1],
                        'name': user[2],
                        'created_at': user[3],
                        'last_login': user[4],
                        'avatar_url': user[5]
                    }

                return None

        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None

    def update_user_profile(self, user_id: int, data: Dict) -> bool:
        """Update user profile"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                allowed_fields = ['username', 'avatar_url']
                update_fields = []
                values = []

                for field in allowed_fields:
                    if field in data:
                        update_fields.append(f"{field} = ?")
                        values.append(data[field])

                if not update_fields:
                    return False

                values.append(user_id)
                query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
                cursor.execute(query, values)
                conn.commit()

                return True

        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            return False

    def change_password(self, user_id: int, current_password: str, new_password: str) -> Dict:
        """Change user password"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get current password hash
                cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
                result = cursor.fetchone()

                if not result:
                    return {'success': False, 'error': 'User not found'}

                password_hash = result[0]

                # Verify current password
                if not bcrypt.checkpw(current_password.encode('utf-8'), password_hash):
                    return {'success': False, 'error': 'Current password is incorrect'}

                # Validate new password
                if len(new_password) < 8:
                    return {'success': False, 'error': 'New password must be at least 8 characters'}

                # Hash and update new password
                new_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
                cursor.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (new_password_hash, user_id)
                )
                conn.commit()

                return {'success': True}

        except Exception as e:
            logger.error(f"Error changing password: {e}")
            return {'success': False, 'error': 'Failed to change password'}


def require_auth(f):
    """Decorator to require authentication for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authentication required'}), 401

        token = auth_header.split('Bearer ')[1]
        auth_manager = AuthManager()
        payload = auth_manager.verify_token(token)

        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401

        # Add user info to request context
        request.user_id = payload['user_id']
        request.user_email = payload['email']

        return f(*args, **kwargs)

    return decorated_function


def optional_auth(f):
    """Decorator to optionally check authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split('Bearer ')[1]
            auth_manager = AuthManager()
            payload = auth_manager.verify_token(token)

            if payload:
                request.user_id = payload['user_id']
                request.user_email = payload['email']
            else:
                request.user_id = None
                request.user_email = None
        else:
            request.user_id = None
            request.user_email = None

        return f(*args, **kwargs)

    return decorated_function
