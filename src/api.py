#!/usr/bin/env python3
"""
Flask API for SAM Bot with RAG capabilities
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import os
from database import DatabaseManager
from embeddings import EmbeddingProcessor
from models.chat_model import ChatModel
from rag_processor import RAGProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialize components
db = DatabaseManager()
embeddings = EmbeddingProcessor()
chat_model = ChatModel()
rag_processor = RAGProcessor(db, embeddings)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "SAM is running"})

@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint with RAG capabilities"""
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({"error": "Message is required"}), 400
        
        message = data['message']
        user_id = data.get('user_id', 'anonymous')
        
        logger.info(f"Processing message from user {user_id}: {message}")
        
        # Store user message
        message_id = db.store_message(user_id, message, "user")
        
        # Generate embedding for the message
        message_embedding = embeddings.get_embedding(message)
        
        # Store embedding
        embedding_data = embeddings.serialize_embedding(message_embedding)
        db.store_embedding(message_id, embedding_data)
        
        # Use RAG to find relevant context
        context = rag_processor.get_relevant_context(message, message_embedding)
        
        # Generate response using chat model with context
        response = chat_model.generate_response(message, context)
        
        # Store bot response
        response_id = db.store_message(user_id, response, "bot")
        response_embedding = embeddings.get_embedding(response)
        response_embedding_data = embeddings.serialize_embedding(response_embedding)
        db.store_embedding(response_id, response_embedding_data)
        
        return jsonify({
            "response": response,
            "user_id": user_id,
            "context_used": len(context) > 0
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/upload-knowledge', methods=['POST'])
def upload_knowledge():
    """Upload knowledge base documents"""
    try:
        data = request.get_json()
        
        if not data or 'content' not in data:
            return jsonify({"error": "Content is required"}), 400
        
        content = data['content']
        title = data.get('title', 'Untitled Document')
        
        # Process and store the knowledge
        doc_id = rag_processor.add_knowledge(title, content)
        
        return jsonify({
            "message": "Knowledge added successfully",
            "document_id": doc_id
        })
        
    except Exception as e:
        logger.error(f"Error uploading knowledge: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/knowledge', methods=['GET'])
def get_knowledge():
    """Get all knowledge base documents"""
    try:
        documents = rag_processor.get_all_knowledge()
        return jsonify({"documents": documents})
        
    except Exception as e:
        logger.error(f"Error getting knowledge: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/conversations/<user_id>', methods=['GET'])
def get_conversations(user_id):
    """Get conversation history for a user"""
    try:
        limit = request.args.get('limit', 10, type=int)
        history = db.get_conversation_history(user_id, limit)
        
        return jsonify({
            "user_id": user_id,
            "conversations": history
        })
        
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)