#!/usr/bin/env python3
"""
SAM Bot - Production API
Search Augmented Model with OpenAI Integration
"""

import os
import logging
import traceback
from datetime import datetime, timedelta
from pathlib import Path
import uuid
import json

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

import openai
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'change-this-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_FILE_SIZE', 16777216))  # 16MB

CORS(app, origins=os.getenv('ALLOWED_ORIGINS', '*').split(','))
jwt = JWTManager(app)

# Initialize OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key or openai.api_key == 'sk-your-actual-openai-api-key-here':
    logger.warning("⚠️  OpenAI API key not configured. Some features will be limited.")

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///sam_bot_production.db')
engine = create_engine(DATABASE_URL, echo=os.getenv('DB_ECHO', 'false').lower() == 'true')
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Database Models
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class Document(Base):
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    processed = Column(Boolean, default=False)
    user_id = Column(Integer, nullable=True)

class Conversation(Base):
    __tablename__ = 'conversations'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100), nullable=False)
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    confidence_score = Column(Float, default=0.0)
    sources_used = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, nullable=True)

class KnowledgeChunk(Base):
    __tablename__ = 'knowledge_chunks'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    embedding_summary = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(engine)

# Knowledge Base (in-memory for quick access)
KNOWLEDGE_BASE = {}

# Track most recent document per session
SESSION_RECENT_DOCS = {}

def load_knowledge_base():
    """Load knowledge base from database - Serverless compatible"""
    global KNOWLEDGE_BASE

    # In serverless, check if already loaded to avoid repeated database hits
    if KNOWLEDGE_BASE:
        return

    db = SessionLocal()
    try:
        chunks = db.query(KnowledgeChunk).all()
        documents = db.query(Document).order_by(Document.upload_date.desc()).all()  # Order by most recent first

        doc_map = {doc.id: doc for doc in documents}

        for chunk in chunks:
            doc = doc_map.get(chunk.document_id)
            if doc:
                KNOWLEDGE_BASE[f"{doc.id}_{chunk.id}"] = {
                    'title': doc.title,
                    'content': chunk.chunk_text,
                    'document_type': doc.file_type,
                    'document_id': doc.id,
                    'chunk_id': chunk.id,
                    'upload_date': doc.upload_date  # Add upload date for recency scoring
                }

        logger.info(f"✅ Loaded {len(KNOWLEDGE_BASE)} knowledge chunks")
    except Exception as e:
        logger.error(f"Failed to load knowledge base: {e}")
    finally:
        db.close()

def should_search_documents(query):
    """Determine if a query should search documents or be handled as general conversation"""
    query_lower = query.strip().lower()
    
    # Skip document search for basic greetings and conversational phrases
    skip_phrases = [
        'hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening',
        'goog morning', 'gud morning', 'morning', 'evening', 'afternoon',
        'yes', 'no', 'ok', 'okay', 'thanks', 'thank you', 'bye', 'goodbye',
        'bhai', 'dude', 'bro', 'mate', 'hmm', 'uh', 'oh', 'ah', 'hm'
    ]
    
    # Check for greeting variations (including typos) - but be precise to avoid false matches
    for phrase in skip_phrases:
        # Use word boundaries to avoid partial matches (like 'hi' matching 'this')
        import re
        pattern = r'\b' + re.escape(phrase) + r'\b'
        if re.search(pattern, query_lower) or query_lower == phrase:
            return False
    
    # Skip if query is just a greeting or short conversational word (after checking phrases)
    if len(query_lower) <= 3:
        return False
    
    # Skip for basic math expressions
    if any(char in query_lower for char in ['+', '-', '*', '/', '=']) and any(char.isdigit() for char in query_lower):
        return False
    
    # Skip for basic questions that don't need documents (but allow document-related "what is" questions)
    basic_question_starters = ['how to', 'why', 'when', 'where', 'who', 'help me with', 'can you']
    if any(query_lower.startswith(starter) for starter in basic_question_starters) and 'document' not in query_lower and 'file' not in query_lower:
        return False
    
    # Search documents for specific document-related queries
    document_keywords = [
        'document', 'file', 'pdf', 'content', 'text', 'paper', 'report',
        'summary', 'summarize', 'analyze', 'extract', 'find in', 'search in',
        'mark', 'grade', 'score', 'student', 'name', 'roll', 'enrollment',
        'subject', 'course', 'university', 'college', 'school', 'exam',
        'resume', 'cv', 'qualification', 'education', 'experience',
        'github', 'linkedin', 'email', 'phone', 'contact', 'link', 'website',
        'skills', 'projects', 'work', 'job', 'company', 'profile'
    ]
    
    # Special phrases that should always search documents
    document_phrases = [
        'what is this about', 'what is this', 'what does this say', 'tell me about this',
        'what does it contain', 'what is in this', 'describe this', 'explain this',
        'about this', 'this document', 'this file', 'what are the details',
        'show me', 'find', 'search', 'what it is about', 'what it is about this',
        'what about this', 'tell me about', 'what does it say', 'what is inside',
        'content of this', 'details of this', 'more detailed', 'more details',
        'detailed information', 'tell me more', 'i want more', 'more about this'
    ]
    
    # Check for document-related phrases
    for phrase in document_phrases:
        if phrase in query_lower:
            return True
    
    # Additional pattern matching for common document queries
    if ('what' in query_lower and 'this' in query_lower) or ('about' in query_lower and 'this' in query_lower):
        return True
    
    if ('tell' in query_lower and 'about' in query_lower) or ('describe' in query_lower):
        return True
    
    # Only search if query contains document-related keywords or is a substantial query
    return any(keyword in query_lower for keyword in document_keywords) or len(query_lower.split()) > 4

