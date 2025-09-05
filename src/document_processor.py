"""
Advanced document processing with LangChain and embeddings
"""
import logging
from typing import List, Tuple, Optional
from pathlib import Path
import json
import os

try:
    from langchain.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logging.warning("LangChain not available, using basic text processing")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("SentenceTransformers not available, using basic embeddings")

import numpy as np

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """Initialize document processor with embedding model"""
        self.chunk_size = 1000
        self.chunk_overlap = 200
        
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer(model_name)
                logger.info(f"Loaded SentenceTransformer model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to load SentenceTransformer: {e}")
                self.embedding_model = None
        else:
            self.embedding_model = None
        
        if LANGCHAIN_AVAILABLE:
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n", "\n", " ", ""]
            )
        else:
            self.text_splitter = None
    
    def process_document(self, file_path: str) -> Tuple[List[str], List[List[float]]]:
        """Process a document file and return chunks with embeddings"""
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Load document content
            content = self.load_document(file_path)
            
            # Split into chunks
            chunks = self.split_text(content)
            
            # Generate embeddings
            embeddings = self.generate_embeddings(chunks)
            
            logger.info(f"Processed document: {len(chunks)} chunks generated")
            return chunks, embeddings
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            raise
    
    def load_document(self, file_path: Path) -> str:
        """Load document content based on file type"""
        try:
            suffix = file_path.suffix.lower()
            
            if LANGCHAIN_AVAILABLE:
                if suffix == '.pdf':
                    loader = PyPDFLoader(str(file_path))
                    documents = loader.load()
                    return "\n".join([doc.page_content for doc in documents])
                
                elif suffix == '.docx':
                    loader = Docx2txtLoader(str(file_path))
                    documents = loader.load()
                    return "\n".join([doc.page_content for doc in documents])
                
                elif suffix in ['.txt', '.md']:
                    loader = TextLoader(str(file_path))
                    documents = loader.load()
                    return "\n".join([doc.page_content for doc in documents])
            
            # Fallback to basic file reading
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Error loading document {file_path}: {e}")
            raise
    
    def split_text(self, text: str) -> List[str]:
        """Split text into chunks"""
        try:
            if self.text_splitter:
                # Use LangChain text splitter
                chunks = self.text_splitter.split_text(text)
                return chunks
            else:
                # Basic splitting
                words = text.split()
                chunks = []
                current_chunk = []
                current_length = 0
                
                for word in words:
                    if current_length + len(word) + 1 > self.chunk_size:
                        if current_chunk:
                            chunks.append(" ".join(current_chunk))
                            # Keep some overlap
                            overlap_words = current_chunk[-20:] if len(current_chunk) > 20 else current_chunk
                            current_chunk = overlap_words + [word]
                            current_length = sum(len(w) + 1 for w in current_chunk)
                        else:
                            current_chunk = [word]
                            current_length = len(word)
                    else:
                        current_chunk.append(word)
                        current_length += len(word) + 1
                
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                
                return chunks
                
        except Exception as e:
            logger.error(f"Error splitting text: {e}")
            return [text]  # Return original text as single chunk
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for text chunks"""
        try:
            if self.embedding_model and texts:
                embeddings = self.embedding_model.encode(texts, convert_to_numpy=True)
                return embeddings.tolist()
            else:
                # Return dummy embeddings if model not available
                return [[0.0] * 384 for _ in texts]  # 384 is typical for MiniLM
                
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return [[0.0] * 384 for _ in texts]
    
    def process_text_content(self, title: str, content: str) -> Tuple[List[str], List[List[float]]]:
        """Process text content directly (without file)"""
        try:
            # Split into chunks
            chunks = self.split_text(content)
            
            # Add title context to first chunk if provided
            if title and chunks:
                chunks[0] = f"Title: {title}\n\n{chunks[0]}"
            
            # Generate embeddings
            embeddings = self.generate_embeddings(chunks)
            
            logger.info(f"Processed text content: {len(chunks)} chunks generated")
            return chunks, embeddings
            
        except Exception as e:
            logger.error(f"Error processing text content: {e}")
            raise
    
    def similarity_search(self, query_embedding: List[float], document_embeddings: List[List[float]], 
                         top_k: int = 5) -> List[int]:
        """Find most similar document chunks using cosine similarity"""
        try:
            if not document_embeddings or not query_embedding:
                return []
            
            query_array = np.array(query_embedding)
            doc_arrays = np.array(document_embeddings)
            
            # Calculate cosine similarity
            similarities = np.dot(doc_arrays, query_array) / (
                np.linalg.norm(doc_arrays, axis=1) * np.linalg.norm(query_array)
            )
            
            # Get top-k indices
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            return top_indices.tolist()
            
        except Exception as e:
            logger.error(f"Error in similarity search: {e}")
            return []
    
    def get_embedding_model_info(self) -> dict:
        """Get information about the embedding model"""
        return {
            "model_available": self.embedding_model is not None,
            "model_name": getattr(self.embedding_model, 'model_name', 'unknown') if self.embedding_model else None,
            "langchain_available": LANGCHAIN_AVAILABLE,
            "sentence_transformers_available": SENTENCE_TRANSFORMERS_AVAILABLE
        }