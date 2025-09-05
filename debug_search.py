#!/usr/bin/env python3
"""
Debug script to test document search logic
"""

def should_search_documents(query):
    """Debug version of the should_search_documents function"""
    query_lower = query.strip().lower()
    print(f"Testing query: '{query}' -> '{query_lower}'")
    
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
            print(f"  -> SKIP: Found greeting phrase '{phrase}'")
            return False
    
    # Skip if query is just a greeting or short conversational word (after checking phrases)
    if len(query_lower) <= 3:
        print(f"  -> SKIP: Query too short ({len(query_lower)} chars)")
        return False
    
    # Skip for basic math expressions
    if any(char in query_lower for char in ['+', '-', '*', '/', '=']) and any(char.isdigit() for char in query_lower):
        print(f"  -> SKIP: Math expression detected")
        return False
    
    # Skip for basic questions that don't need documents (but allow document-related "what is" questions)
    basic_question_starters = ['how to', 'why', 'when', 'where', 'who', 'help me with', 'can you']
    if any(query_lower.startswith(starter) for starter in basic_question_starters) and 'document' not in query_lower and 'file' not in query_lower:
        print(f"  -> SKIP: Basic question starter found")
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
        'content of this', 'details of this'
    ]
    
    # Check for document-related phrases
    for phrase in document_phrases:
        if phrase in query_lower:
            print(f"  -> SEARCH: Found document phrase '{phrase}'")
            return True
    
    # Additional pattern matching for common document queries
    if ('what' in query_lower and 'this' in query_lower) or ('about' in query_lower and 'this' in query_lower):
        print(f"  -> SEARCH: Found 'what/about + this' pattern")
        return True
    
    if ('tell' in query_lower and 'about' in query_lower) or ('describe' in query_lower):
        print(f"  -> SEARCH: Found 'tell about' or 'describe' pattern")
        return True
    
    # Check for document keywords
    for keyword in document_keywords:
        if keyword in query_lower:
            print(f"  -> SEARCH: Found document keyword '{keyword}'")
            return True
    
    # Only search if query contains document-related keywords or is a substantial query
    if len(query_lower.split()) > 4:
        print(f"  -> SEARCH: Substantial query ({len(query_lower.split())} words)")
        return True
    
    print(f"  -> SKIP: No matching patterns found")
    return False

def test_queries():
    """Test various queries"""
    test_cases = [
        "hi",
        "hello",
        "what is this",
        "what is this about", 
        "what it is about this",
        "marks",
        "resume",
        "kapil-resume",
        "tell me about this document",
        "describe this",
        "5+5",
        "github link",
        "what are the skills"
    ]
    
    print("Testing document search logic:")
    print("=" * 50)
    
    for query in test_cases:
        result = should_search_documents(query)
        print(f"'{query}' -> {'SEARCH' if result else 'SKIP'}")
        print()

if __name__ == "__main__":
    test_queries()