def search_knowledge_base(query, limit=5, session_id=None):
    """Search knowledge base with session-aware relevance scoring"""
    # Check if we should search documents for this query
    if not should_search_documents(query):
        return []
    
    query_lower = query.lower()
    query_words = [word.strip() for word in query_lower.split() if len(word.strip()) > 2]
    
    # Check if this is a general query about "this document" (should use most recent)
    is_general_query = any(phrase in query_lower for phrase in [
        'what is this', 'what about this', 'about this', 'this document',
        'what is this about', 'tell me about this', 'describe this',
        'what are the main points', 'main points', 'explain the content',
        'explain this', 'summarize this', 'summary of this', 'content of this',
        'what does this say', 'what is in this', 'details of this',
        'more detailed', 'more details', 'detailed information', 'tell me more', 'i want more',
        'what is tis about', 'what tis about', 'about tis'  # Handle common typos
    ]) or (
        # Also treat standalone queries as general if they don't mention specific keywords
        query_lower in ['summarize', 'summary', 'explain', 'describe', 'main points', 'key points', 'overview', 'more', 'details']
    ) or (
        # Pattern-based detection for flexible matching
        ('what' in query_lower and ('this' in query_lower or 'tis' in query_lower) and 'about' in query_lower)
    )
    
    # For general queries, prioritize session's most recent document
    if is_general_query and session_id and session_id in SESSION_RECENT_DOCS:
        recent_doc = SESSION_RECENT_DOCS[session_id]
        recent_doc_id = recent_doc['document_id']
        
        # Find and return the session's most recent document FIRST
        for key, item in KNOWLEDGE_BASE.items():
            if item['document_id'] == recent_doc_id:
                logger.info(f"Prioritizing session's recent document: {item['title']} (ID: {recent_doc_id})")
                return [{
                    'title': item['title'],
                    'content': item['content'][:300] + ('...' if len(item['content']) > 300 else ''),
                    'score': 100,  # Perfect score
                    'document_id': item['document_id'],
                    'chunk_id': item['chunk_id']
                }]
    
    # Fallback: For general queries without session data, use global most recent
    if is_general_query:
        max_document_id = max([item['document_id'] for item in KNOWLEDGE_BASE.values()]) if KNOWLEDGE_BASE else 0
        
        # Find and return ONLY the most recent document globally
        for key, item in KNOWLEDGE_BASE.items():
            if item['document_id'] == max_document_id:
                logger.info(f"Using globally most recent document: {item['title']} (ID: {max_document_id})")
                return [{
                    'title': item['title'],
                    'content': item['content'][:300] + ('...' if len(item['content']) > 300 else ''),
                    'score': 100,  # Perfect score
                    'document_id': item['document_id'],
                    'chunk_id': item['chunk_id']
                }]
        
        # Fallback if no recent document found
        return []
    
    # For specific queries, use normal scoring
    results = []
    for key, item in KNOWLEDGE_BASE.items():
        score = 0
        
        # Title matching (high weight)
        title_lower = item['title'].lower()
        for word in query_words:
            if word in title_lower:
                score += 3
        
        # Content matching (medium weight)
        content_lower = item['content'].lower()
        for word in query_words:
            if word in content_lower:
                score += 1
        
        # Exact phrase matching (highest weight)
        if query_lower in title_lower:
            score += 10
        if query_lower in content_lower:
            score += 5
        
        # Boost score for PDF files over URL files
        if item['title'].endswith('.pdf'):
            score += 2
        
        # Boost score for substantial content (not just metadata)
        if len(item['content']) > 200 and 'Content extraction for this file type' not in item['content']:
            score += 2
        
        if score > 0:
            results.append({
                'title': item['title'],
                'content': item['content'][:300] + ('...' if len(item['content']) > 300 else ''),
                'score': score,
                'document_id': item['document_id'],
                'chunk_id': item['chunk_id']
            })
    
    # Sort by score (highest first)
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:limit]

# Global flag to skip OpenAI calls when quota exceeded
OPENAI_QUOTA_EXCEEDED = False

def generate_intelligent_fallback(message, context_chunks=None):
    """Generate intelligent responses based on document content and query analysis"""
    if not context_chunks:
        return generate_no_context_response(message)
    
    # Get the best matching document
    best_chunk = context_chunks[0]
    content = best_chunk['content']
    query_lower = message.lower().strip()
    
    # Advanced question analysis and content extraction
    if any(word in query_lower for word in ['mark', 'marks', 'grade', 'grades', 'score', 'scores', 'cgpa', 'gpa', 'percentage', 'result', 'performance']):
        return extract_academic_performance(content, best_chunk['title'], query_lower)
    
    elif any(word in query_lower for word in ['name', 'student', 'who', 'person']):
        return extract_student_info(content, best_chunk['title'])
    
    elif any(word in query_lower for word in ['subject', 'subjects', 'course', 'courses', 'paper', 'papers', 'module', 'modules']):
        return extract_subjects(content, best_chunk['title'])
    
    elif any(word in query_lower for word in ['university', 'college', 'institution', 'school', 'where']):
        return extract_institution_info(content, best_chunk['title'])
    
    elif any(word in query_lower for word in ['semester', 'year', 'when', 'date', 'time', 'examination', 'exam']):
        return extract_time_info(content, best_chunk['title'])
    
    elif any(word in query_lower for word in ['about', 'what', 'describe', 'summary', 'summarize', 'tell me']):
        return generate_document_summary(content, best_chunk['title'])
    
    elif any(word in query_lower for word in ['father', 'parent', 'family']):
        return extract_family_info(content, best_chunk['title'])
    
    elif any(word in query_lower for word in ['roll', 'enrollment', 'id', 'number']):
        return extract_id_info(content, best_chunk['title'])
    
    else:
        # Smart content search for specific terms
        return search_specific_content(content, best_chunk['title'], query_lower)

