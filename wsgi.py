"""
WSGI Entry Point for Production Deployment
Use with Gunicorn: gunicorn -c gunicorn_config.py wsgi:app
"""
import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import the Flask app
from api.main_api import app
from utils.logger import setup_error_tracking, get_logger

# Setup error tracking
setup_error_tracking()

# Get logger
logger = get_logger(__name__)
logger.info("Mitra Bot WSGI application starting...")

# Export app for WSGI server
application = app

if __name__ == "__main__":
    # This is only for debugging. In production, use gunicorn
    port = int(os.environ.get('PORT', 5000))
    logger.warning("Running with built-in Flask server. Use Gunicorn for production!")
    app.run(host='0.0.0.0', port=port, debug=False)
