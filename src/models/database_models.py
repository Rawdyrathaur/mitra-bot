from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, create_engine, Boolean, Float, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import ARRAY, UUID
try:
    from sqlalchemy.dialects.postgresql import JSONB
except ImportError:
    from sqlalchemy import Text as JSONB  # Fallback for SQLite
from sqlalchemy.sql import func
from datetime import datetime
import os
import redis
import uuid

Base = declarative_base()

class User(Base):
    """User model for authentication and session management"""
    __tablename__ = 'users'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default='user')  # user, admin, moderator
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    conversations = relationship("Conversation", back_populates="user")
    uploaded_documents = relationship("Document", back_populates="uploaded_by_user")

class Document(Base):
    """Enhanced document model with version tracking and metadata"""
    __tablename__ = 'documents'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False, index=True)
    filename = Column(String(255), nullable=True)
    file_type = Column(String(50), nullable=False)  # pdf, docx, txt, html
    file_size = Column(Integer)  # in bytes
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)  # for deduplication
    category = Column(String(100), index=True)  # auto-categorized or manual
    language = Column(String(10), default='en')  # language code
    version = Column(Integer, default=1)
    parent_document_id = Column(String(36), ForeignKey('documents.id'), nullable=True)
    uploaded_by = Column(String(36), ForeignKey('users.id'), nullable=True)
    processing_status = Column(String(50), default='pending')  # pending, processing, completed, failed
    processing_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    uploaded_by_user = relationship("User", back_populates="uploaded_documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    versions = relationship("Document", remote_side=[id])  # self-referential for versions

class DocumentChunk(Base):
    """Document chunks with vector embeddings for semantic search"""
    __tablename__ = 'document_chunks'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey('documents.id'), nullable=False)
    chunk_index = Column(Integer, nullable=False)  # order within document
    content = Column(Text, nullable=False)
    embedding = Column(ARRAY(Float))  # PostgreSQL array for vector embedding
    token_count = Column(Integer)
    char_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
    
    # Index for similarity search
    __table_args__ = (Index('idx_document_chunk_order', document_id, chunk_index),)

class Conversation(Base):
    """Enhanced conversation model with context and analytics"""
    __tablename__ = 'conversations'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    context_chunks_used = Column(JSONB)  # JSON array of chunk IDs used
    confidence_score = Column(Float)  # AI confidence in the response
    response_time_ms = Column(Integer)  # response generation time
    feedback_rating = Column(Integer)  # 1-5 star rating from user
    feedback_comment = Column(Text)  # user feedback text
    requires_human_handoff = Column(Boolean, default=False)
    handoff_reason = Column(String(255))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="conversations")

class ConversationSession(Base):
    """Session management for multi-turn conversations"""
    __tablename__ = 'conversation_sessions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=True)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    last_activity = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # session expiration
    
    # Session metadata
    user_agent = Column(String(500))
    ip_address = Column(String(45))  # supports IPv6
    conversation_count = Column(Integer, default=0)