def extract_academic_performance(content, title, query):
    """Extract academic performance information"""
    lines = content.split('\n')
    performance_data = []
    
    for line in lines:
        line_lower = line.lower()
        if any(term in line_lower for term in ['mark', 'grade', 'score', 'cgpa', 'gpa', '%', 'point', 'total', 'obtained']):
            if any(char.isdigit() for char in line):  # Has numbers
                performance_data.append(line.strip())
    
    if performance_data:
        response = f"📊 **Academic Performance from {title}:**\n\n"
        
        # Group similar data
        subjects_found = []
        totals_found = []
        
        for data in performance_data[:8]:  # Limit to first 8 relevant lines
            if any(word in data.lower() for word in ['total', 'cgpa', 'gpa', 'percentage', 'overall']):
                totals_found.append(f"🎯 {data}")
            else:
                subjects_found.append(f"📚 {data}")
        
        if totals_found:
            response += "**Overall Performance:**\n" + "\n".join(totals_found) + "\n\n"
        
        if subjects_found:
            response += "**Subject-wise Details:**\n" + "\n".join(subjects_found[:5])
        
        response += "\n\n💡 *Ask about specific subjects or grades for more details!*"
    else:
        response = f"📄 **From {title}:**\n\nI can see this is an academic document, but I need more specific information to find the exact marks you're looking for.\n\n🔍 **Try asking:**\n• 'What subjects are there?'\n• 'Show me the total marks'\n• 'What is the CGPA?'"
    
    return {
        'response': response,
        'confidence_score': 0.9,
        'sources_used': 1
    }

def extract_student_info(content, title):
    """Extract student information"""
    lines = content.split('\n')
    student_data = []
    
    for line in lines:
        line_lower = line.lower()
        if any(term in line_lower for term in ['name', 'student', 'roll', 'enrollment', 'father', 'mother']):
            if ':' in line and len(line.strip()) > 5:
                student_data.append(line.strip())
    
    if student_data:
        response = f"👤 **Student Information from {title}:**\n\n"
        response += "\n".join([f"📋 {data}" for data in student_data[:6]])
        response += "\n\n💡 *This information is extracted from your academic document.*"
    else:
        # Try to find names in general content
        words = content.split()
        potential_names = []
        for i, word in enumerate(words):
            if word.isupper() and len(word) > 2 and word.isalpha():
                if i < len(words)-1 and words[i+1].isupper() and words[i+1].isalpha():
                    potential_names.append(f"{word} {words[i+1]}")
        
        if potential_names:
            response = f"👤 **Names found in {title}:**\n\n"
            response += "\n".join([f"📋 {name}" for name in potential_names[:3]])
        else:
            response = f"👤 **From {title}:**\n\nI can see this is a student document but need to look more carefully for specific name information.\n\n🔍 **The document contains:** {content[:200]}..."
    
    return {
        'response': response,
        'confidence_score': 0.8,
        'sources_used': 1
    }

def extract_subjects(content, title):
    """Extract subject/course information"""
    lines = content.split('\n')
    subjects = []
    
    # Common subject indicators
    subject_keywords = ['engineering', 'mathematics', 'physics', 'chemistry', 'computer', 'science', 'communication', 'management', 'economics', 'statistics', 'programming', 'software', 'hardware', 'electronics', 'mechanical', 'civil', 'electrical']
    
    for line in lines:
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in subject_keywords):
            if len(line.strip()) > 10:
                subjects.append(line.strip())
    
    if subjects:
        response = f"📚 **Subjects/Courses from {title}:**\n\n"
        response += "\n".join([f"📖 {subject}" for subject in subjects[:6]])
        response += "\n\n💡 *Ask about marks in specific subjects for detailed performance!*"
    else:
        # Look for course codes (like THU201, CSE101, etc.)
        import re
        course_codes = re.findall(r'[A-Z]{2,4}\d{2,4}', content)
        if course_codes:
            response = f"📚 **Course Codes found in {title}:**\n\n"
            response += "\n".join([f"📖 {code}" for code in course_codes[:8]])
        else:
            response = f"📚 **From {title}:**\n\nThis appears to be an academic document. Let me show you the content structure:\n\n{content[:300]}...\n\n🔍 **Try asking:** 'What are the marks?' or 'Show me the performance'"
    
    return {
        'response': response,
        'confidence_score': 0.8,
        'sources_used': 1
    }

def extract_institution_info(content, title):
    """Extract institution information"""
    lines = content.split('\n')
    institution_data = []
    
    for line in lines:
        line_lower = line.lower()
        if any(term in line_lower for term in ['university', 'college', 'institute', 'school', 'road', 'address', 'www']):
            if len(line.strip()) > 5:
                institution_data.append(line.strip())
    
    response = f"🏛️ **Institution Information from {title}:**\n\n"
    if institution_data:
        response += "\n".join([f"🏢 {data}" for data in institution_data[:5]])
    else:
        # Look for capitalized institution names
        words = content.split()
        potential_institutions = []
        for word in words:
            if 'university' in word.lower() or 'college' in word.lower():
                potential_institutions.append(word)
        
        if potential_institutions:
            response += "\n".join([f"🏢 {inst}" for inst in potential_institutions[:3]])
        else:
            response += f"I can see this is an educational document. Here's the header information:\n\n{content[:200]}..."
    
    return {
        'response': response,
        'confidence_score': 0.8,
        'sources_used': 1
    }

def generate_document_summary(content, title):
    """Generate intelligent document summary"""
    lines = [line.strip() for line in content.split('\n') if line.strip() and len(line.strip()) > 10]
    
    # Identify document type
    doc_type = "Document"
    if 'marksheet' in title.lower() or 'marks' in content.lower():
        doc_type = "Academic Marksheet"
    elif 'transcript' in title.lower():
        doc_type = "Academic Transcript"
    elif 'certificate' in title.lower():
        doc_type = "Certificate"
    
    response = f"📋 **Summary of {title}:**\n\n"
    response += f"📄 **Document Type:** {doc_type}\n\n"
    response += f"📊 **Key Information:**\n"
    
    # Show most important lines
    important_lines = lines[:6]
    for i, line in enumerate(important_lines, 1):
        response += f"{i}. {line}\n"
    
    response += "\n💬 **You can ask me:**\n"
    response += "• What is this document about?\n"
    response += "• What are the main points?\n"
    response += "• Find specific information\n"
    response += "• Explain the content"
    
    return {
        'response': response,
        'confidence_score': 0.9,
        'sources_used': 1
    }

