"""
Comprehensive REST API for SAM Bot
Includes authentication, document management, chat, analytics, and admin endpoints
"""
import os
import logging
import json
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from functools import wraps

from flask import Flask, request, jsonify, session, send_file
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import bcrypt

# Import our services
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_manager import DatabaseManager
from services.document_service import DocumentProcessor, DocumentUploadHandler
from services.knowledge_service import KnowledgeSearchEngine, KnowledgeManagement
from services.conversation_service import ConversationEngine, ConversationTemplates

# Security and validation
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
import secrets

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', secrets.token_hex(32))
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_FILE_SIZE', 16 * 1024 * 1024))  # 16MB

# Initialize extensions
CORS(app, origins=os.getenv('ALLOWED_ORIGINS', '*').split(','))
jwt = JWTManager(app)
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["1000 per day", "100 per hour"]
)

# Initialize services
db_manager = DatabaseManager()
doc_processor = DocumentProcessor(db_manager)
doc_uploader = DocumentUploadHandler(doc_processor)
knowledge_engine = KnowledgeSearchEngine(db_manager)
knowledge_mgmt = KnowledgeManagement(db_manager, knowledge_engine)
conversation_engine = ConversationEngine(db_manager, knowledge_engine)
templates = ConversationTemplates()

# Authentication decorator for admin routes
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            current_user = get_jwt_identity()
            if not current_user:
                return jsonify({'error': 'Authentication required'}), 401
            
            # Check if user is admin
            user_info = db_manager.get_user_by_email(current_user)
            if not user_info or user_info.get('role') != 'admin':
                return jsonify({'error': 'Admin access required'}), 403
            
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in admin_required decorator: {e}")
            return jsonify({'error': 'Authorization error'}), 500
    
    return decorated_function

# Helper functions
def generate_session_id():
    """Generate a unique session ID"""
    return str(uuid.uuid4())

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password: str, hashed: str) -> bool:
    """Check password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# Health and Status Endpoints
@app.route('/api/health', methods=['GET'])
def health_check():
    """Comprehensive health check"""
    try:
        db_health = db_manager.health_check()
        
        # Check Redis connectivity
        redis_healthy = True
        try:
            db_manager.conversation_memory.redis.ping()
        except:
            redis_healthy = False
        
        # Check OpenAI connectivity
        openai_healthy = conversation_engine.client is not None
        
        status = {
            'status': 'healthy' if all([
                db_health.get('database') == 'healthy',
                redis_healthy,
                openai_healthy
            ]) else 'degraded',
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'database': db_health,
                'redis': 'healthy' if redis_healthy else 'unhealthy',
                'openai': 'healthy' if openai_healthy else 'unhealthy'
            },
            'version': '1.0.0'
        }
        
        return jsonify(status), 200 if status['status'] == 'healthy' else 503
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503

@app.route('/api/status', methods=['GET'])
@jwt_required()
@admin_required
def system_status():
    """Detailed system status for administrators"""
    try:
        # Get comprehensive system statistics
        knowledge_stats = knowledge_mgmt.get_knowledge_stats()
        analytics = conversation_engine.get_conversation_analytics()
        categories = knowledge_mgmt.get_categories()
        
        return jsonify({
            'knowledge_base': knowledge_stats,
            'conversations': analytics,
            'categories': categories,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({'error': str(e)}), 500

# Authentication Endpoints
@app.route('/api/auth/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    """User registration"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['email', 'username', 'password']):
            return jsonify({'error': 'Email, username, and password are required'}), 400
        
        email = data['email'].lower().strip()
        username = data['username'].strip()
        password = data['password']
        
        # Validate inputs
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        
        # Check if user already exists
        if db_manager.get_user_by_email(email):
            return jsonify({'error': 'User already exists'}), 409
        
        # Create user
        password_hash = hash_password(password)
        user_id = db_manager.create_user(email, username, password_hash)
        
        # Generate access token
        access_token = create_access_token(identity=email)
        
        return jsonify({
            'message': 'User registered successfully',
            'user_id': user_id,
            'access_token': access_token
        }), 201
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """User login"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['email', 'password']):
            return jsonify({'error': 'Email and password are required'}), 400
        
        email = data['email'].lower().strip()
        password = data['password']
        
        # Get user
        user = db_manager.get_user_by_email(email)
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Check password
        if not check_password(password, user.get('password_hash', '')):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Update login time and generate token
        authenticated_user = db_manager.authenticate_user(email, hash_password(password))
        if authenticated_user:
            access_token = create_access_token(identity=email)
            
            return jsonify({
                'message': 'Login successful',
                'user': {
                    'id': authenticated_user['id'],
                    'email': authenticated_user['email'],
                    'username': authenticated_user['username'],
                    'role': authenticated_user['role']
                },
                'access_token': access_token
            })
        else:
            return jsonify({'error': 'Authentication failed'}), 401
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    """User logout (client-side token invalidation)"""
    return jsonify({'message': 'Logged out successfully'})

@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user information"""
    try:
        current_user_email = get_jwt_identity()
        user = db_manager.get_user_by_email(current_user_email)
        
        if user:
            return jsonify({
                'user': {
                    'id': user['id'],
                    'email': user['email'],
                    'username': user['username'],
                    'role': user['role'],
                    'created_at': user['created_at']
                }
            })
        else:
            return jsonify({'error': 'User not found'}), 404
        
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        return jsonify({'error': str(e)}), 500

