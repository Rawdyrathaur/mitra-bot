#!/usr/bin/env python3
"""
Simple Flask API for SAM Bot - Running Version
"""
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import logging
import os
import json
import uuid
from datetime import datetime
import sqlite3
from typing import Optional, List, Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='../templates')
CORS(app)

# Simple database manager using SQLite
class SimpleDatabase:
    def __init__(self, db_path: str = "sam_bot.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create messages table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT,
                        session_id TEXT,
                        message TEXT NOT NULL,
                        message_type TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create documents table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS documents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        content TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def store_message(self, user_id: str, session_id: str, message: str, message_type: str) -> int:
        """Store a message in the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages (user_id, session_id, message, message_type) VALUES (?, ?, ?, ?)",
                    (user_id, session_id, message, message_type)
                )
                conn.commit()
                return cursor.lastrowid
                
        except Exception as e:
            logger.error(f"Error storing message: {e}")
            return None
    
    def get_conversation_history(self, session_id: str, limit: int = 5) -> List[Dict]:
        """Get conversation history for a session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT message, message_type, timestamp 
                    FROM messages 
                    WHERE session_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (session_id, limit * 2))  # Get both user and bot messages
                
                results = cursor.fetchall()
                return [
                    {
                        'message': row[0],
                        'type': row[1],
                        'timestamp': row[2]
                    }
                    for row in results
                ]
                
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []
    
    def store_document(self, title: str, content: str) -> int:
        """Store a document in the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO documents (title, content) VALUES (?, ?)",
                    (title, content)
                )
                conn.commit()
                return cursor.lastrowid
                
        except Exception as e:
            logger.error(f"Error storing document: {e}")
            return None
    
    def extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from a query"""
        import re
        # Remove common stop words and extract meaningful terms
        stop_words = {'what', 'is', 'are', 'how', 'why', 'when', 'where', 'who', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        
        # Extract words (remove punctuation)
        words = re.findall(r'\w+', query.lower())
        
        # Filter out stop words and short words
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        # If no keywords found, use original query
        if not keywords:
            keywords = [query.lower()]
            
        return keywords

    def search_documents(self, query: str, limit: int = 3) -> List[Dict]:
        """Enhanced text search in documents with keyword extraction"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Extract keywords from query
                keywords = self.extract_keywords(query)
                logger.info(f"Searching for: '{query}' with keywords: {keywords}")
                
                # Search for documents containing any of the keywords
                results = []
                for keyword in keywords:
                    search_term = f"%{keyword}%"
                    cursor.execute('''
                        SELECT id, title, content, timestamp 
                        FROM documents 
                        WHERE LOWER(content) LIKE ? OR LOWER(title) LIKE ?
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    ''', (search_term, search_term, limit))
                    
                    keyword_results = cursor.fetchall()
                    for result in keyword_results:
                        if result not in results:  # Avoid duplicates
                            results.append(result)
                
                logger.info(f"Found {len(results)} documents matching keywords from '{query}'")
                return [
                    {
                        'id': row[0],
                        'title': row[1],
                        'content': row[2][:300] + "..." if len(row[2]) > 300 else row[2],
                        'timestamp': row[3]
                    }
                    for row in results[:limit]  # Limit final results
                ]
                
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []
    
    def get_all_documents(self) -> List[Dict]:
        """Get all documents"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, title, content, timestamp 
                    FROM documents 
                    ORDER BY timestamp DESC
                ''')
                
                results = cursor.fetchall()
                return [
                    {
                        'id': row[0],
                        'title': row[1],
                        'content': row[2][:200] + "..." if len(row[2]) > 200 else row[2],
                        'timestamp': row[3]
                    }
                    for row in results
                ]
                
        except Exception as e:
            logger.error(f"Error getting documents: {e}")
            return []

# Simple chat model
class SimpleChatModel:
    def __init__(self):
        """Initialize the simple chat model"""
        self.responses = {
            "greeting": [
                "Hello! How can I help you today?",
                "Hi there! What can I do for you?",
                "Hello! I'm SAM, your assistant. How may I assist you?"
            ],
            "farewell": [
                "Goodbye! Have a great day!",
                "See you later!",
                "Take care!"
            ],
            "default": [
                "That's interesting! Can you tell me more?",
                "I understand. What would you like to know?",
                "Thanks for sharing that with me.",
                "I'm here to help. What else can I do for you?",
                "That's a good question. Let me think about that."
            ],
            "help": [
                "I'm SAM, your AI assistant. I can chat with you and help answer questions!",
                "I'm here to help! You can ask me questions or just have a conversation.",
                "I'm SAM Bot! I can assist you with various topics and have conversations."
            ]
        }
        logger.info("Simple chat model initialized")
    
    def classify_intent(self, message: str) -> str:
        """Classify the intent of a message"""
        message_lower = message.lower()
        
        greetings = ["hello", "hi", "hey", "good morning", "good afternoon"]
        farewells = ["bye", "goodbye", "see you", "farewell"]
        help_keywords = ["help", "what can you do", "who are you", "what are you"]
        
        if any(greeting in message_lower for greeting in greetings):
            return "greeting"
        elif any(farewell in message_lower for farewell in farewells):
            return "farewell"
        elif any(help_word in message_lower for help_word in help_keywords):
            return "help"
        else:
            return "default"
    
    def generate_response(self, message: str, context: Optional[List] = None) -> str:
        """Generate a response to the user message"""
        try:
            intent = self.classify_intent(message)
            
            # If we have relevant context from documents, use it
            if context and len(context) > 0:
                context_info = context[0]['content'][:200]  # First 200 chars of most relevant document
                return f"Based on the available information: {context_info}... Would you like me to elaborate on this topic?"
            
            # Fallback to intent-based responses
            if intent in self.responses:
                import random
                response = random.choice(self.responses[intent])
            else:
                import random
                response = random.choice(self.responses["default"])
            
            logger.info(f"Generated response for intent: {intent}")
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I'm sorry, I'm having trouble processing that right now."

# Initialize components
db = SimpleDatabase()
chat_model = SimpleChatModel()

@app.route('/')
def index():
    """Serve the web interface"""
    try:
        return render_template('index.html')
    except Exception as e:
        return f"""
        <html>
        <head><title>SAM Bot</title></head>
        <body>
            <h1>SAM Bot is Running!</h1>
            <p>The web interface template is not available, but the API is working.</p>
            <h2>Available Endpoints:</h2>
            <ul>
                <li>GET /api/health - Health check</li>
                <li>POST /api/chat - Chat with the bot</li>
                <li>POST /api/upload - Upload documents</li>
                <li>GET /api/knowledge - Get all documents</li>
            </ul>
            <h2>Test the API:</h2>
            <pre>
curl -X POST http://localhost:5000/api/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"message": "Hello!", "user_id": "test-user"}}'
            </pre>
        </body>
        </html>
        """

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "SAM is running",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected",
        "version": "simple"
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint with simple RAG capabilities"""
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({"error": "Message is required"}), 400
        
        message = data['message']
        user_id = data.get('user_id', 'anonymous')
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        logger.info(f"Chat request from user {user_id}, session {session_id}: {message}")
        
        # Store user message
        db.store_message(user_id, session_id, message, "user")
        
        # Get conversation history for context
        history = db.get_conversation_history(session_id, limit=3)
        
        # Search for relevant documents
        relevant_docs = db.search_documents(message, limit=2)
        
        # Generate response using context
        response = chat_model.generate_response(message, relevant_docs)
        
        # Store bot response
        db.store_message(user_id, session_id, response, "bot")
        
        return jsonify({
            "response": response,
            "user_id": user_id,
            "session_id": session_id,
            "context_used": len(relevant_docs) > 0,
            "knowledge_sources": len(relevant_docs),
            "conversation_history": len(history)
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/upload', methods=['POST'])
def upload_document():
    """Enhanced document upload endpoint supporting both files and JSON"""
    try:
        # Handle file upload (multipart/form-data)
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            
            # Read file content based on file type
            try:
                filename = file.filename.lower() if file.filename else ''
                title = file.filename or 'Untitled Document'
                logger.info(f"Processing uploaded file: {title}")
                
                if filename.endswith('.docx'):
                    # Process Word document
                    import docx2txt
                    import tempfile
                    import os
                    
                    # Save file temporarily
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp_file:
                        file.save(tmp_file.name)
                        content = docx2txt.process(tmp_file.name)
                        os.unlink(tmp_file.name)  # Clean up temp file
                    
                    if not content or len(content.strip()) < 10:
                        return jsonify({"error": "Could not extract text from Word document or content too short"}), 400
                        
                elif filename.endswith(('.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.csv')):
                    # Process text-based files
                    content = file.read().decode('utf-8')
                else:
                    # Try to read as UTF-8 text
                    try:
                        content = file.read().decode('utf-8')
                    except UnicodeDecodeError:
                        return jsonify({"error": "File must be text-based (UTF-8 encoding) or Word document (.docx)"}), 400
                        
            except ImportError:
                return jsonify({"error": "Word document processing not available. Please install docx2txt."}), 400
            except Exception as e:
                return jsonify({"error": f"Error reading file: {str(e)}"}), 400
        
        # Handle JSON content upload
        elif request.is_json:
            data = request.get_json()
            
            if not data or 'content' not in data:
                return jsonify({"error": "Content is required"}), 400
            
            content = data['content']
            title = data.get('title', 'Untitled Document')
            logger.info(f"Processing JSON content: {title}")
        
        else:
            return jsonify({"error": "No file or JSON content provided"}), 400
        
        # Validate content
        if not content or len(content.strip()) < 10:
            return jsonify({"error": "Content must be at least 10 characters long"}), 400
        
        # Store the document
        doc_id = db.store_document(title, content)
        
        if doc_id:
            logger.info(f"Document stored: {title} (ID: {doc_id})")
            return jsonify({
                "message": "Document uploaded successfully",
                "document_id": doc_id,
                "title": title,
                "content_length": len(content)
            })
        else:
            return jsonify({"error": "Failed to store document"}), 500
        
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/knowledge', methods=['GET'])
def get_knowledge():
    """Get all knowledge base documents"""
    try:
        documents = db.get_all_documents()
        return jsonify({
            "documents": documents,
            "total": len(documents)
        })
        
    except Exception as e:
        logger.error(f"Error getting knowledge: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/conversations/<user_id>', methods=['GET'])
def get_conversations(user_id):
    """Get conversation history for a user"""
    try:
        session_id = request.args.get('session_id')
        limit = request.args.get('limit', 10, type=int)
        
        if session_id:
            history = db.get_conversation_history(session_id, limit)
            return jsonify({
                "user_id": user_id,
                "session_id": session_id,
                "conversations": history,
                "total": len(history)
            })
        else:
            return jsonify({
                "user_id": user_id,
                "conversations": [],
                "total": 0,
                "message": "session_id parameter required"
            })
        
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/sessions/<session_id>/clear', methods=['DELETE'])
def clear_session(session_id):
    """Clear conversation history for a session"""
    try:
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            deleted_count = cursor.rowcount
            conn.commit()
        
        logger.info(f"Cleared {deleted_count} messages from session {session_id}")
        return jsonify({
            "message": f"Session {session_id} cleared successfully",
            "deleted_messages": deleted_count
        })
        
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    
    logger.info(f"Starting SAM Bot API on port {port}")
    logger.info(f"Debug mode: {debug}")
    logger.info("Available endpoints:")
    logger.info("  GET    /                              - Web interface")
    logger.info("  GET    /api/health                    - Health check")
    logger.info("  POST   /api/chat                      - Chat with bot")
    logger.info("  POST   /api/upload                    - Upload document (file or JSON)")
    logger.info("  GET    /api/knowledge                 - Get documents")
    logger.info("  GET    /api/conversations/<user_id>   - Get conversation history")
    logger.info("  DELETE /api/sessions/<session_id>/clear - Clear session")
    
    app.run(host='0.0.0.0', port=port, debug=debug)