def search_specific_content(content, title, query):
    """Search for specific terms in content"""
    lines = content.split('\n')
    relevant_lines = []
    query_lower = query.lower().strip()
    
    # Handle requests for more detailed information
    if any(phrase in query_lower for phrase in ['more detailed', 'more details', 'detailed information', 'tell me more', 'i want more']):
        # Return comprehensive document analysis
        response = f"📋 **Comprehensive Analysis of {title}:**\n\n"
        response += f"📄 **Full Content Preview:**\n{content[:800]}..\n\n"
        
        # Extract key sections
        sections = []
        current_section = ""
        
        for line in lines[:20]:  # Analyze first 20 lines
            if line.strip() and len(line.strip()) > 3:
                current_section += line.strip() + " "
                if len(current_section) > 100:
                    sections.append(current_section.strip())
                    current_section = ""
        
        if sections:
            response += "**📊 Key Sections:**\n"
            for i, section in enumerate(sections[:5], 1):
                response += f"{i}. {section}\n\n"
        
        response += "💡 **Ask me specific questions like:**\n"
        response += "• 'What are the skills mentioned?'\n"
        response += "• 'Show me contact information'\n"
        response += "• 'What is the education background?'\n"
        response += "• 'What projects are mentioned?'"
        
        return {'response': response, 'confidence_score': 0.9, 'sources_used': 1}
    
    # Special handling for common requests
    if 'github' in query_lower:
        github_lines = [line.strip() for line in lines if 'github' in line.lower()]
        if github_lines:
            response = f"🔗 **GitHub information from {title}:**\n\n"
            response += "\n".join([f"📌 {line}" for line in github_lines[:3]])
            return {'response': response, 'confidence_score': 0.9, 'sources_used': 1}
    
    elif 'linkedin' in query_lower:
        linkedin_lines = [line.strip() for line in lines if 'linkedin' in line.lower()]
        if linkedin_lines:
            response = f"🔗 **LinkedIn information from {title}:**\n\n"
            response += "\n".join([f"📌 {line}" for line in linkedin_lines[:3]])
            return {'response': response, 'confidence_score': 0.9, 'sources_used': 1}
    
    elif any(word in query_lower for word in ['email', 'contact', 'phone']):
        contact_lines = []
        for line in lines:
            if any(term in line.lower() for term in ['@', 'email', 'phone', 'contact', '+91', 'tel']):
                contact_lines.append(line.strip())
        if contact_lines:
            response = f"📧 **Contact information from {title}:**\n\n"
            response += "\n".join([f"📌 {line}" for line in contact_lines[:4]])
            return {'response': response, 'confidence_score': 0.9, 'sources_used': 1}
    
    # General search
    query_words = [word.strip().lower() for word in query_lower.split() if len(word.strip()) > 2]
    
    # Find lines containing query terms
    for line in lines:
        line_lower = line.lower()
        for word in query_words:
            if word in line_lower and len(line.strip()) > 5:
                relevant_lines.append(line.strip())
                break
    
    if relevant_lines:
        response = f"🔍 **Found '{query}' in {title}:**\n\n"
        response += "\n".join([f"📌 {line}" for line in relevant_lines[:5]])
        response += "\n\n🚀 *Need something specific? Just ask!*"
    else:
        response = f"📄 **About {title}:**\n\n{content[:300]}...\n\n💡 **Try asking:** 'What skills are mentioned?' or 'Show me contact details'"
    
    return {
        'response': response,
        'confidence_score': 0.8,
        'sources_used': 1
    }

