"""
Vercel Serverless Entry Point for Mitra Bot
Lightweight version to avoid OOM errors
"""
import sys
import os

# Add the parent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import minimal Flask app for Vercel
# Note: Full app.py may have heavy dependencies that cause OOM
# Use lightweight version for serverless deployment
try:
    from src.api.main_api import app
except ImportError:
    # Fallback to basic app if full version fails
    from flask import Flask, jsonify

    app = Flask(__name__)

    @app.route('/api/health')
    def health():
        return jsonify({'status': 'healthy', 'platform': 'vercel'})

    @app.route('/')
    def index():
        return jsonify({
            'name': 'Mitra Bot API',
            'message': 'Deploy to a server for full functionality',
            'platform': 'Vercel Serverless'
        })

# Vercel expects the app to be available as a module-level variable
