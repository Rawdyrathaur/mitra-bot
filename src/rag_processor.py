"""
RAG (Retrieval-Augmented Generation) processor for SAM Bot
"""
import logging
import sqlite3
from typing import List, Dict, Optional, Tuple
from embeddings import EmbeddingProcessor

logger = logging.getLogger(__name__)

class RAGProcessor:
    def __init__(self, database_manager, embedding_processor: EmbeddingProcessor):
        self.db = database_manager
        self.embeddings = embedding_processor
        self.init_knowledge_base()
        
    def init_knowledge_base(self):
        """Initialize knowledge base tables"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                
                # Create knowledge base table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS knowledge_base (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        chunk_id INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create knowledge embeddings table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS knowledge_embeddings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        knowledge_id INTEGER,
                        embedding BLOB,
                        FOREIGN KEY (knowledge_id) REFERENCES knowledge_base (id)
                    )
                ''')
                
                conn.commit()
                logger.info("Knowledge base tables initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing knowledge base: {e}")
            raise
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk.strip())
                
        return chunks
    
    def add_knowledge(self, title: str, content: str) -> int:
        """Add knowledge to the knowledge base"""
        try:
            # Split content into chunks for better retrieval
            chunks = self.chunk_text(content)
            
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                
                for i, chunk in enumerate(chunks):
                    # Store knowledge chunk
                    cursor.execute(
                        "INSERT INTO knowledge_base (title, content, chunk_id) VALUES (?, ?, ?)",
                        (title, chunk, i)
                    )
                    knowledge_id = cursor.lastrowid
                    
                    # Generate and store embedding
                    embedding = self.embeddings.get_embedding(chunk)
                    embedding_data = self.embeddings.serialize_embedding(embedding)
                    
                    cursor.execute(
                        "INSERT INTO knowledge_embeddings (knowledge_id, embedding) VALUES (?, ?)",
                        (knowledge_id, embedding_data)
                    )
                
                conn.commit()
                logger.info(f"Added knowledge: {title} ({len(chunks)} chunks)")
                return knowledge_id
                
        except Exception as e:
            logger.error(f"Error adding knowledge: {e}")
            raise
    
    def get_relevant_context(self, query: str, query_embedding: List[float], top_k: int = 3) -> List[str]:
        """Retrieve relevant context for a query using similarity search"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all knowledge embeddings
                cursor.execute('''
                    SELECT kb.content, ke.embedding, kb.title
                    FROM knowledge_base kb
                    JOIN knowledge_embeddings ke ON kb.id = ke.knowledge_id
                ''')
                
                results = cursor.fetchall()
                
                if not results:
                    return []
                
                # Calculate similarities and rank
                similarities = []
                for content, embedding_data, title in results:
                    stored_embedding = self.embeddings.deserialize_embedding(embedding_data)
                    if stored_embedding:
                        similarity = self.embeddings.similarity(query_embedding, stored_embedding)
                        similarities.append((similarity, content, title))
                
                # Sort by similarity and return top-k
                similarities.sort(reverse=True, key=lambda x: x[0])
                
                context = []
                for sim, content, title in similarities[:top_k]:
                    if sim > 0.1:  # Minimum similarity threshold
                        context.append(f"[{title}]: {content}")
                
                logger.info(f"Retrieved {len(context)} relevant contexts for query")
                return context
                
        except Exception as e:
            logger.error(f"Error retrieving relevant context: {e}")
            return []
    
    def get_all_knowledge(self) -> List[Dict]:
        """Get all documents in the knowledge base"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT DISTINCT title, MIN(id) as first_id, COUNT(*) as chunks, MIN(created_at) as created_at
                    FROM knowledge_base
                    GROUP BY title
                    ORDER BY created_at DESC
                ''')
                
                results = cursor.fetchall()
                
                documents = []
                for title, doc_id, chunk_count, created_at in results:
                    documents.append({
                        'id': doc_id,
                        'title': title,
                        'chunks': chunk_count,
                        'created_at': created_at
                    })
                
                return documents
                
        except Exception as e:
            logger.error(f"Error getting all knowledge: {e}")
            return []
    
    def search_knowledge(self, query: str, limit: int = 5) -> List[Dict]:
        """Search knowledge base by text similarity"""
        try:
            query_embedding = self.embeddings.get_embedding(query)
            relevant_contexts = self.get_relevant_context(query, query_embedding, limit)
            
            search_results = []
            for i, context in enumerate(relevant_contexts):
                search_results.append({
                    'rank': i + 1,
                    'content': context,
                    'relevance': 'high' if i < 2 else 'medium'
                })
            
            return search_results
            
        except Exception as e:
            logger.error(f"Error searching knowledge: {e}")
            return []