def generate_no_context_response(message):
    """Generate response when no documents are available"""
    query_lower = message.lower().strip()
    
    # Enhanced greeting detection (including typos and variations)
    greeting_patterns = [
        'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
        'goog morning', 'gud morning', 'morning', 'evening', 'afternoon', 'helo', 'hii'
    ]
    
    if any(pattern in query_lower for pattern in greeting_patterns):
        import random
        greetings = [
            "👋 **Hello there! I'm SAM.**\n\nHow can I assist you today? Feel free to ask me anything!",
            "🌅 **Good to see you!** I'm SAM, your AI assistant.\n\nWhat can I help you with today?",
            "👋 **Hi! I'm SAM.**\n\nReady to help with questions, tasks, or just have a conversation. What's on your mind?"
        ]
        response = random.choice(greetings)
    
    # Help and capability requests
    elif any(phrase in query_lower for phrase in ['help', 'what can you do', 'what are you', 'who are you', 'capabilities']):
        response = "🤖 **I'm SAM - your intelligent AI assistant!**\n\n🎆 **I excel at:**\n• 🧠 Answering questions & explaining concepts\n• 📊 Research & data analysis\n• 💻 Programming & technical help\n• ✍️ Writing & creative tasks\n• 📄 Document analysis & summarization\n\n🚀 **Just tell me what you need - I'm here to help!**"
    
    # Math/calculation requests
    elif any(char in query_lower for char in ['+', '-', '*', '/', '=', 'calculate', 'math', 'solve']):
        if any(char.isdigit() for char in message):
            try:
                # Simple math evaluation (be careful with security)
                import re
                math_expr = re.findall(r'[0-9+\-*/.\s()]+', message)
                if math_expr:
                    # Basic calculation
                    result = eval(''.join(math_expr))
                    response = f"🧮 **Calculation Result:**\n\n**{message}** = **{result}**\n\n💡 *I can help with more complex math problems too!*"
                else:
                    response = f"🧮 **Math Help**\n\nI'd be happy to help with calculations! Could you provide the specific numbers or equation you'd like me to solve?\n\n**Example:** 15 + 25 = ? or What is 20% of 150?"
            except:
                response = f"🧮 **Math Help**\n\nI can help with calculations! Please provide a clear mathematical expression.\n\n**Examples:**\n• 15 + 25\n• What is 20% of 150?\n• Solve: 2x + 5 = 15"
        else:
            response = f"🧮 **Math & Calculations**\n\nI can help you with:\n• Basic arithmetic (+, -, ×, ÷)\n• Percentages and ratios\n• Algebraic equations\n• Unit conversions\n\n**Just ask:** What's 15 + 25? or Calculate 20% of 200"
    
    # Programming/coding questions
    elif any(word in query_lower for word in ['code', 'programming', 'python', 'javascript', 'html', 'css', 'sql', 'debug', 'error']):
        response = f"💻 **Programming & Code Help**\n\nI can assist with:\n• Writing and debugging code\n• Explaining programming concepts\n• Code review and optimization\n• Multiple languages (Python, JavaScript, etc.)\n• Troubleshooting errors\n\n🔧 **What specific programming question do you have?**"
    
    # Weather/time questions
    elif any(word in query_lower for word in ['weather', 'temperature', 'time', 'date', 'today']):
        response = f"🌤️ **Current Information**\n\nI don't have access to real-time data like current weather or exact time, but I can help with:\n• General weather information\n• Time zone conversions\n• Date calculations\n• Seasonal information\n\n💡 **Try asking:** What's the weather like in [city]? or Convert 3 PM EST to PST"
    
    # General knowledge questions
    elif any(word in query_lower for word in ['what', 'how', 'why', 'when', 'where', 'who', 'explain', 'tell me']):
        response = f"🧠 **Knowledge & Information**\n\nI'm ready to help answer your question: **\"{message}\"**\n\nI can provide information about:\n• Science and technology\n• History and current events\n• Arts and culture\n• Business and economics\n• Health and lifestyle\n• And much more!\n\n🤔 **Could you be more specific about what you'd like to know?**"
    
    # Handle requests for links/contact info that might need documents
    elif any(word in query_lower for word in ['github', 'linkedin', 'email', 'phone', 'contact', 'link', 'website']):
        response = f"🔍 **Looking for contact/profile information?**\n\nI'd be happy to help find {message}! If you have a resume or document uploaded, I can extract specific links and contact details from it.\n\n📎 **Otherwise, feel free to ask me:**\n• General questions about GitHub, LinkedIn, etc.\n• How to create profiles or find links\n• Tech advice and guidance"
    
    # Handle unclear or short queries more intelligently
    elif len(query_lower) <= 4 or query_lower in ['fuck', 'shit', 'damn', 'wtf', 'omg']:
        responses = [
            "🤔 **I'm not sure what you're looking for.**\n\nCould you ask me a specific question? I'm here to help with anything from tech questions to document analysis!",
            "😅 **Let's try that again!**\n\nWhat would you like help with? I can answer questions, solve problems, or just chat!",
            "💬 **I'm ready to help!**\n\nWhat's on your mind? Feel free to ask me anything - from simple questions to complex problems."
        ]
        import random
        response = random.choice(responses)
    
    # Intelligent default for substantial queries
    elif len(query_lower.split()) > 2:
        response = f"🧠 **Regarding: \"{message}\"**\n\nI'd be happy to help with this! Could you provide a bit more context or ask a specific question?\n\n💡 **For example:**\n• If it's a tech question, ask for specific help\n• If you want information, ask \"What is...\" or \"How does...\"\n• If you need analysis, upload a document first"
    
    # Simple fallback for very short queries
    else:
        response = f"👋 **Hi there!**\n\nI noticed you said \"{message}\" - how can I help you today?\n\n🎆 **I'm great at:**\n• Answering questions\n• Solving problems\n• Explaining concepts\n• Analyzing documents\n• Having conversations!"
    
    return {
        'response': response,
        'confidence_score': 0.8,
        'sources_used': 0
    }

def extract_time_info(content, title):
    """Extract time/date/semester information"""
    lines = content.split('\n')
    time_data = []
    
    for line in lines:
        line_lower = line.lower()
        if any(term in line_lower for term in ['semester', 'year', 'examination', 'exam', 'date', '202', '201', 'session']):
            if len(line.strip()) > 5:
                time_data.append(line.strip())
    
    if time_data:
        response = f"📅 **Time/Date Information from {title}:**\n\n"
        response += "\n".join([f"🗓️ {data}" for data in time_data[:5]])
    else:
        response = f"📅 **From {title}:**\n\nLet me look for time-related information...\n\n{content[:200]}..."
    
    return {
        'response': response,
        'confidence_score': 0.8,
        'sources_used': 1
    }

def extract_family_info(content, title):
    """Extract family information"""
    lines = content.split('\n')
    family_data = []
    
    for line in lines:
        line_lower = line.lower()
        if any(term in line_lower for term in ['father', 'mother', 'parent', 'guardian']):
            if ':' in line and len(line.strip()) > 5:
                family_data.append(line.strip())
    
    if family_data:
        response = f"👨‍👩‍👧‍👦 **Family Information from {title}:**\n\n"
        response += "\n".join([f"👤 {data}" for data in family_data[:3]])
    else:
        response = f"👨‍👩‍👧‍👦 **From {title}:**\n\nLooking for family information...\n\n{content[:200]}..."
    
    return {
        'response': response,
        'confidence_score': 0.8,
        'sources_used': 1
    }

def extract_id_info(content, title):
    """Extract ID/roll/enrollment information"""
    lines = content.split('\n')
    id_data = []
    
    for line in lines:
        line_lower = line.lower()
        if any(term in line_lower for term in ['roll', 'enrollment', 'id', 'number', 'registration']):
            if ':' in line and any(char.isdigit() for char in line):
                id_data.append(line.strip())
    
    if id_data:
        response = f"🆔 **ID/Registration Information from {title}:**\n\n"
        response += "\n".join([f"📋 {data}" for data in id_data[:4]])
    else:
        # Look for number patterns
        import re
        numbers = re.findall(r'\b\d{6,}\b', content)  # Find 6+ digit numbers
        if numbers:
            response = f"🆔 **Number patterns found in {title}:**\n\n"
            response += "\n".join([f"🔢 {num}" for num in numbers[:5]])
        else:
            response = f"🆔 **From {title}:**\n\nLooking for ID information...\n\n{content[:200]}..."
    
    return {
        'response': response,
        'confidence_score': 0.8,
        'sources_used': 1
    }

