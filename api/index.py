"""
Vercel Serverless Entry Point for Mitra Bot
"""
import sys
import os

# Add the parent directory to Python path (so we can import app.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import the Flask app
from app import app

# Initialize the app for serverless
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', '')

# Vercel expects the app to be available as a module-level variable
# The app will be called by Vercel's Python runtime
