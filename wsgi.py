"""
WSGI Entry Point for Production Deployment
Use with Gunicorn: gunicorn -c gunicorn_config.py wsgi:app
"""
import os
import sys
from flask import send_from_directory

# Add src directory to path
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import the Flask app
import_error = None
try:
    from src.simple_api import app
except Exception as e:
    import_error = str(e)
    print(f"Error importing simple_api: {e}")
    from flask import Flask, jsonify
    app = Flask(__name__)

    @app.route('/api/health')
    def health():
        return jsonify({'status': 'healthy', 'error': import_error})

# Frontend routes are now handled by simple_api.py

# Export app for WSGI server
application = app

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    print(f"\n{'='*60}")
    print(f"Mitra Bot Starting...")
    print(f"{'='*60}")
    print(f"Frontend: http://localhost:{port}")
    print(f"API: http://localhost:{port}/api/health")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=port, debug=True)