def generate_ai_response(message, context_chunks=None):
    """Generate AI response using OpenAI or intelligent fallback"""
    global OPENAI_QUOTA_EXCEEDED
    
    try:
        # Skip OpenAI if we know quota is exceeded for faster responses
        if OPENAI_QUOTA_EXCEEDED:
            logger.info("Skipping OpenAI call - using intelligent fallback")
            return generate_intelligent_fallback(message, context_chunks)
        
        # Build system prompt
        system_prompt = """You are SAM, a helpful and intelligent AI assistant. You can assist with a wide variety of tasks including answering questions, providing explanations, helping with problem-solving, creative tasks, and analyzing information.

Guidelines:
- Be helpful, accurate, and professional
- Use the provided context when relevant, but don't assume everything is about documents
- Provide clear, concise, and useful responses
- Be conversational and friendly
- If you don't know something, say so honestly
- Adapt your responses to the user's needs and context"""

        # Build context from knowledge chunks
        context_text = ""
        if context_chunks:
            context_text = "\n\nRelevant context from knowledge base:\n"
            for i, chunk in enumerate(context_chunks, 1):
                context_text += f"{i}. {chunk['title']}: {chunk['content']}\n"

        # Create the full prompt
        user_prompt = f"User question: {message}{context_text}"

        # Call OpenAI API
        if openai.api_key and openai.api_key != 'sk-your-actual-openai-api-key-here':
            client = openai.OpenAI(api_key=openai.api_key)
            response = client.chat.completions.create(
                model=os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=int(os.getenv('MAX_RESPONSE_TOKENS', 500)),
                temperature=float(os.getenv('OPENAI_TEMPERATURE', 0.7))
            )
            
            ai_response = response.choices[0].message.content
            confidence_score = 0.9 if context_chunks else 0.7
            
        else:
            # Enhanced fallback response with intelligent document analysis
            if context_chunks:
                # Analyze the document content intelligently
                best_chunk = context_chunks[0]
                content = best_chunk['content']
                
                # Smart document analysis based on query
                query_lower = message.lower()
                
                if 'mark' in query_lower or 'grade' in query_lower or 'score' in query_lower:
                    # Look for marks/grades in the content
                    lines = content.split('\n')
                    grade_info = []
                    for line in lines:
                        if any(term in line.lower() for term in ['mark', 'grade', 'score', 'cgpa', 'gpa', 'percentage', '%']):
                            grade_info.append(line.strip())
                    
                    if grade_info:
                        ai_response = f"**📊 Academic Performance from '{best_chunk['title']}':**\n\n" + "\n".join(grade_info[:5]) + "\n\n💡 *This is extracted from your marksheet document.*"
                    else:
                        ai_response = f"**📄 From '{best_chunk['title']}':**\n\n{content[:400]}...\n\n💡 *I found your document but couldn't locate specific grade information.*"
                
                elif any(word in query_lower for word in ['name', 'student', 'who']):
                    # Look for student information
                    lines = content.split('\n')
                    student_info = []
                    for line in lines:
                        if any(term in line.lower() for term in ['name', 'student', 'roll', 'id', 'enrollment']):
                            student_info.append(line.strip())
                    
                    if student_info:
                        ai_response = f"**👤 Student Information from '{best_chunk['title']}':**\n\n" + "\n".join(student_info[:3]) + "\n\n💡 *Extracted from your document.*"
                    else:
                        ai_response = f"**📄 From '{best_chunk['title']}':**\n\n{content[:300]}...\n\n💡 *I found your document - it appears to be an academic record.*"
                
                elif any(word in query_lower for word in ['about', 'what', 'describe', 'summary']):
                    # Provide a summary of the document
                    lines = content.split('\n')[:10]  # First 10 lines for summary
                    key_lines = [line.strip() for line in lines if line.strip() and len(line.strip()) > 10]
                    
                    ai_response = f"**📋 Document Summary - '{best_chunk['title']}':**\n\n"
                    if 'university' in content.lower() or 'college' in content.lower():
                        ai_response += "📚 **Academic Document**: This appears to be an educational record\n\n"
                    
                    ai_response += "**Key Information:**\n" + "\n".join([f"• {line}" for line in key_lines[:5]])
                    ai_response += "\n\n💡 *Ask me specific questions about marks, grades, student details, or subjects!*"
                
                elif any(word in query_lower for word in ['subject', 'course', 'paper']):
                    # Look for subject/course information
                    lines = content.split('\n')
                    subject_info = []
                    for line in lines:
                        if any(term in line for term in ['Engineering', 'Mathematics', 'Physics', 'Chemistry', 'Computer', 'Science']):
                            subject_info.append(line.strip())
                    
                    if subject_info:
                        ai_response = f"**📚 Subjects/Courses from '{best_chunk['title']}':**\n\n" + "\n".join(subject_info[:5]) + "\n\n💡 *These are the subjects found in your academic record.*"
                    else:
                        ai_response = f"**📄 From '{best_chunk['title']}':**\n\n{content[:350]}...\n\n💡 *I can see your document but need more specific subject information.*"
                
                else:
                    # General content-based response
                    ai_response = f"**📄 Based on '{best_chunk['title']}':**\n\n{content[:400]}...\n\n**💬 You can ask me:**\n• What are the marks/grades?\n• Who is the student?\n• What subjects are covered?\n• Summarize this document\n\n💡 *Ask specific questions for better answers!*"
                
                confidence_score = 0.8
            else:
                # Use the general no-context response function
                fallback_result = generate_no_context_response(message)
                ai_response = fallback_result['response']
                confidence_score = fallback_result['confidence_score']
        
        return {
            'response': ai_response,
            'confidence_score': confidence_score,
            'sources_used': len(context_chunks) if context_chunks else 0
        }
        
    except Exception as e:
        logger.error(f"AI response generation failed: {e}")
        
        # Handle specific OpenAI errors
        error_str = str(e).lower()
        if 'quota' in error_str or 'insufficient_quota' in error_str:
            # Set global flag to skip OpenAI for faster future responses
            OPENAI_QUOTA_EXCEEDED = True
            logger.info("OpenAI quota exceeded - switching to intelligent fallback mode")
            
            # Use intelligent document analysis
            return generate_intelligent_fallback(message, context_chunks)
        else:
            return {
                'response': "I'm sorry, I encountered an issue processing your request. Please try again.",
                'confidence_score': 0.0,
                'sources_used': 0
            }

