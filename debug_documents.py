#!/usr/bin/env python3
"""
Debug script to check document order and IDs in database
"""

import sqlite3
import os

def check_documents():
    """Check current documents in database"""
    db_path = 'sam_bot_production.db'
    
    if not os.path.exists(db_path):
        print("❌ Database file not found!")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("📋 Current Documents (ordered by ID):")
        cursor.execute('SELECT id, title, filename, file_type, upload_date FROM documents ORDER BY id')
        docs = cursor.fetchall()
        
        if docs:
            max_id = max(doc[0] for doc in docs)
            print(f"📊 Maximum Document ID: {max_id}")
            print()
            
            for doc in docs:
                is_newest = "🔥 NEWEST" if doc[0] == max_id else ""
                print(f"ID: {doc[0]} | {doc[1]} | Type: {doc[3]} | Date: {doc[4]} {is_newest}")
        else:
            print("   No documents found")
        
        print(f"\n📊 Knowledge chunks:")
        cursor.execute('SELECT document_id, COUNT(*) FROM knowledge_chunks GROUP BY document_id ORDER BY document_id')
        chunks = cursor.fetchall()
        for doc_id, count in chunks:
            is_newest = "🔥 NEWEST" if doc_id == max_id else ""
            print(f"   Document ID {doc_id}: {count} chunks {is_newest}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")

if __name__ == "__main__":
    check_documents()
