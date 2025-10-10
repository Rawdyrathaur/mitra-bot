"""
Vercel Serverless Entry Point for Mitra Bot
"""
import sys
import os

# Add the mitra-bot directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mitra-bot'))

# Import the Flask app
from app import app

# Vercel expects the app to be available
# No need to run app.run() - Vercel handles that
