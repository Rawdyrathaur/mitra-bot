"""
Database management for SAM Bot
"""
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class DatabaseManager:
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
                        message TEXT NOT NULL,
                        message_type TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create embeddings table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS embeddings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_id INTEGER,
                        embedding BLOB,
                        FOREIGN KEY (message_id) REFERENCES messages (id)
                    )
                ''')
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def store_message(self, user_id: Optional[str], message: str, message_type: str) -> int:
        """Store a message in the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages (user_id, message, message_type) VALUES (?, ?, ?)",
                    (user_id, message, message_type)
                )
                conn.commit()
                return cursor.lastrowid
                
        except Exception as e:
            logger.error(f"Error storing message: {e}")
            raise
    
    def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get conversation history for a user"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT message, message_type, timestamp 
                    FROM messages 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (user_id, limit))
                
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
    
    def store_embedding(self, message_id: int, embedding: bytes):
        """Store an embedding for a message"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO embeddings (message_id, embedding) VALUES (?, ?)",
                    (message_id, embedding)
                )
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error storing embedding: {e}")
            raise