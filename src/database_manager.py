"""
Advanced database manager for SAM Bot with PostgreSQL vector support
"""
import os
import logging
import hashlib
import json
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from contextlib import contextmanager

from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import numpy as np

from models.database_models import (
    Base, User, Document, DocumentChunk, Conversation, 
    ConversationSession, Analytics, SystemConfig, WebhookConfig,
    ConversationMemory
)

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Enhanced database manager with vector operations and analytics"""
    
    def __init__(self, database_url: str = None, redis_url: str = None):
        self.database_url = database_url or os.getenv(
            'DATABASE_URL', 
            'postgresql://sam_user:sam_password@localhost:5432/sam_db'
        )
        
        # Initialize SQLAlchemy
        self.engine = create_engine(
            self.database_url,
            echo=os.getenv('DB_ECHO', 'false').lower() == 'true',
            pool_size=int(os.getenv('DB_POOL_SIZE', '10')),
            max_overflow=int(os.getenv('DB_MAX_OVERFLOW', '20')),
        )
        
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Initialize conversation memory with Redis
        self.conversation_memory = ConversationMemory(redis_url)
        
        # Create tables
        self.init_database()
        
        logger.info(f"Database initialized with URL: {self.database_url}")
    
    def init_database(self):
        """Initialize database tables and extensions"""
        try:
            # Enable PostgreSQL vector extension if available
            with self.engine.connect() as conn:
                try:
                    # Try to create vector extension (requires pgvector)
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    conn.commit()
                    logger.info("Vector extension enabled")
                except Exception as e:
                    logger.warning(f"Vector extension not available: {e}")
            
            # Create all tables
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
            
            # Insert default configuration
            self._insert_default_config()
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    @contextmanager
    def get_session(self):
        """Get database session with automatic cleanup"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    # User Management
    def create_user(self, email: str, username: str, password_hash: str, role: str = 'user') -> str:
        """Create a new user"""
        try:
            with self.get_session() as session:
                user = User(
                    email=email,
                    username=username,
                    password_hash=password_hash,
                    role=role
                )
                session.add(user)
                session.flush()
                user_id = user.id
                
                # Log analytics
                self._log_analytics(session, 'user_created', user_id=user_id)
                
                logger.info(f"Created user: {username} ({user_id})")
                return user_id
        except SQLAlchemyError as e:
            logger.error(f"Error creating user: {e}")
            raise
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter(User.email == email).first()
                if user:
                    return {
                        'id': user.id,
                        'email': user.email,
                        'username': user.username,
                        'role': user.role,
                        'is_active': user.is_active,
                        'created_at': user.created_at
                    }
                return None
        except SQLAlchemyError as e:
            logger.error(f"Error getting user by email: {e}")
            return None
    
    def authenticate_user(self, email: str, password_hash: str) -> Optional[Dict]:
        """Authenticate user and update last login"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter(
                    User.email == email,
                    User.password_hash == password_hash,
                    User.is_active == True
                ).first()
                
                if user:
                    # Update last login
                    user.last_login = datetime.utcnow()
                    
                    # Log analytics
                    self._log_analytics(session, 'user_login', user_id=user.id)
                    
                    return {
                        'id': user.id,
                        'email': user.email,
                        'username': user.username,
                        'role': user.role,
                    }
                return None
        except SQLAlchemyError as e:
            logger.error(f"Error authenticating user: {e}")
            return None
    
    # Document Management
    def store_document(self, title: str, content: str, file_type: str, 
                      filename: str = None, uploaded_by: str = None, 
                      category: str = None) -> str:
        """Store document with metadata"""
        try:
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            
            with self.get_session() as session:
                # Check for duplicate content
                existing = session.query(Document).filter(
                    Document.content_hash == content_hash
                ).first()
                
                if existing:
                    logger.info(f"Document already exists: {existing.id}")
                    return existing.id
                
                document = Document(
                    title=title,
                    filename=filename,
                    file_type=file_type,
                    file_size=len(content.encode()),
                    content=content,
                    content_hash=content_hash,
                    uploaded_by=uploaded_by,
                    category=category,
                    processing_status='pending'
                )
                
                session.add(document)
                session.flush()
                doc_id = document.id
                
                # Log analytics
                self._log_analytics(session, 'document_uploaded', 
                                  user_id=uploaded_by, 
                                  metadata={'document_id': doc_id, 'file_type': file_type})
                
                logger.info(f"Stored document: {title} ({doc_id})")
                return doc_id
                
        except SQLAlchemyError as e:
            logger.error(f"Error storing document: {e}")
            raise
    
    def store_document_chunks(self, document_id: str, chunks: List[str], 
                            embeddings: List[List[float]]) -> List[str]:
        """Store document chunks with embeddings"""
        try:
            chunk_ids = []
            
            with self.get_session() as session:
                # Update document status
                document = session.query(Document).filter(Document.id == document_id).first()
                if document:
                    document.processing_status = 'processing'
                
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    chunk_record = DocumentChunk(
                        document_id=document_id,
                        chunk_index=i,
                        content=chunk,
                        embedding=embedding,
                        token_count=len(chunk.split()),
                        char_count=len(chunk)
                    )
                    session.add(chunk_record)
                    session.flush()
                    chunk_ids.append(chunk_record.id)
                
                # Update document status to completed
                if document:
                    document.processing_status = 'completed'
                
                logger.info(f"Stored {len(chunk_ids)} chunks for document {document_id}")
                return chunk_ids
                
        except SQLAlchemyError as e:
            logger.error(f"Error storing document chunks: {e}")
            # Update document status to failed
            with self.get_session() as session:
                document = session.query(Document).filter(Document.id == document_id).first()
                if document:
                    document.processing_status = 'failed'
                    document.processing_error = str(e)
            raise
    
    def semantic_search(self, query_embedding: List[float], limit: int = 5, 
                       similarity_threshold: float = 0.1) -> List[Dict]:
        """Perform semantic search using vector similarity"""
        try:
            with self.get_session() as session:
                # Use PostgreSQL vector operations if available
                try:
                    # This requires pgvector extension
                    sql = text("""
                        SELECT dc.id, dc.document_id, dc.content, d.title, d.category,
                               1 - (dc.embedding <=> :query_embedding) as similarity
                        FROM document_chunks dc
                        JOIN documents d ON dc.document_id = d.id
                        WHERE d.processing_status = 'completed'
                        ORDER BY dc.embedding <=> :query_embedding
                        LIMIT :limit
                    """)
                    
                    result = session.execute(sql, {
                        'query_embedding': query_embedding,
                        'limit': limit
                    })
                    
                except Exception as e:
                    # Fallback to Python-based similarity calculation
                    logger.warning(f"Vector search not available, using fallback: {e}")
                    return self._fallback_similarity_search(session, query_embedding, limit, similarity_threshold)
                
                results = []
                for row in result:
                    if row.similarity >= similarity_threshold:
                        results.append({
                            'chunk_id': row.id,
                            'document_id': row.document_id,
                            'content': row.content,
                            'document_title': row.title,
                            'category': row.category,
                            'similarity': float(row.similarity)
                        })
                
                logger.info(f"Found {len(results)} relevant chunks")
                return results
                
        except SQLAlchemyError as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    def _fallback_similarity_search(self, session: Session, query_embedding: List[float], 
                                  limit: int, threshold: float) -> List[Dict]:
        """Fallback similarity search using Python calculations"""
        try:
            # Get all chunks with embeddings
            chunks = session.query(DocumentChunk, Document).join(Document).filter(
                Document.processing_status == 'completed'
            ).all()
            
            if not chunks:
                return []
            
            query_array = np.array(query_embedding)
            similarities = []
            
            for chunk, document in chunks:
                if chunk.embedding:
                    chunk_array = np.array(chunk.embedding)
                    # Cosine similarity
                    similarity = np.dot(query_array, chunk_array) / (
                        np.linalg.norm(query_array) * np.linalg.norm(chunk_array)
                    )
                    
                    if similarity >= threshold:
                        similarities.append({
                            'chunk_id': chunk.id,
                            'document_id': chunk.document_id,
                            'content': chunk.content,
                            'document_title': document.title,
                            'category': document.category,
                            'similarity': float(similarity)
                        })
            
            # Sort by similarity and return top results
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            return similarities[:limit]
            
        except Exception as e:
            logger.error(f"Error in fallback similarity search: {e}")
            return []
    
    # Conversation Management
    def store_conversation(self, session_id: str, user_id: str, question: str, 
                          answer: str, context_chunks: List[str] = None, 
                          confidence_score: float = None, response_time_ms: int = None) -> str:
        """Store conversation with analytics"""
        try:
            with self.get_session() as session:
                conversation = Conversation(
                    session_id=session_id,
                    user_id=user_id,
                    question=question,
                    answer=answer,
                    context_chunks_used=context_chunks or [],
                    confidence_score=confidence_score,
                    response_time_ms=response_time_ms
                )
                
                session.add(conversation)
                session.flush()
                conv_id = conversation.id
                
                # Store in Redis for fast access
                self.conversation_memory.store_conversation(
                    session_id, question, answer, 
                    {'chunks': context_chunks or []},
                    {'confidence': confidence_score, 'response_time': response_time_ms}
                )
                
                # Log analytics
                self._log_analytics(session, 'conversation', 
                                  user_id=user_id, 
                                  session_id=session_id,
                                  metadata={
                                      'conversation_id': conv_id,
                                      'confidence_score': confidence_score,
                                      'response_time_ms': response_time_ms
                                  })
                
                return conv_id
                
        except SQLAlchemyError as e:
            logger.error(f"Error storing conversation: {e}")
            raise
    
    def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get conversation history for a user"""
        try:
            with self.get_session() as session:
                conversations = session.query(Conversation).filter(
                    Conversation.user_id == user_id
                ).order_by(Conversation.timestamp.desc()).limit(limit).all()
                
                return [{
                    'id': conv.id,
                    'session_id': conv.session_id,
                    'question': conv.question,
                    'answer': conv.answer,
                    'confidence_score': conv.confidence_score,
                    'timestamp': conv.timestamp.isoformat(),
                    'feedback_rating': conv.feedback_rating
                } for conv in conversations]
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting conversation history: {e}")
            return []
    
    def update_conversation_feedback(self, conversation_id: str, rating: int, comment: str = None):
        """Update conversation feedback"""
        try:
            with self.get_session() as session:
                conversation = session.query(Conversation).filter(
                    Conversation.id == conversation_id
                ).first()
                
                if conversation:
                    conversation.feedback_rating = rating
                    conversation.feedback_comment = comment
                    
                    # Log analytics
                    self._log_analytics(session, 'feedback_provided',
                                      user_id=conversation.user_id,
                                      metadata={
                                          'conversation_id': conversation_id,
                                          'rating': rating,
                                          'has_comment': bool(comment)
                                      })
                    
                    logger.info(f"Updated feedback for conversation {conversation_id}: {rating} stars")
                    
        except SQLAlchemyError as e:
            logger.error(f"Error updating conversation feedback: {e}")
            raise
    
    # Analytics
    def _log_analytics(self, session: Session, event_type: str, user_id: str = None, 
                      session_id: str = None, metadata: Dict = None):
        """Internal method to log analytics events"""
        try:
            analytics = Analytics(
                event_type=event_type,
                user_id=user_id,
                session_id=session_id,
                metadata=metadata or {}
            )
            session.add(analytics)
        except Exception as e:
            logger.error(f"Error logging analytics: {e}")
    
    def get_analytics_summary(self, days: int = 7) -> Dict:
        """Get analytics summary for the last N days"""
        try:
            with self.get_session() as session:
                since = datetime.utcnow() - timedelta(days=days)
                
                # Get event counts
                events = session.query(
                    Analytics.event_type,
                    func.count(Analytics.id).label('count')
                ).filter(
                    Analytics.timestamp >= since
                ).group_by(Analytics.event_type).all()
                
                # Get active users
                active_users = session.query(func.count(func.distinct(Analytics.user_id))).filter(
                    Analytics.timestamp >= since,
                    Analytics.user_id.isnot(None)
                ).scalar()
                
                # Get conversation metrics
                avg_confidence = session.query(func.avg(Conversation.confidence_score)).filter(
                    Conversation.timestamp >= since,
                    Conversation.confidence_score.isnot(None)
                ).scalar()
                
                avg_response_time = session.query(func.avg(Conversation.response_time_ms)).filter(
                    Conversation.timestamp >= since,
                    Conversation.response_time_ms.isnot(None)
                ).scalar()
                
                return {
                    'period_days': days,
                    'events': {event.event_type: event.count for event in events},
                    'active_users': active_users or 0,
                    'avg_confidence_score': float(avg_confidence) if avg_confidence else None,
                    'avg_response_time_ms': float(avg_response_time) if avg_response_time else None,
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting analytics summary: {e}")
            return {}
    
    # Configuration Management
    def _insert_default_config(self):
        """Insert default system configuration"""
        try:
            with self.get_session() as session:
                defaults = [
                    ('max_file_size', '10485760', 'int', 'Maximum file size for uploads in bytes'),
                    ('chunk_size', '1000', 'int', 'Document chunk size in characters'),
                    ('chunk_overlap', '200', 'int', 'Document chunk overlap in characters'),
                    ('similarity_threshold', '0.1', 'float', 'Minimum similarity threshold for search'),
                    ('conversation_context_window', '5', 'int', 'Number of recent conversations to include in context'),
                    ('enable_analytics', 'true', 'boolean', 'Enable analytics tracking'),
                    ('enable_feedback', 'true', 'boolean', 'Enable user feedback collection'),
                ]
                
                for key, value, data_type, description in defaults:
                    existing = session.query(SystemConfig).filter(SystemConfig.key == key).first()
                    if not existing:
                        config = SystemConfig(
                            key=key,
                            value=value,
                            data_type=data_type,
                            description=description
                        )
                        session.add(config)
                        
        except SQLAlchemyError as e:
            logger.error(f"Error inserting default config: {e}")
    
    def get_config(self, key: str, default=None):
        """Get configuration value"""
        try:
            with self.get_session() as session:
                config = session.query(SystemConfig).filter(SystemConfig.key == key).first()
                if config:
                    # Convert based on data type
                    if config.data_type == 'int':
                        return int(config.value)
                    elif config.data_type == 'float':
                        return float(config.value)
                    elif config.data_type == 'boolean':
                        return config.value.lower() in ('true', '1', 'yes')
                    elif config.data_type == 'json':
                        return json.loads(config.value)
                    else:
                        return config.value
                return default
        except (SQLAlchemyError, ValueError) as e:
            logger.error(f"Error getting config {key}: {e}")
            return default
    
    def set_config(self, key: str, value: Any, data_type: str = 'string', updated_by: str = None):
        """Set configuration value"""
        try:
            with self.get_session() as session:
                config = session.query(SystemConfig).filter(SystemConfig.key == key).first()
                
                # Convert value to string
                if data_type == 'json':
                    str_value = json.dumps(value)
                else:
                    str_value = str(value)
                
                if config:
                    config.value = str_value
                    config.data_type = data_type
                    config.updated_by = updated_by
                    config.updated_at = datetime.utcnow()
                else:
                    config = SystemConfig(
                        key=key,
                        value=str_value,
                        data_type=data_type,
                        updated_by=updated_by
                    )
                    session.add(config)
                    
        except SQLAlchemyError as e:
            logger.error(f"Error setting config {key}: {e}")
            raise
    
    # Health and Monitoring
    def health_check(self) -> Dict:
        """Perform database health check"""
        try:
            with self.get_session() as session:
                # Test basic connectivity
                session.execute(text("SELECT 1"))
                
                # Get basic stats
                user_count = session.query(func.count(User.id)).scalar()
                document_count = session.query(func.count(Document.id)).scalar()
                conversation_count = session.query(func.count(Conversation.id)).scalar()
                
                return {
                    'database': 'healthy',
                    'users': user_count,
                    'documents': document_count,
                    'conversations': conversation_count,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'database': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
