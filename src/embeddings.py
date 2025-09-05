"""
Embedding processing for SAM Bot
"""
import logging
from typing import List, Optional
import pickle
import math

logger = logging.getLogger(__name__)

class EmbeddingProcessor:
    def __init__(self):
        """Initialize the embedding processor"""
        logger.info("Embedding processor initialized")
    
    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text (simple implementation)"""
        try:
            # Simple word-based embedding (for demo purposes)
            # In production, use models like sentence-transformers
            words = text.lower().split()
            
            # Create a simple hash-based embedding
            embedding = [0.0] * 384  # Standard embedding dimension
            
            for i, word in enumerate(words[:50]):  # Limit to 50 words
                word_hash = hash(word) % 384
                embedding[word_hash] += 1.0 / (i + 1)  # Position weighting
            
            # Normalize
            norm = math.sqrt(sum(x * x for x in embedding))
            if norm > 0:
                embedding = [x / norm for x in embedding]
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return [0.0] * 384
    
    def serialize_embedding(self, embedding: List[float]) -> bytes:
        """Serialize embedding for storage"""
        try:
            return pickle.dumps(embedding)
        except Exception as e:
            logger.error(f"Error serializing embedding: {e}")
            return b''
    
    def deserialize_embedding(self, data: bytes) -> Optional[List[float]]:
        """Deserialize embedding from storage"""
        try:
            return pickle.loads(data)
        except Exception as e:
            logger.error(f"Error deserializing embedding: {e}")
            return None
    
    def similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between embeddings"""
        try:
            # Calculate dot product
            dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
            
            # Calculate norms
            norm1 = math.sqrt(sum(x * x for x in embedding1))
            norm2 = math.sqrt(sum(x * x for x in embedding2))
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return dot_product / (norm1 * norm2)
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0