#!/usr/bin/env python3
"""
Database Cleanup Script for SAM Bot
This script clears all old documents and knowledge base data to ensure fresh responses
"""

import sqlite3
import os
import sys
from datetime import datetime

def cleanup_database():
    """Clear all documents and knowledge chunks from the database"""
    db_path = 'sam_bot_production.db'
    
    if not os.path.exists(db_path):
        print("❌ Database file not found!")
        return False
    
    try:
        # Backup the database first
        backup_path = f'sam_bot_production_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        
        print(f"📋 Creating backup: {backup_path}")
        import shutil
        shutil.copy2(db_path, backup_path)
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current data
        cursor.execute('SELECT COUNT(*) FROM documents')
        doc_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM knowledge_chunks')
        chunk_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM conversations')
        conversation_count = cursor.fetchone()[0]
        
        print(f"📊 Current database state:")
        print(f"   • Documents: {doc_count}")
        print(f"   • Knowledge chunks: {chunk_count}")
        print(f"   • Conversations: {conversation_count}")
        
        if doc_count == 0 and chunk_count == 0:
            print("✅ Database is already clean!")
            conn.close()
            return True
        
        # Ask for confirmation
        print(f"\n⚠️  This will DELETE:")
        print(f"   • All {doc_count} documents")
        print(f"   • All {chunk_count} knowledge chunks")
        print(f"   • Keep {conversation_count} conversations (for history)")
        
        confirm = input("\n❓ Continue with cleanup? (y/N): ").lower().strip()
        
        if confirm not in ['y', 'yes']:
            print("❌ Cleanup cancelled")
            conn.close()
            return False
        
        # Clear knowledge chunks first (due to foreign key constraints)
        print("🧹 Clearing knowledge chunks...")
        cursor.execute('DELETE FROM knowledge_chunks')
        
        # Clear documents
        print("🧹 Clearing documents...")
        cursor.execute('DELETE FROM documents')
        
        # Reset autoincrement counters
        cursor.execute('DELETE FROM sqlite_sequence WHERE name IN ("documents", "knowledge_chunks")')
        
        # Commit changes
        conn.commit()
        
        # Verify cleanup
        cursor.execute('SELECT COUNT(*) FROM documents')
        remaining_docs = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM knowledge_chunks')
        remaining_chunks = cursor.fetchone()[0]
        
        conn.close()
        
        if remaining_docs == 0 and remaining_chunks == 0:
            print("✅ Database cleanup successful!")
            print(f"💾 Backup saved as: {backup_path}")
            print("\n🚀 Your SAM bot will now provide fresh responses!")
            return True
        else:
            print("❌ Cleanup incomplete - some data remains")
            return False
            
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        return False

def show_current_data():
    """Show current data in the database"""
    db_path = 'sam_bot_production.db'
    
    if not os.path.exists(db_path):
        print("❌ Database file not found!")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("📋 Current Documents:")
        cursor.execute('SELECT id, title, filename, file_type, upload_date FROM documents')
        docs = cursor.fetchall()
        
        if docs:
            for doc in docs:
                print(f"   ID: {doc[0]} | {doc[1]} | Type: {doc[3]} | Date: {doc[4]}")
        else:
            print("   No documents found")
        
        print(f"\n📊 Knowledge chunks: {cursor.execute('SELECT COUNT(*) FROM knowledge_chunks').fetchone()[0]}")
        print(f"💬 Conversations: {cursor.execute('SELECT COUNT(*) FROM conversations').fetchone()[0]}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")

def main():
    """Main function"""
    print("🤖 SAM Bot Database Cleanup Tool")
    print("=" * 40)
    
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--show', '-s']:
            show_current_data()
            return
        elif sys.argv[1] in ['--help', '-h']:
            print("Usage:")
            print("  python cleanup_database.py          - Clean database")
            print("  python cleanup_database.py --show   - Show current data")
            print("  python cleanup_database.py --help   - Show this help")
            return
    
    show_current_data()
    print()
    
    if cleanup_database():
        print("\n💡 Tip: Restart your SAM bot to see the changes!")
        print("     python app.py")
    else:
        print("\n⚠️  Cleanup failed - check the error messages above")

if __name__ == "__main__":
    main()
