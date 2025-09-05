#!/usr/bin/env python3
"""
Document Management Module for SAM Bot
Provides functionality to manage documents and clear knowledge base
"""

import os
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Document, KnowledgeChunk

logger = logging.getLogger(__name__)

# Create Blueprint for document management
doc_manager = Blueprint('document_manager', __name__, url_prefix='/api/admin')

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///sam_bot_production.db')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def clear_knowledge_base():
    """Clear all documents and knowledge chunks from the database"""
    db = SessionLocal()
    try:
        # Get counts before deletion
        doc_count = db.query(Document).count()
        chunk_count = db.query(KnowledgeChunk).count()
        
        # Delete knowledge chunks first (foreign key constraint)
        db.query(KnowledgeChunk).delete()
        
        # Delete documents
        db.query(Document).delete()
        
        db.commit()
        
        logger.info(f"Knowledge base cleared: {doc_count} documents, {chunk_count} chunks")
        return {
            'success': True,
            'documents_removed': doc_count,
            'chunks_removed': chunk_count,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error clearing knowledge base: {e}")
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        db.close()

def delete_document(document_id):
    """Delete a specific document and its chunks"""
    db = SessionLocal()
    try:
        # Find the document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return {
                'success': False,
                'error': f'Document with ID {document_id} not found'
            }
        
        doc_title = document.title
        
        # Delete associated knowledge chunks
        chunk_count = db.query(KnowledgeChunk).filter(
            KnowledgeChunk.document_id == document_id
        ).count()
        
        db.query(KnowledgeChunk).filter(
            KnowledgeChunk.document_id == document_id
        ).delete()
        
        # Delete the document
        db.delete(document)
        db.commit()
        
        logger.info(f"Deleted document: {doc_title} ({chunk_count} chunks)")
        return {
            'success': True,
            'document_title': doc_title,
            'chunks_removed': chunk_count,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting document {document_id}: {e}")
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        db.close()

def get_documents_info():
    """Get information about all documents in the knowledge base"""
    db = SessionLocal()
    try:
        documents = db.query(Document).all()
        
        doc_info = []
        for doc in documents:
            chunk_count = db.query(KnowledgeChunk).filter(
                KnowledgeChunk.document_id == doc.id
            ).count()
            
            doc_info.append({
                'id': doc.id,
                'title': doc.title,
                'filename': doc.filename,
                'file_type': doc.file_type,
                'file_size': doc.file_size,
                'upload_date': doc.upload_date.isoformat(),
                'chunks': chunk_count,
                'processed': doc.processed
            })
        
        return {
            'success': True,
            'documents': doc_info,
            'total_documents': len(doc_info),
            'total_chunks': sum(doc['chunks'] for doc in doc_info)
        }
        
    except Exception as e:
        logger.error(f"Error getting documents info: {e}")
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        db.close()

# API Endpoints

@doc_manager.route('/clear-knowledge-base', methods=['POST'])
def clear_kb_endpoint():
    """API endpoint to clear the entire knowledge base"""
    try:
        result = clear_knowledge_base()
        
        if result['success']:
            return jsonify({
                'message': 'Knowledge base cleared successfully',
                **result
            }), 200
        else:
            return jsonify({
                'error': 'Failed to clear knowledge base',
                **result
            }), 500
            
    except Exception as e:
        logger.error(f"Clear knowledge base endpoint error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@doc_manager.route('/delete-document/<int:doc_id>', methods=['DELETE'])
def delete_document_endpoint(doc_id):
    """API endpoint to delete a specific document"""
    try:
        result = delete_document(doc_id)
        
        if result['success']:
            return jsonify({
                'message': f'Document deleted successfully',
                **result
            }), 200
        else:
            return jsonify({
                'error': 'Failed to delete document',
                **result
            }), 400 if 'not found' in result.get('error', '') else 500
            
    except Exception as e:
        logger.error(f"Delete document endpoint error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@doc_manager.route('/documents', methods=['GET'])
def list_documents_endpoint():
    """API endpoint to list all documents"""
    try:
        result = get_documents_info()
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify({
                'error': 'Failed to retrieve documents',
                **result
            }), 500
            
    except Exception as e:
        logger.error(f"List documents endpoint error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@doc_manager.route('/status', methods=['GET'])
def status_endpoint():
    """API endpoint to get knowledge base status"""
    try:
        result = get_documents_info()
        
        if result['success']:
            return jsonify({
                'status': 'healthy',
                'knowledge_base_size': result['total_chunks'],
                'total_documents': result['total_documents'],
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'error': result.get('error', 'Unknown error')
            }), 500
            
    except Exception as e:
        logger.error(f"Status endpoint error: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# CLI Functions for standalone use

def main():
    """CLI interface for document management"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python document_manager.py list              - List all documents")
        print("  python document_manager.py clear             - Clear all documents")
        print("  python document_manager.py delete <id>       - Delete specific document")
        print("  python document_manager.py status            - Show status")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'list':
        result = get_documents_info()
        if result['success']:
            print(f"📚 Total Documents: {result['total_documents']}")
            print(f"🧩 Total Chunks: {result['total_chunks']}")
            print()
            for doc in result['documents']:
                print(f"ID: {doc['id']} | {doc['title']} | Chunks: {doc['chunks']} | Type: {doc['file_type']}")
        else:
            print(f"Error: {result['error']}")
    
    elif command == 'clear':
        print("⚠️  This will delete ALL documents and knowledge chunks!")
        confirm = input("Continue? (y/N): ").lower().strip()
        if confirm in ['y', 'yes']:
            result = clear_knowledge_base()
            if result['success']:
                print(f"✅ Cleared {result['documents_removed']} documents and {result['chunks_removed']} chunks")
            else:
                print(f"Error: {result['error']}")
        else:
            print("Cancelled")
    
    elif command == 'delete':
        if len(sys.argv) < 3:
            print("Please specify document ID")
            return
        
        try:
            doc_id = int(sys.argv[2])
            result = delete_document(doc_id)
            if result['success']:
                print(f"✅ Deleted document: {result['document_title']}")
            else:
                print(f"Error: {result['error']}")
        except ValueError:
            print("Invalid document ID")
    
    elif command == 'status':
        result = get_documents_info()
        if result['success']:
            print(f"Knowledge Base Status:")
            print(f"  Documents: {result['total_documents']}")
            print(f"  Chunks: {result['total_chunks']}")
            print(f"  Status: {'Empty' if result['total_documents'] == 0 else 'Active'}")
        else:
            print(f"Error: {result['error']}")
    
    else:
        print(f"Unknown command: {command}")

if __name__ == '__main__':
    main()