def process_document(file):
    """Process uploaded document and extract text"""
    try:
        filename = secure_filename(file.filename)
        file_ext = Path(filename).suffix.lower()
        
        # Read file content based on type
        if file_ext == '.txt':
            content = file.read().decode('utf-8')
        elif file_ext == '.md':
            content = file.read().decode('utf-8')
        elif file_ext == '.json':
            content = file.read().decode('utf-8')
        elif file_ext == '.csv':
            content = file.read().decode('utf-8')
        elif file_ext == '.html':
            from bs4 import BeautifulSoup
            html_content = file.read().decode('utf-8')
            soup = BeautifulSoup(html_content, 'html.parser')
            content = soup.get_text()
        elif file_ext == '.pdf':
            # Extract text from PDF
            try:
                import pdfplumber
                file.seek(0)  # Reset file pointer
                with pdfplumber.open(file) as pdf:
                    content = ""
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            content += page_text + "\n\n"
                    
                    if not content.strip():
                        # Fallback to PyPDF2 if pdfplumber fails
                        file.seek(0)
                        import PyPDF2
                        pdf_reader = PyPDF2.PdfReader(file)
                        content = ""
                        for page in pdf_reader.pages:
                            content += page.extract_text() + "\n\n"
                    
                    if not content.strip():
                        content = f"PDF Document: {filename}\nUploaded: {datetime.now()}\nNote: This PDF appears to contain images or non-extractable text. Please try a text-based PDF."
                    
            except Exception as pdf_error:
                logger.warning(f"PDF extraction failed for {filename}: {pdf_error}")
                content = f"PDF Document: {filename}\nUploaded: {datetime.now()}\nNote: Could not extract text from this PDF. The file may be image-based or encrypted."
        else:
            # For other formats, store as text representation
            content = f"Document: {filename}\nFile type: {file_ext}\nUploaded: {datetime.now()}\nContent extraction for this file type requires additional processing."
        
        return {
            'content': content,
            'filename': filename,
            'file_type': file_ext,
            'file_size': len(content.encode('utf-8'))
        }
        
    except Exception as e:
        logger.error(f"Document processing failed: {e}")
        raise

def chunk_text(text, chunk_size=1000, overlap=200):
    """Split text into overlapping chunks"""
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk.strip())
    
    return chunks if chunks else [text]

# API Routes

@app.route('/')
def home():
    """Main chat interface"""
    return render_template('index.html')

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard"""
    return render_template('admin_dashboard.html')

@app.route('/favicon.ico')
def favicon():
    """Return a simple favicon response to avoid 404 errors"""
    return '', 204  # No content response

@app.route('/api/health', methods=['GET'])
def health_check():
    """System health check"""
    db = SessionLocal()
    try:
        # Test database connection
        db.execute('SELECT 1')
        db_status = 'healthy'
    except Exception:
        db_status = 'unhealthy'
    finally:
        db.close()
    
    # Test OpenAI connection
    openai_status = 'configured' if (openai.api_key and openai.api_key != 'sk-your-actual-openai-api-key-here') else 'not_configured'
    
    return jsonify({
        'status': 'healthy' if db_status == 'healthy' else 'degraded',
        'version': '2.0.0',
        'timestamp': datetime.utcnow().isoformat(),
        'services': {
            'database': db_status,
            'openai': openai_status,
            'knowledge_base': f'{len(KNOWLEDGE_BASE)} items loaded'
        }
    })

@app.route('/api/register', methods=['POST'])
def register():
    """Register new user"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not all([username, email, password]):
            return jsonify({'error': 'Username, email, and password are required'}), 400
        
        if len(password) < int(os.getenv('PASSWORD_MIN_LENGTH', 8)):
            return jsonify({'error': f'Password must be at least {os.getenv("PASSWORD_MIN_LENGTH", 8)} characters'}), 400
        
        db = SessionLocal()
        try:
            # Check if user exists
            existing_user = db.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing_user:
                return jsonify({'error': 'Username or email already exists'}), 409
            
            # Create new user
            password_hash = generate_password_hash(password)
            new_user = User(
                username=username,
                email=email,
                password_hash=password_hash
            )
            
            db.add(new_user)
            db.commit()
            
            # Generate access token
            access_token = create_access_token(identity=new_user.id)
            
            logger.info(f"New user registered: {username}")
            
            return jsonify({
                'message': 'User registered successfully',
                'access_token': access_token,
                'user': {
                    'id': new_user.id,
                    'username': new_user.username,
                    'email': new_user.email
                }
            }), 201
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    """User login"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        db = SessionLocal()
        try:
            user = db.query(User).filter(
                (User.username == username) | (User.email == username)
            ).first()
            
            if not user or not check_password_hash(user.password_hash, password):
                return jsonify({'error': 'Invalid credentials'}), 401
            
            if not user.is_active:
                return jsonify({'error': 'Account is disabled'}), 403
            
            access_token = create_access_token(identity=user.id)
            
            logger.info(f"User logged in: {user.username}")
            
            return jsonify({
                'access_token': access_token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            })
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Main chat endpoint with AI integration"""
    try:
        # Load knowledge base (serverless-compatible: loads on first request)
        load_knowledge_base()

        data = request.get_json()

        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400

        message = data['message'].strip()
        session_id = data.get('session_id', str(uuid.uuid4()))
        user_id = None

        # Try to get user ID from JWT if present
        try:
            user_id = get_jwt_identity()
        except:
            pass  # Anonymous user

        if not message:
            return jsonify({'error': 'Message cannot be empty'}), 400

        # Search knowledge base for relevant context
        context_chunks = search_knowledge_base(message, limit=3, session_id=session_id)
        
        # Generate AI response
        ai_result = generate_ai_response(message, context_chunks)
        
        # Store conversation
        db = SessionLocal()
        try:
            conversation = Conversation(
                session_id=session_id,
                user_message=message,
                bot_response=ai_result['response'],
                confidence_score=ai_result['confidence_score'],
                sources_used=ai_result['sources_used'],
                user_id=user_id
            )
            db.add(conversation)
            db.commit()
        finally:
            db.close()
        
        logger.info(f"Chat processed - User: {message[:50]}... | Sources: {ai_result['sources_used']} | Confidence: {ai_result['confidence_score']:.2f}")
        
        return jsonify({
            'response': ai_result['response'],
            'session_id': session_id,
            'confidence_score': ai_result['confidence_score'],
            'sources_used': ai_result['sources_used'],
            'context_used': len(context_chunks) > 0,
            'knowledge_sources': len(context_chunks),
            'conversation_history': 0,  # TODO: Implement conversation history
            'context_chunks': [
                {
                    'title': chunk['title'],
                    'snippet': chunk['content'][:150] + '...',
                    'relevance_score': chunk['score']
                }
                for chunk in context_chunks
            ]
        })
        
    except Exception as e:
        logger.error(f"Chat error: {traceback.format_exc()}")
        return jsonify({'error': 'Chat service temporarily unavailable'}), 500