# Chat Endpoints
@app.route('/api/chat', methods=['POST'])
@limiter.limit("60 per minute")
def chat():
    """Main chat endpoint with RAG capabilities"""
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        
        message = data['message'].strip()
        if not message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        session_id = data.get('session_id') or generate_session_id()
        user_id = None
        
        # Get user ID if authenticated
        try:
            if 'Authorization' in request.headers:
                from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
                verify_jwt_in_request()
                current_user_email = get_jwt_identity()
                user_info = db_manager.get_user_by_email(current_user_email)
                user_id = user_info['id'] if user_info else None
        except:
            pass  # Allow anonymous users
        
        # Generate response
        response_data = await conversation_engine.generate_response(
            message, session_id, user_id
        )
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({'error': 'Chat service temporarily unavailable'}), 500

@app.route('/api/chat/rate', methods=['POST'])
def rate_response():
    """Rate a chat response"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['conversation_id', 'rating']):
            return jsonify({'error': 'Conversation ID and rating are required'}), 400
        
        conversation_id = data['conversation_id']
        rating = data['rating']
        comment = data.get('comment')
        
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({'error': 'Rating must be an integer between 1 and 5'}), 400
        
        success = conversation_engine.rate_response(conversation_id, rating, comment)
        
        if success:
            return jsonify({'message': 'Rating recorded successfully'})
        else:
            return jsonify({'error': 'Failed to record rating'}), 500
        
    except Exception as e:
        logger.error(f"Rating error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/suggestions', methods=['GET'])
def get_suggestions():
    """Get conversation suggestions"""
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({'error': 'Session ID is required'}), 400
        
        suggestions = conversation_engine.get_conversation_suggestions(session_id)
        
        return jsonify({'suggestions': suggestions})
        
    except Exception as e:
        logger.error(f"Suggestions error: {e}")
        return jsonify({'error': str(e)}), 500

# Document Management Endpoints
@app.route('/api/documents/upload', methods=['POST'])
@jwt_required()
@limiter.limit("10 per minute")
def upload_document():
    """Upload and process a document"""
    try:
        current_user_email = get_jwt_identity()
        user_info = db_manager.get_user_by_email(current_user_email)
        user_id = user_info['id'] if user_info else None
        
        # Handle file upload
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get additional parameters
        title = request.form.get('title')
        category = request.form.get('category')
        
        # Validate file
        is_valid, validation_message = doc_uploader.validate_file(
            file.filename, 
            len(file.read())
        )\n        file.seek(0)  # Reset file pointer\n        \n        if not is_valid:\n            return jsonify({'error': validation_message}), 400\n        \n        # Process upload\n        result = await doc_uploader.handle_file_upload(\n            file, \n            file.filename,\n            title=title,\n            uploaded_by=user_id,\n            category=category\n        )\n        \n        if result['success']:\n            return jsonify({\n                'message': 'Document uploaded successfully',\n                'document_id': result['document_id']\n            }), 201\n        else:\n            return jsonify({'error': result['error']}), 500\n        \n    except Exception as e:\n        logger.error(f\"Document upload error: {e}\")\n        return jsonify({'error': 'Upload failed'}), 500\n\n@app.route('/api/documents/text', methods=['POST'])\n@jwt_required()\ndef upload_text_content():\n    \"\"\"Upload raw text content\"\"\"\n    try:\n        current_user_email = get_jwt_identity()\n        user_info = db_manager.get_user_by_email(current_user_email)\n        user_id = user_info['id'] if user_info else None\n        \n        data = request.get_json()\n        \n        if not data or 'content' not in data:\n            return jsonify({'error': 'Content is required'}), 400\n        \n        title = data.get('title', 'Untitled Document')\n        content = data['content']\n        category = data.get('category')\n        \n        if not content.strip():\n            return jsonify({'error': 'Content cannot be empty'}), 400\n        \n        # Process content\n        doc_id = await doc_processor.process_text_content(\n            title, content, uploaded_by=user_id, category=category\n        )\n        \n        return jsonify({\n            'message': 'Text content processed successfully',\n            'document_id': doc_id\n        }), 201\n        \n    except Exception as e:\n        logger.error(f\"Text upload error: {e}\")\n        return jsonify({'error': 'Processing failed'}), 500\n\n@app.route('/api/documents', methods=['GET'])\ndef list_documents():\n    \"\"\"List documents with optional filtering\"\"\"\n    try:\n        category = request.args.get('category')\n        status = request.args.get('status')\n        limit = int(request.args.get('limit', 20))\n        offset = int(request.args.get('offset', 0))\n        \n        documents = doc_processor.list_documents(\n            category=category,\n            status=status,\n            limit=limit,\n            offset=offset\n        )\n        \n        return jsonify({\n            'documents': documents,\n            'limit': limit,\n            'offset': offset\n        })\n        \n    except Exception as e:\n        logger.error(f\"List documents error: {e}\")\n        return jsonify({'error': str(e)}), 500\n\n@app.route('/api/documents/<document_id>', methods=['GET'])\ndef get_document(document_id):\n    \"\"\"Get detailed document information\"\"\"\n    try:\n        document_info = doc_processor.get_document_info(document_id)\n        \n        if 'error' in document_info:\n            return jsonify(document_info), 404\n        \n        return jsonify({'document': document_info})\n        \n    except Exception as e:\n        logger.error(f\"Get document error: {e}\")\n        return jsonify({'error': str(e)}), 500\n\n@app.route('/api/documents/<document_id>', methods=['DELETE'])\n@jwt_required()\ndef delete_document(document_id):\n    \"\"\"Delete a document\"\"\"\n    try:\n        current_user_email = get_jwt_identity()\n        user_info = db_manager.get_user_by_email(current_user_email)\n        user_id = user_info['id'] if user_info else None\n        \n        success = doc_processor.delete_document(document_id, user_id)\n        \n        if success:\n            return jsonify({'message': 'Document deleted successfully'})\n        else:\n            return jsonify({'error': 'Document not found'}), 404\n        \n    except Exception as e:\n        logger.error(f\"Delete document error: {e}\")\n        return jsonify({'error': str(e)}), 500\n\n# Search Endpoints\n@app.route('/api/search', methods=['GET', 'POST'])\n@limiter.limit(\"30 per minute\")\ndef search_knowledge():\n    \"\"\"Search the knowledge base\"\"\"\n    try:\n        if request.method == 'GET':\n            query = request.args.get('q', '').strip()\n            search_type = request.args.get('type', 'semantic')\n            category = request.args.get('category')\n            limit = int(request.args.get('limit', 10))\n        else:\n            data = request.get_json()\n            query = data.get('query', '').strip()\n            search_type = data.get('type', 'semantic')\n            category = data.get('category')\n            limit = int(data.get('limit', 10))\n        \n        if not query:\n            return jsonify({'error': 'Query is required'}), 400\n        \n        filters = {}\n        if category:\n            filters['category'] = category\n        \n        # Perform search\n        if search_type == 'advanced':\n            facets = ['category', 'document_type']\n            results = await knowledge_engine.advanced_search(query, 'all', filters, facets)\n        else:\n            results = await knowledge_engine.semantic_search(query, filters, limit)\n        \n        return jsonify(results)\n        \n    except Exception as e:\n        logger.error(f\"Search error: {e}\")\n        return jsonify({'error': str(e)}), 500\n\n@app.route('/api/search/suggestions', methods=['GET'])\ndef search_suggestions():\n    \"\"\"Get search suggestions for autocomplete\"\"\"\n    try:\n        partial_query = request.args.get('q', '').strip()\n        limit = int(request.args.get('limit', 5))\n        \n        if len(partial_query) < 2:\n            return jsonify({'suggestions': []})\n        \n        suggestions = knowledge_engine.get_search_suggestions(partial_query, limit)\n        \n        return jsonify({'suggestions': suggestions})\n        \n    except Exception as e:\n        logger.error(f\"Search suggestions error: {e}\")\n        return jsonify({'error': str(e)}), 500\n\n# Conversation Management\n@app.route('/api/conversations/<session_id>', methods=['GET'])\ndef get_conversation_history(session_id):\n    \"\"\"Get conversation history for a session\"\"\"\n    try:\n        limit = int(request.args.get('limit', 10))\n        \n        history = db_manager.conversation_memory.get_conversation_history(session_id, limit)\n        \n        return jsonify({\n            'session_id': session_id,\n            'conversations': history,\n            'total': len(history)\n        })\n        \n    except Exception as e:\n        logger.error(f\"Get conversation history error: {e}\")\n        return jsonify({'error': str(e)}), 500\n\n@app.route('/api/conversations/<session_id>/export', methods=['GET'])\ndef export_conversation(session_id):\n    \"\"\"Export conversation history\"\"\"\n    try:\n        format_type = request.args.get('format', 'json').lower()\n        \n        if format_type not in ['json', 'txt']:\n            return jsonify({'error': 'Supported formats: json, txt'}), 400\n        \n        exported_data = conversation_engine.export_conversation(session_id, format_type)\n        \n        if exported_data:\n            return jsonify({\n                'session_id': session_id,\n                'format': format_type,\n                'data': exported_data\n            })\n        else:\n            return jsonify({'error': 'Export failed'}), 500\n        \n    except Exception as e:\n        logger.error(f\"Export conversation error: {e}\")\n        return jsonify({'error': str(e)}), 500\n\n@app.route('/api/conversations/<session_id>', methods=['DELETE'])\ndef clear_conversation(session_id):\n    \"\"\"Clear conversation history\"\"\"\n    try:\n        success = conversation_engine.clear_conversation(session_id)\n        \n        if success:\n            return jsonify({'message': 'Conversation cleared successfully'})\n        else:\n            return jsonify({'error': 'Failed to clear conversation'}), 500\n        \n    except Exception as e:\n        logger.error(f\"Clear conversation error: {e}\")\n        return jsonify({'error': str(e)}), 500\n\n# Analytics Endpoints (Admin only)\n@app.route('/api/analytics/overview', methods=['GET'])\n@jwt_required()\n@admin_required\ndef analytics_overview():\n    \"\"\"Get comprehensive analytics overview\"\"\"\n    try:\n        days = int(request.args.get('days', 7))\n        \n        # Get analytics from multiple sources\n        conversation_analytics = conversation_engine.get_conversation_analytics(days)\n        search_analytics = knowledge_engine.get_search_analytics(days)\n        system_analytics = db_manager.get_analytics_summary(days)\n        \n        return jsonify({\n            'period_days': days,\n            'conversations': conversation_analytics,\n            'search': search_analytics,\n            'system': system_analytics,\n            'timestamp': datetime.utcnow().isoformat()\n        })\n        \n    except Exception as e:\n        logger.error(f\"Analytics overview error: {e}\")\n        return jsonify({'error': str(e)}), 500\n\n@app.route('/api/analytics/conversations', methods=['GET'])\n@jwt_required()\n@admin_required\ndef conversation_analytics():\n    \"\"\"Get detailed conversation analytics\"\"\"\n    try:\n        days = int(request.args.get('days', 7))\n        analytics = conversation_engine.get_conversation_analytics(days)\n        \n        return jsonify(analytics)\n        \n    except Exception as e:\n        logger.error(f\"Conversation analytics error: {e}\")\n        return jsonify({'error': str(e)}), 500\n\n# Knowledge Base Management (Admin)\n@app.route('/api/knowledge/categories', methods=['GET'])\ndef get_categories():\n    \"\"\"Get all document categories\"\"\"\n    try:\n        categories = knowledge_mgmt.get_categories()\n        return jsonify({'categories': categories})\n        \n    except Exception as e:\n        logger.error(f\"Get categories error: {e}\")\n        return jsonify({'error': str(e)}), 500\n\n@app.route('/api/knowledge/stats', methods=['GET'])\n@jwt_required()\n@admin_required\ndef knowledge_stats():\n    \"\"\"Get knowledge base statistics\"\"\"\n    try:\n        stats = knowledge_mgmt.get_knowledge_stats()\n        return jsonify(stats)\n        \n    except Exception as e:\n        logger.error(f\"Knowledge stats error: {e}\")\n        return jsonify({'error': str(e)}), 500\n\n# Configuration Management (Admin)\n@app.route('/api/config', methods=['GET'])\n@jwt_required()\n@admin_required\ndef get_configuration():\n    \"\"\"Get system configuration\"\"\"\n    try:\n        # Get all configuration keys (this would be a proper admin interface)\n        config_keys = [\n            'max_file_size', 'chunk_size', 'chunk_overlap', 'similarity_threshold',\n            'conversation_context_window', 'enable_analytics', 'enable_feedback'\n        ]\n        \n        config = {}\n        for key in config_keys:\n            config[key] = db_manager.get_config(key)\n        \n        return jsonify({'configuration': config})\n        \n    except Exception as e:\n        logger.error(f\"Get configuration error: {e}\")\n        return jsonify({'error': str(e)}), 500\n\n@app.route('/api/config', methods=['PUT'])\n@jwt_required()\n@admin_required\ndef update_configuration():\n    \"\"\"Update system configuration\"\"\"\n    try:\n        current_user_email = get_jwt_identity()\n        user_info = db_manager.get_user_by_email(current_user_email)\n        user_id = user_info['id'] if user_info else None\n        \n        data = request.get_json()\n        if not data:\n            return jsonify({'error': 'Configuration data is required'}), 400\n        \n        # Update configuration values\n        updated_keys = []\n        for key, value in data.items():\n            try:\n                # Determine data type\n                if isinstance(value, bool):\n                    data_type = 'boolean'\n                elif isinstance(value, int):\n                    data_type = 'int'\n                elif isinstance(value, float):\n                    data_type = 'float'\n                elif isinstance(value, (dict, list)):\n                    data_type = 'json'\n                else:\n                    data_type = 'string'\n                \n                db_manager.set_config(key, value, data_type, user_id)\n                updated_keys.append(key)\n                \n            except Exception as e:\n                logger.error(f\"Error updating config key {key}: {e}\")\n        \n        return jsonify({\n            'message': f'Updated {len(updated_keys)} configuration keys',\n            'updated_keys': updated_keys\n        })\n        \n    except Exception as e:\n        logger.error(f\"Update configuration error: {e}\")\n        return jsonify({'error': str(e)}), 500\n\n# User Management (Admin)\n@app.route('/api/users', methods=['GET'])\n@jwt_required()\n@admin_required\ndef list_users():\n    \"\"\"List all users (admin only)\"\"\"\n    try:\n        # This would require implementing a list_users method in DatabaseManager\n        # For now, return a placeholder\n        return jsonify({\n            'message': 'User management endpoint - to be implemented',\n            'users': []\n        })\n        \n    except Exception as e:\n        logger.error(f\"List users error: {e}\")\n        return jsonify({'error': str(e)}), 500\n\n# Error handlers\n@app.errorhandler(404)\ndef not_found(error):\n    return jsonify({'error': 'Endpoint not found'}), 404\n\n@app.errorhandler(429)\ndef ratelimit_handler(e):\n    return jsonify({'error': 'Rate limit exceeded', 'retry_after': str(e.retry_after)}), 429\n\n@app.errorhandler(500)\ndef internal_error(error):\n    logger.error(f\"Internal server error: {error}\")\n    return jsonify({'error': 'Internal server error'}), 500\n\n# JWT error handlers\n@jwt.expired_token_loader\ndef expired_token_callback(jwt_header, jwt_payload):\n    return jsonify({'error': 'Token has expired'}), 401\n\n@jwt.invalid_token_loader\ndef invalid_token_callback(error):\n    return jsonify({'error': 'Invalid token'}), 401\n\n@jwt.unauthorized_loader\ndef missing_token_callback(error):\n    return jsonify({'error': 'Authorization token is required'}), 401\n\nif __name__ == '__main__':\n    port = int(os.environ.get('PORT', 5000))\n    debug = os.environ.get('FLASK_ENV') == 'development'\n    \n    logger.info(f\"Starting SAM Bot API on port {port}\")\n    app.run(host='0.0.0.0', port=port, debug=debug)"}}
