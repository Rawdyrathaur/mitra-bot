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
# CORS configuration - allow requests from Vercel frontend
allowed_origins = os.getenv('ALLOWED_ORIGINS', '*')
if allowed_origins == '*':
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
else:
    CORS(app, resources={r"/api/*": {"origins": allowed_origins.split(',')}}, supports_credentials=True)

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

# Helper function for async operations
def run_async(coro):
    """Run async coroutine in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# Helper function for async operations
def run_async(coro):
    """Run async coroutine in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


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
        # Note: If generate_response is async, we need to run it in an event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        response_data = run_async(conversation_engine.generate_response(message, session_id, user_id))

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
        )
        file.seek(0)  # Reset file pointer
        
        if not is_valid:
            return jsonify({'error': validation_message}), 400
        
        # Process upload
        result = run_async(doc_uploader.handle_file_upload(
            file,
            file.filename,
            title=title,
            uploaded_by=user_id,
            category=category
        ))
        
        if result['success']:
            return jsonify({
                'message': 'Document uploaded successfully',
                'document_id': result['document_id']
            }), 201
        else:
            return jsonify({'error': result['error']}), 500
        
    except Exception as e:
        logger.error(f\"Document upload error: {e}\")
        return jsonify({'error': 'Upload failed'}), 500

@app.route('/api/documents/text', methods=['POST'])
@jwt_required()
def upload_text_content():
    \"\"\"Upload raw text content\"\"\"
    try:
        current_user_email = get_jwt_identity()
        user_info = db_manager.get_user_by_email(current_user_email)
        user_id = user_info['id'] if user_info else None
        
        data = request.get_json()
        
        if not data or 'content' not in data:
            return jsonify({'error': 'Content is required'}), 400
        
        title = data.get('title', 'Untitled Document')
        content = data['content']
        category = data.get('category')
        
        if not content.strip():
            return jsonify({'error': 'Content cannot be empty'}), 400
        
        # Process content
        doc_id = run_async(doc_processor.process_text_content(
            title, content, uploaded_by=user_id, category=category
        )))
        
        return jsonify({
            'message': 'Text content processed successfully',
            'document_id': doc_id
        }), 201
        
    except Exception as e:
        logger.error(f\"Text upload error: {e}\")
        return jsonify({'error': 'Processing failed'}), 500

@app.route('/api/documents', methods=['GET'])
def list_documents():
    \"\"\"List documents with optional filtering\"\"\"
    try:
        category = request.args.get('category')
        status = request.args.get('status')
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        
        documents = doc_processor.list_documents(
            category=category,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return jsonify({
            'documents': documents,
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        logger.error(f\"List documents error: {e}\")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/<document_id>', methods=['GET'])
def get_document(document_id):
    \"\"\"Get detailed document information\"\"\"
    try:
        document_info = doc_processor.get_document_info(document_id)
        
        if 'error' in document_info:
            return jsonify(document_info), 404
        
        return jsonify({'document': document_info})
        
    except Exception as e:
        logger.error(f\"Get document error: {e}\")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/<document_id>', methods=['DELETE'])
@jwt_required()
def delete_document(document_id):
    \"\"\"Delete a document\"\"\"
    try:
        current_user_email = get_jwt_identity()
        user_info = db_manager.get_user_by_email(current_user_email)
        user_id = user_info['id'] if user_info else None
        
        success = doc_processor.delete_document(document_id, user_id)
        
        if success:
            return jsonify({'message': 'Document deleted successfully'})
        else:
            return jsonify({'error': 'Document not found'}), 404
        
    except Exception as e:
        logger.error(f\"Delete document error: {e}\")
        return jsonify({'error': str(e)}), 500

# Search Endpoints
@app.route('/api/search', methods=['GET', 'POST'])
@limiter.limit(\"30 per minute\")
def search_knowledge():
    \"\"\"Search the knowledge base\"\"\"
    try:
        if request.method == 'GET':
            query = request.args.get('q', '').strip()
            search_type = request.args.get('type', 'semantic')
            category = request.args.get('category')
            limit = int(request.args.get('limit', 10))
        else:
            data = request.get_json()
            query = data.get('query', '').strip()
            search_type = data.get('type', 'semantic')
            category = data.get('category')
            limit = int(data.get('limit', 10))
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        filters = {}
        if category:
            filters['category'] = category
        
        # Perform search
        if search_type == 'advanced':
            facets = ['category', 'document_type']
            results = run_async(knowledge_engine.advanced_search(query, 'all', filters, facets)
        else:
            results = run_async(knowledge_engine.semantic_search(query, filters, limit)
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f\"Search error: {e}\")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search/suggestions', methods=['GET'])
def search_suggestions():
    \"\"\"Get search suggestions for autocomplete\"\"\"
    try:
        partial_query = request.args.get('q', '').strip()
        limit = int(request.args.get('limit', 5))
        
        if len(partial_query) < 2:
            return jsonify({'suggestions': []})
        
        suggestions = knowledge_engine.get_search_suggestions(partial_query, limit)
        
        return jsonify({'suggestions': suggestions})
        
    except Exception as e:
        logger.error(f\"Search suggestions error: {e}\")
        return jsonify({'error': str(e)}), 500

# Conversation Management
@app.route('/api/conversations/<session_id>', methods=['GET'])
def get_conversation_history(session_id):
    \"\"\"Get conversation history for a session\"\"\"
    try:
        limit = int(request.args.get('limit', 10))
        
        history = db_manager.conversation_memory.get_conversation_history(session_id, limit)
        
        return jsonify({
            'session_id': session_id,
            'conversations': history,
            'total': len(history)
        })
        
    except Exception as e:
        logger.error(f\"Get conversation history error: {e}\")
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations/<session_id>/export', methods=['GET'])
def export_conversation(session_id):
    \"\"\"Export conversation history\"\"\"
    try:
        format_type = request.args.get('format', 'json').lower()
        
        if format_type not in ['json', 'txt']:
            return jsonify({'error': 'Supported formats: json, txt'}), 400
        
        exported_data = conversation_engine.export_conversation(session_id, format_type)
        
        if exported_data:
            return jsonify({
                'session_id': session_id,
                'format': format_type,
                'data': exported_data
            })
        else:
            return jsonify({'error': 'Export failed'}), 500
        
    except Exception as e:
        logger.error(f\"Export conversation error: {e}\")
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations/<session_id>', methods=['DELETE'])
def clear_conversation(session_id):
    \"\"\"Clear conversation history\"\"\"
    try:
        success = conversation_engine.clear_conversation(session_id)
        
        if success:
            return jsonify({'message': 'Conversation cleared successfully'})
        else:
            return jsonify({'error': 'Failed to clear conversation'}), 500
        
    except Exception as e:
        logger.error(f\"Clear conversation error: {e}\")
        return jsonify({'error': str(e)}), 500

# Analytics Endpoints (Admin only)
@app.route('/api/analytics/overview', methods=['GET'])
@jwt_required()
@admin_required
def analytics_overview():
    \"\"\"Get comprehensive analytics overview\"\"\"
    try:
        days = int(request.args.get('days', 7))
        
        # Get analytics from multiple sources
        conversation_analytics = conversation_engine.get_conversation_analytics(days)
        search_analytics = knowledge_engine.get_search_analytics(days)
        system_analytics = db_manager.get_analytics_summary(days)
        
        return jsonify({
            'period_days': days,
            'conversations': conversation_analytics,
            'search': search_analytics,
            'system': system_analytics,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f\"Analytics overview error: {e}\")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/conversations', methods=['GET'])
@jwt_required()
@admin_required
def conversation_analytics():
    \"\"\"Get detailed conversation analytics\"\"\"
    try:
        days = int(request.args.get('days', 7))
        analytics = conversation_engine.get_conversation_analytics(days)
        
        return jsonify(analytics)
        
    except Exception as e:
        logger.error(f\"Conversation analytics error: {e}\")
        return jsonify({'error': str(e)}), 500

# Knowledge Base Management (Admin)
@app.route('/api/knowledge/categories', methods=['GET'])
def get_categories():
    \"\"\"Get all document categories\"\"\"
    try:
        categories = knowledge_mgmt.get_categories()
        return jsonify({'categories': categories})
        
    except Exception as e:
        logger.error(f\"Get categories error: {e}\")
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/stats', methods=['GET'])
@jwt_required()
@admin_required
def knowledge_stats():
    \"\"\"Get knowledge base statistics\"\"\"
    try:
        stats = knowledge_mgmt.get_knowledge_stats()
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f\"Knowledge stats error: {e}\")
        return jsonify({'error': str(e)}), 500

# Configuration Management (Admin)
@app.route('/api/config', methods=['GET'])
@jwt_required()
@admin_required
def get_configuration():
    \"\"\"Get system configuration\"\"\"
    try:
        # Get all configuration keys (this would be a proper admin interface)
        config_keys = [
            'max_file_size', 'chunk_size', 'chunk_overlap', 'similarity_threshold',
            'conversation_context_window', 'enable_analytics', 'enable_feedback'
        ]
        
        config = {}
        for key in config_keys:
            config[key] = db_manager.get_config(key)
        
        return jsonify({'configuration': config})
        
    except Exception as e:
        logger.error(f\"Get configuration error: {e}\")
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['PUT'])
@jwt_required()
@admin_required
def update_configuration():
    \"\"\"Update system configuration\"\"\"
    try:
        current_user_email = get_jwt_identity()
        user_info = db_manager.get_user_by_email(current_user_email)
        user_id = user_info['id'] if user_info else None
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Configuration data is required'}), 400
        
        # Update configuration values
        updated_keys = []
        for key, value in data.items():
            try:
                # Determine data type
                if isinstance(value, bool):
                    data_type = 'boolean'
                elif isinstance(value, int):
                    data_type = 'int'
                elif isinstance(value, float):
                    data_type = 'float'
                elif isinstance(value, (dict, list)):
                    data_type = 'json'
                else:
                    data_type = 'string'
                
                db_manager.set_config(key, value, data_type, user_id)
                updated_keys.append(key)
                
            except Exception as e:
                logger.error(f\"Error updating config key {key}: {e}\")
        
        return jsonify({
            'message': f'Updated {len(updated_keys)} configuration keys',
            'updated_keys': updated_keys
        })
        
    except Exception as e:
        logger.error(f\"Update configuration error: {e}\")
        return jsonify({'error': str(e)}), 500

# User Management (Admin)
@app.route('/api/users', methods=['GET'])
@jwt_required()
@admin_required
def list_users():
    \"\"\"List all users (admin only)\"\"\"
    try:
        # This would require implementing a list_users method in DatabaseManager
        # For now, return a placeholder
        return jsonify({
            'message': 'User management endpoint - to be implemented',
            'users': []
        })
        
    except Exception as e:
        logger.error(f\"List users error: {e}\")
        return jsonify({'error': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Rate limit exceeded', 'retry_after': str(e.retry_after)}), 429

@app.errorhandler(500)
def internal_error(error):
    logger.error(f\"Internal server error: {error}\")
    return jsonify({'error': 'Internal server error'}), 500

# JWT error handlers
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({'error': 'Token has expired'}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({'error': 'Invalid token'}), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({'error': 'Authorization token is required'}), 401

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f\"Starting SAM Bot API on port {port}\")
    app.run(host='0.0.0.0', port=port, debug=debug)"}}