@app.route('/api/upload', methods=['POST'])
def upload_document():
    """Upload and process documents"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get session ID to track recent uploads
        data = request.form.to_dict()
        session_id = data.get('session_id', 'default_session')
        
        # Get user ID if authenticated
        user_id = None
        try:
            user_id = get_jwt_identity()
        except:
            pass  # Anonymous upload allowed
        
        # Process the document
        doc_data = process_document(file)
        
        # Save document to database
        db = SessionLocal()
        try:
            document = Document(
                title=doc_data['filename'],
                filename=doc_data['filename'],
                content=doc_data['content'],
                file_type=doc_data['file_type'],
                file_size=doc_data['file_size'],
                user_id=user_id,
                processed=True
            )
            
            db.add(document)
            db.commit()
            
            # Create text chunks
            chunks = chunk_text(doc_data['content'])
            chunk_objects = []
            
            for i, chunk_content in enumerate(chunks):
                chunk = KnowledgeChunk(
                    document_id=document.id,
                    chunk_text=chunk_content,
                    chunk_index=i,
                    embedding_summary=chunk_content[:500]  # Simple summary for now
                )
                chunk_objects.append(chunk)
                
                # Add to in-memory knowledge base
                KNOWLEDGE_BASE[f"{document.id}_{i}"] = {
                    'title': document.title,
                    'content': chunk_content,
                    'document_type': document.file_type,
                    'document_id': document.id,
                    'chunk_id': i
                }
            
            db.add_all(chunk_objects)
            db.commit()
            
            # Track this as the most recent document for this session
            global SESSION_RECENT_DOCS
            SESSION_RECENT_DOCS[session_id] = {
                'document_id': document.id,
                'title': document.title,
                'filename': document.filename,
                'upload_time': datetime.utcnow()
            }
            
            logger.info(f"Document uploaded: {doc_data['filename']} ({len(chunks)} chunks) - Session: {session_id}")
            
            return jsonify({
                'message': f'Document {doc_data["filename"]} uploaded successfully',
                'document_id': document.id,
                'title': document.title,
                'chunks_generated': len(chunks),
                'file_size': doc_data['file_size'],
                'success': True
            })
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Upload error: {traceback.format_exc()}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/search', methods=['GET'])
def search():
    """Search knowledge base"""
    try:
        query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 10)), 50)
        
        if not query:
            return jsonify({'error': 'Query parameter q is required'}), 400
        
        results = search_knowledge_base(query, limit)
        
        return jsonify({
            'query': query,
            'results': results,
            'total_found': len(results)
        })
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'error': 'Search failed'}), 500

@app.route('/api/documents', methods=['GET'])
@jwt_required(optional=True)
def list_documents():
    """List all documents"""
    try:
        user_id = get_jwt_identity()
        
        db = SessionLocal()
        try:
            query = db.query(Document)
            if user_id:
                query = query.filter((Document.user_id == user_id) | (Document.user_id.is_(None)))
            else:
                query = query.filter(Document.user_id.is_(None))
            
            documents = query.order_by(Document.upload_date.desc()).all()
            
            return jsonify({
                'documents': [
                    {
                        'id': doc.id,
                        'title': doc.title,
                        'filename': doc.filename,
                        'file_type': doc.file_type,
                        'file_size': doc.file_size,
                        'upload_date': doc.upload_date.isoformat(),
                        'processed': doc.processed
                    }
                    for doc in documents
                ],
                'total': len(documents)
            })
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Document listing error: {e}")
        return jsonify({'error': 'Failed to fetch documents'}), 500

@app.route('/api/analytics', methods=['GET'])
@jwt_required(optional=True)
def analytics():
    """Basic analytics"""
    try:
        db = SessionLocal()
        try:
            # Get conversation count
            conversation_count = db.query(Conversation).count()
            
            # Get document count
            document_count = db.query(Document).count()
            
            # Get recent activity (last 24 hours)
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_conversations = db.query(Conversation).filter(
                Conversation.timestamp >= yesterday
            ).count()
            
            return jsonify({
                'total_conversations': conversation_count,
                'total_documents': document_count,
                'recent_conversations_24h': recent_conversations,
                'knowledge_base_size': len(KNOWLEDGE_BASE),
                'average_confidence': 0.8,  # TODO: Calculate from actual data
                'timestamp': datetime.utcnow().isoformat()
            })
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        return jsonify({'error': 'Analytics unavailable'}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Load knowledge base on startup
    load_knowledge_base()
    
    # Start server
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"🚀 Starting SAM Bot Production Server on http://localhost:{port}")
    logger.info(f"🤖 OpenAI Integration: {'✅ Enabled' if openai.api_key and openai.api_key != 'sk-your-actual-openai-api-key-here' else '⚠️  Not configured'}")
    logger.info(f"📚 Knowledge Base: {len(KNOWLEDGE_BASE)} chunks loaded")
    logger.info(f"🎯 Access the application at: http://localhost:{port}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
