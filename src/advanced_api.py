#!/usr/bin/env python3
"""
Advanced Flask API for SAM Bot with PostgreSQL, Redis, and OpenAI
"""
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import logging
import os
import json
import uuid
from datetime import datetime
from typing import Optional

# Import our modules
from models.database_models import DatabaseSession, Document, Conversation, ConversationMemory
from models.chat_model import ChatModel
from document_processor import DocumentProcessor
from sqlalchemy.orm import sessionmaker
from sqlalchemy import desc

# Environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='../templates')
CORS(app)

# Initialize components
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///sam_bot.db')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

try:
    db_session = DatabaseSession(DATABASE_URL)
    logger.info(f"Database connected: {DATABASE_URL}")
except Exception as e:
    logger.error(f"Database connection failed: {e}")
    db_session = None

try:
    conversation_memory = ConversationMemory(REDIS_URL)
    logger.info("Redis conversation memory initialized")
except Exception as e:
    logger.error(f"Redis connection failed: {e}")
    conversation_memory = None

chat_model = ChatModel()
doc_processor = DocumentProcessor()

@app.route('/')
def index():
    """Serve the web interface"""
    return render_template('index.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    """Enhanced health check endpoint"""
    health_status = {
        "status": "SAM is running",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected" if db_session else "disconnected",
        "redis": "connected" if conversation_memory else "disconnected",
        "openai": "enabled" if chat_model.openai_api_key else "disabled",
        "embedding_model": doc_processor.get_embedding_model_info()
    }
    return jsonify(health_status)

@app.route('/api/chat', methods=['POST'])
def chat():
    """Enhanced chat endpoint with conversation memory and OpenAI"""
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({"error": "Message is required"}), 400
        
        message = data['message']
        user_id = data.get('user_id', 'anonymous')
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        logger.info(f"Chat request from user {user_id}, session {session_id}: {message}")
        
        # Get conversation history for context
        conversation_context = []
        if conversation_memory:
            history = conversation_memory.get_conversation_history(session_id, limit=3)
            conversation_context = [f"User: {h['question']}\nBot: {h['answer']}" for h in history]
        
        # Find relevant knowledge from documents
        knowledge_context = []
        if db_session:
            session = db_session.get_session()
            try:
                # Generate embedding for the question
                question_chunks, question_embeddings = doc_processor.process_text_content("", message)
                if question_embeddings:
                    query_embedding = question_embeddings[0]
                    
                    # Search for similar documents
                    documents = session.query(Document).all()
                    if documents:
                        doc_similarities = []
                        for doc in documents:
                            if doc.embedding:
                                doc_embedding = json.loads(doc.embedding)
                                similarity_indices = doc_processor.similarity_search(
                                    query_embedding, [doc_embedding], top_k=1
                                )
                                if similarity_indices:
                                    doc_similarities.append((doc, similarity_indices[0]))
                        
                        # Get top 3 most relevant documents
                        doc_similarities.sort(key=lambda x: x[1], reverse=True)
                        for doc, _ in doc_similarities[:3]:
                            knowledge_context.append(doc.content[:500])  # First 500 chars
                            
            except Exception as e:
                logger.error(f"Error searching knowledge base: {e}")
            finally:
                db_session.close_session(session)
        
        # Combine all context
        all_context = conversation_context + knowledge_context
        
        # Generate response
        response = chat_model.generate_response(message, all_context)
        
        # Store conversation in database
        if db_session:
            session = db_session.get_session()
            try:
                conversation = Conversation(
                    session_id=session_id,
                    user_id=user_id,
                    question=message,
                    answer=response,
                    context_used=json.dumps(all_context[:3]) if all_context else None
                )
                session.add(conversation)
                session.commit()
            except Exception as e:
                logger.error(f"Error storing conversation in database: {e}")
                session.rollback()
            finally:
                db_session.close_session(session)
        
        # Store in Redis for fast access
        if conversation_memory:
            conversation_memory.store_conversation(
                session_id, message, response, json.dumps(all_context[:2])
            )
        
        return jsonify({
            "response": response,
            "user_id": user_id,
            "session_id": session_id,
            "context_used": len(all_context) > 0,
            "knowledge_sources": len(knowledge_context),
            "conversation_history": len(conversation_context)
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/upload', methods=['POST'])
def upload_document():
    """Enhanced document upload endpoint"""
    try:
        # Handle file upload
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            
            # Save uploaded file
            os.makedirs('uploads', exist_ok=True)
            file_path = os.path.join('uploads', file.filename)
            file.save(file_path)
            
            try:
                # Process the document
                chunks, embeddings = doc_processor.process_document(file_path)
                title = file.filename
                content = " ".join(chunks)
                
                # Store in database
                if db_session:
                    session = db_session.get_session()
                    try:
                        # Store document with average embedding
                        avg_embedding = [sum(col) / len(embeddings) for col in zip(*embeddings)] if embeddings else []
                        
                        document = Document(
                            title=title,
                            content=content,
                            embedding=json.dumps(avg_embedding)
                        )
                        session.add(document)
                        session.commit()
                        
                        doc_id = document.id
                        logger.info(f"Document uploaded and processed: {title} (ID: {doc_id})")
                        
                        return jsonify({
                            "message": "Document uploaded and processed successfully",
                            "document_id": doc_id,
                            "title": title,
                            "chunks_generated": len(chunks)
                        })
                        
                    except Exception as e:
                        session.rollback()
                        raise
                    finally:
                        db_session.close_session(session)
                        
            finally:
                # Clean up uploaded file
                if os.path.exists(file_path):
                    os.remove(file_path)
        
        # Handle JSON content upload
        elif request.is_json:
            data = request.get_json()
            
            if not data or 'content' not in data:
                return jsonify({"error": "Content is required"}), 400
            
            content = data['content']
            title = data.get('title', 'Untitled Document')
            
            # Process the content
            chunks, embeddings = doc_processor.process_text_content(title, content)
            
            # Store in database
            if db_session:
                session = db_session.get_session()
                try:
                    # Store document with average embedding
                    avg_embedding = [sum(col) / len(embeddings) for col in zip(*embeddings)] if embeddings else []
                    
                    document = Document(
                        title=title,
                        content=" ".join(chunks),
                        embedding=json.dumps(avg_embedding)
                    )
                    session.add(document)
                    session.commit()
                    
                    doc_id = document.id
                    logger.info(f"Knowledge uploaded: {title} (ID: {doc_id})")
                    
                    return jsonify({
                        "message": "Knowledge added successfully",
                        "document_id": doc_id,
                        "title": title,
                        "chunks_generated": len(chunks)
                    })
                    
                except Exception as e:
                    session.rollback()
                    raise
                finally:
                    db_session.close_session(session)
        
        else:
            return jsonify({"error": "No file or content provided"}), 400
            
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/knowledge', methods=['GET'])
def get_knowledge():
    """Get all knowledge base documents"""
    try:
        if not db_session:
            return jsonify({"error": "Database not available"}), 500
            
        session = db_session.get_session()
        try:
            documents = session.query(Document).order_by(desc(Document.created_at)).all()
            
            doc_list = []
            for doc in documents:
                doc_list.append({
                    "id": doc.id,
                    "title": doc.title,
                    "content": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "updated_at": doc.updated_at.isoformat() if doc.updated_at else None
                })
            
            return jsonify({
                "documents": doc_list,
                "total": len(doc_list)
            })
            
        finally:
            db_session.close_session(session)
        
    except Exception as e:
        logger.error(f"Error getting knowledge: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/conversations/<user_id>', methods=['GET'])
def get_conversations(user_id):
    """Get conversation history for a user"""
    try:
        limit = request.args.get('limit', 10, type=int)
        session_id = request.args.get('session_id')
        
        # Try Redis first for recent conversations
        if conversation_memory and session_id:
            redis_history = conversation_memory.get_conversation_history(session_id, limit)
            if redis_history:
                return jsonify({
                    "user_id": user_id,
                    "session_id": session_id,
                    "conversations": redis_history,
                    "source": "redis"
                })
        
        # Fallback to database
        if db_session:
            session = db_session.get_session()
            try:
                query = session.query(Conversation).filter(Conversation.user_id == user_id)
                
                if session_id:
                    query = query.filter(Conversation.session_id == session_id)
                
                conversations = query.order_by(desc(Conversation.timestamp)).limit(limit).all()
                
                conv_list = []
                for conv in conversations:
                    conv_list.append({
                        "question": conv.question,
                        "answer": conv.answer,
                        "timestamp": conv.timestamp.isoformat(),
                        "session_id": conv.session_id,
                        "context_used": json.loads(conv.context_used) if conv.context_used else None
                    })
                
                return jsonify({
                    "user_id": user_id,
                    "conversations": conv_list,
                    "total": len(conv_list),
                    "source": "database"
                })
                
            finally:
                db_session.close_session(session)
        
        return jsonify({"error": "No conversation storage available"}), 500
        
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/sessions/<session_id>/clear', methods=['DELETE'])
def clear_session(session_id):
    """Clear conversation history for a session"""
    try:
        if conversation_memory:
            conversation_memory.clear_conversation(session_id)
        
        return jsonify({"message": f"Session {session_id} cleared successfully"})
        
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)