class Analytics(Base):
    """Analytics and metrics tracking"""
    __tablename__ = 'analytics'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(100), nullable=False, index=True)  # chat, upload, search, etc.
    user_id = Column(String(36), ForeignKey('users.id'), nullable=True)
    session_id = Column(String(255))
    event_metadata = Column(JSONB)  # flexible event data
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class SystemConfig(Base):
    """System configuration and feature flags"""
    __tablename__ = 'system_config'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    data_type = Column(String(20), default='string')  # string, int, float, boolean, json
    description = Column(Text)
    updated_by = Column(String(36), ForeignKey('users.id'))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WebhookConfig(Base):
    """Webhook configuration for integrations"""
    __tablename__ = 'webhook_configs'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    event_types = Column(ARRAY(String))  # list of events to trigger webhook
    is_active = Column(Boolean, default=True)
    secret_token = Column(String(255))  # for webhook verification
    headers = Column(JSONB)  # additional headers to send
    timeout_seconds = Column(Integer, default=30)
    retry_count = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ConversationMemory:
    def __init__(self, redis_url: str = None):
        """Initialize conversation memory with Redis for real-time conversation tracking"""
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.redis = redis.from_url(self.redis_url, decode_responses=True)
        self.expiration_seconds = int(os.getenv('SESSION_EXPIRATION', 86400))  # 24 hours default
        self.history_limit = int(os.getenv('HISTORY_LIMIT', 50))
    
    def store_conversation(self, session_id: str, question: str, answer: str, context: dict = None, metadata: dict = None):
        """Store conversation in Redis for fast access"""
        try:
            import json
            conversation_key = f"conversation:{session_id}"
            active_key = f"active_session:{session_id}"
            timestamp = datetime.utcnow().isoformat()
            
            # Create conversation item with enhanced metadata
            conversation_item = {
                'question': question,
                'answer': answer,
                'context_used': context or {},
                'timestamp': timestamp,
                'metadata': metadata or {},
            }
            
            # Record when each session was last active
            pipe = self.redis.pipeline()
            
            # Store conversation in list
            pipe.lpush(conversation_key, json.dumps(conversation_item))
            pipe.ltrim(conversation_key, 0, self.history_limit - 1)  # Keep limited history
            
            # Update session activity
            pipe.hset(active_key, mapping={
                'last_activity': timestamp,
                'question_count': int(self.redis.hget(active_key, 'question_count') or 0) + 1,
            })
            
            # Set expirations for both keys
            pipe.expire(conversation_key, self.expiration_seconds)
            pipe.expire(active_key, self.expiration_seconds)
            
            pipe.execute()
            
        except Exception as e:
            import logging
            logging.error(f"Error storing conversation in Redis: {e}")
    
    def get_conversation_history(self, session_id: str, limit: int = 10):
        """Get conversation history from Redis"""
        try:
            import json
            key = f"conversation:{session_id}"
            conversations = self.redis.lrange(key, 0, limit - 1)
            
            # Also refresh expiration
            if conversations:
                self.redis.expire(key, self.expiration_seconds)
                self.redis.expire(f"active_session:{session_id}", self.expiration_seconds)
                
            return [json.loads(conv) for conv in conversations]
            
        except Exception as e:
            import logging
            logging.error(f"Error retrieving conversation history: {e}")
            return []
    
    def get_conversation_context(self, session_id: str, context_window: int = 5):
        """Get recent conversation context for multi-turn dialogue"""
        try:
            history = self.get_conversation_history(session_id, context_window)
            context = []
            
            for conv in reversed(history):  # Process in chronological order
                context.append({"role": "user", "content": conv["question"]})
                context.append({"role": "assistant", "content": conv["answer"]})
                
            return context
        except Exception as e:
            import logging
            logging.error(f"Error getting conversation context: {e}")
            return []
    
    def clear_conversation(self, session_id: str):
        """Clear conversation history for a session"""
        try:
            self.redis.delete(f"conversation:{session_id}", f"active_session:{session_id}")
        except Exception as e:
            import logging
            logging.error(f"Error clearing conversation: {e}")
            
    def get_active_sessions(self, hours_ago: int = 24):
        """Get recently active sessions"""
        try:
            import time
            active_sessions = []
            current_time = time.time()
            cutoff_time = current_time - (hours_ago * 3600)  # Convert hours to seconds
            
            # Get all active session keys
            session_keys = self.redis.keys("active_session:*")
            
            for key in session_keys:
                session_id = key.split(':')[1]
                last_activity_str = self.redis.hget(key, 'last_activity')
                
                if last_activity_str:
                    # Parse ISO timestamp to epoch seconds
                    last_activity = datetime.fromisoformat(last_activity_str).timestamp()
                    
                    if last_activity >= cutoff_time:
                        question_count = int(self.redis.hget(key, 'question_count') or 0)
                        active_sessions.append({
                            'session_id': session_id,
                            'last_activity': last_activity_str,
                            'question_count': question_count
                        })
            
            return sorted(active_sessions, key=lambda x: x['last_activity'], reverse=True)
            
        except Exception as e:
            import logging
            logging.error(f"Error getting active sessions: {e}")
            return []

# Database session management
class DatabaseSession:
    def __init__(self, database_url: str = None):
        if not database_url:
            database_url = os.getenv('DATABASE_URL', 'sqlite:///sam_bot.db')
        
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create all tables
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self):
        """Get database session"""
        return self.SessionLocal()
    
    def close_session(self, session):
        """Close database session"""
        session.close()