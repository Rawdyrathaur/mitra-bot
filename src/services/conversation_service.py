"""
Advanced conversation service for SAM Bot
Integrates OpenAI GPT with context management, confidence scoring, and multi-turn conversations
"""
import os
import logging
import json
import asyncio
import time
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime

# OpenAI integration
try:
    import openai
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Text processing
import tiktoken
import re

from database_manager import DatabaseManager
from services.knowledge_service import KnowledgeSearchEngine

logger = logging.getLogger(__name__)

class ConversationEngine:
    """Advanced AI conversation engine with RAG capabilities"""
    
    def __init__(self, db_manager: DatabaseManager, knowledge_engine: KnowledgeSearchEngine):
        self.db = db_manager
        self.knowledge = knowledge_engine
        
        # Initialize OpenAI
        if OPENAI_AVAILABLE:
            self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            self.model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
        else:
            self.client = None
            self.model = None
            logger.error("OpenAI not available - set OPENAI_API_KEY environment variable")
        
        # Conversation settings
        self.max_context_tokens = int(os.getenv('MAX_CONTEXT_TOKENS', '3000'))
        self.max_response_tokens = int(os.getenv('MAX_RESPONSE_TOKENS', '500'))
        self.temperature = float(os.getenv('OPENAI_TEMPERATURE', '0.7'))
        self.confidence_threshold = float(os.getenv('CONFIDENCE_THRESHOLD', '0.6'))
        
        # Initialize tokenizer for token counting
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.model)
        except:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")  # Fallback
        
        # Conversation templates
        self.system_prompt = self._load_system_prompt()
        self.fallback_responses = self._load_fallback_responses()
        
        logger.info("Conversation engine initialized")
    
    def _load_system_prompt(self) -> str:
        """Load the system prompt for the AI assistant"""
        return """You are SAM (Search Augmented Model), an intelligent customer support assistant. 
        
Your primary role is to help users by providing accurate, helpful responses based on the company's documentation and knowledge base.

Key guidelines:
1. Always use the provided context from the knowledge base when available
2. If you don't know something, admit it and suggest ways the user can get help
3. Be conversational but professional
4. Provide specific, actionable information when possible
5. If the context doesn't contain enough information, say so clearly
6. For complex technical issues, break down your response into clear steps
7. Always cite which documents or sections your information comes from when relevant
8. If asked about something outside the knowledge base, politely redirect to supported topics

Remember: You are representing the company, so maintain a helpful, professional tone while being genuinely useful to users."""
    
    def _load_fallback_responses(self) -> List[str]:
        """Load fallback responses for when AI is unavailable"""
        return [
            "I apologize, but I'm experiencing technical difficulties right now. Please try again in a moment or contact human support for immediate assistance.",
            "I'm having trouble processing your request at the moment. Could you please rephrase your question or contact our support team directly?",
            "My AI capabilities are temporarily unavailable. For immediate help, please reach out to our human support team."
        ]
    
    async def generate_response(self, user_message: str, session_id: str, 
                              user_id: str = None, context_override: Dict = None) -> Dict:
        """Generate AI response with RAG context and conversation history"""
        try:
            start_time = time.time()
            
            # Search knowledge base for relevant context
            if not context_override:
                search_results = await self.knowledge.semantic_search(
                    user_message,
                    limit=5,
                    include_context=True
                )
                relevant_context = search_results.get('results', [])
            else:
                relevant_context = context_override.get('results', [])
            
            # Get conversation history
            conversation_history = self.db.conversation_memory.get_conversation_context(
                session_id, context_window=5
            )
            
            # Build the conversation context
            messages = self._build_conversation_context(
                user_message, relevant_context, conversation_history
            )
            
            # Generate AI response
            ai_response, confidence_score = await self._call_openai(messages)
            
            # Calculate response metrics
            response_time = int((time.time() - start_time) * 1000)
            
            # Determine if human handoff is needed
            needs_handoff, handoff_reason = self._should_handoff(
                user_message, ai_response, confidence_score, relevant_context
            )
            
            # Store conversation
            conv_id = self.db.store_conversation(
                session_id=session_id,
                user_id=user_id or 'anonymous',
                question=user_message,
                answer=ai_response,
                context_chunks=[chunk['chunk_id'] for chunk in relevant_context],
                confidence_score=confidence_score,
                response_time_ms=response_time
            )
            
            # Log analytics
            self._log_conversation_analytics(
                user_message, ai_response, confidence_score, 
                len(relevant_context), response_time, needs_handoff
            )
            
            return {
                'response': ai_response,
                'confidence_score': confidence_score,
                'sources_used': len(relevant_context),
                'context_chunks': [
                    {
                        'document_title': chunk['document_title'],
                        'similarity': chunk.get('similarity', 0),
                        'snippet': chunk['content'][:200] + "..." if len(chunk['content']) > 200 else chunk['content']
                    }
                    for chunk in relevant_context[:3]  # Show top 3 sources
                ],
                'requires_human_handoff': needs_handoff,
                'handoff_reason': handoff_reason,
                'conversation_id': conv_id,
                'response_time_ms': response_time,
                'session_id': session_id
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return self._handle_error_response(user_message, session_id, str(e))
    
    def _build_conversation_context(self, user_message: str, relevant_context: List[Dict], 
                                  conversation_history: List[Dict]) -> List[Dict]:
        """Build conversation context for OpenAI API"""
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Add relevant context from knowledge base
        if relevant_context:
            context_text = self._format_context(relevant_context)
            context_message = f"""Based on the following information from our knowledge base, please answer the user's question:

{context_text}

Please use this information to provide a helpful, accurate response. If the context doesn't fully answer the question, mention what additional information might be needed."""
            
            messages.append({"role": "system", "content": context_message})
        
        # Add conversation history (recent messages)
        for msg in conversation_history[-6:]:  # Last 3 exchanges (6 messages)
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Trim context if too long
        messages = self._trim_context(messages)
        
        return messages
    
    def _format_context(self, context_chunks: List[Dict]) -> str:
        """Format knowledge base context for the AI"""
        formatted_contexts = []
        
        for i, chunk in enumerate(context_chunks):
            source_info = f"Source {i+1}: {chunk['document_title']}"
            if chunk.get('category'):
                source_info += f" (Category: {chunk['category']})"
            
            formatted_contexts.append(f"{source_info}\n{chunk['content']}\n")
        
        return "\n---\n".join(formatted_contexts)
    
    def _trim_context(self, messages: List[Dict]) -> List[Dict]:
        """Trim conversation context to fit within token limits"""
        try:
            total_tokens = sum(
                len(self.tokenizer.encode(msg["content"])) 
                for msg in messages
            )
            
            if total_tokens <= self.max_context_tokens:
                return messages
            
            # Keep system message and current user message
            trimmed = [messages[0]]  # System prompt
            user_message = messages[-1]  # Current user message
            
            # Add as many recent messages as possible
            for msg in reversed(messages[1:-1]):  # Skip system and current user
                msg_tokens = len(self.tokenizer.encode(msg["content"]))
                if total_tokens - msg_tokens > self.max_context_tokens:
                    total_tokens -= msg_tokens
                else:
                    trimmed.insert(-1, msg)
            
            trimmed.append(user_message)
            return trimmed
            
        except Exception as e:
            logger.error(f"Error trimming context: {e}")
            # Fallback: return just system prompt and user message
            return [messages[0], messages[-1]]
    
    async def _call_openai(self, messages: List[Dict]) -> Tuple[str, float]:
        """Call OpenAI API and return response with confidence score"""
        try:
            if not self.client:
                raise Exception("OpenAI client not available")
            
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=messages,
                max_tokens=self.max_response_tokens,
                temperature=self.temperature,
                top_p=1,
                presence_penalty=0.1,
                frequency_penalty=0.1
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # Calculate confidence score based on various factors
            confidence_score = self._calculate_confidence_score(
                response, messages, ai_response
            )
            
            return ai_response, confidence_score
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            # Use fallback response
            import random
            fallback_response = random.choice(self.fallback_responses)
            return fallback_response, 0.1  # Very low confidence for fallback
    
    def _calculate_confidence_score(self, openai_response, messages: List[Dict], 
                                  ai_response: str) -> float:
        """Calculate confidence score for the AI response"""
        try:
            base_confidence = 0.7  # Base confidence
            
            # Factor 1: Response length (reasonable responses have moderate length)
            response_length = len(ai_response.split())
            if 10 <= response_length <= 200:
                length_bonus = 0.1
            elif 5 <= response_length <= 300:
                length_bonus = 0.05
            else:
                length_bonus = -0.1
            
            # Factor 2: Presence of uncertainty phrases
            uncertainty_phrases = [
                "i'm not sure", "i don't know", "might be", "could be",
                "perhaps", "i think", "probably", "i'm not certain"
            ]
            uncertainty_penalty = sum(
                0.05 for phrase in uncertainty_phrases 
                if phrase in ai_response.lower()
            )
            
            # Factor 3: Knowledge base context usage
            context_bonus = 0.2 if len(messages) > 2 else 0  # Has context
            
            # Factor 4: Specific information indicators
            specific_indicators = [
                "step 1", "first", "second", "follow these", "here's how",
                "documentation", "according to", "based on"
            ]
            specificity_bonus = min(0.1, sum(
                0.02 for indicator in specific_indicators
                if indicator in ai_response.lower()
            ))
            
            # Calculate final confidence
            confidence = max(0.0, min(1.0, 
                base_confidence + length_bonus - uncertainty_penalty + 
                context_bonus + specificity_bonus
            ))
            
            return round(confidence, 2)
            
        except Exception as e:
            logger.error(f"Error calculating confidence score: {e}")
            return 0.5  # Default moderate confidence
    
    def _should_handoff(self, user_message: str, ai_response: str, 
                       confidence_score: float, context: List[Dict]) -> Tuple[bool, Optional[str]]:
        """Determine if human handoff is needed"""
        try:
            # Low confidence responses
            if confidence_score < self.confidence_threshold:
                return True, f"Low confidence score: {confidence_score}"
            
            # No relevant context found
            if not context:
                return True, "No relevant information found in knowledge base"
            
            # Explicit handoff requests
            handoff_keywords = [
                "speak to human", "talk to person", "human agent",
                "escalate", "complaint", "cancel", "refund", "billing",
                "legal", "urgent", "emergency"
            ]
            
            if any(keyword in user_message.lower() for keyword in handoff_keywords):
                return True, "User requested human assistance"
            
            # Complex technical issues (heuristic)
            complexity_indicators = [
                "doesn't work", "still broken", "tried everything",
                "error code", "system down", "can't access"
            ]
            
            if (len([ind for ind in complexity_indicators if ind in user_message.lower()]) >= 2 and
                confidence_score < 0.8):
                return True, "Complex technical issue detected"
            
            return False, None
            
        except Exception as e:
            logger.error(f"Error determining handoff: {e}")
            return False, None
    
    def _log_conversation_analytics(self, question: str, answer: str, 
                                  confidence: float, context_count: int,
                                  response_time: int, needs_handoff: bool):
        """Log conversation analytics"""
        try:
            with self.db.get_session() as session:
                self.db._log_analytics(
                    session,
                    'ai_conversation',
                    metadata={
                        'question_length': len(question),
                        'answer_length': len(answer),
                        'confidence_score': confidence,
                        'context_chunks_used': context_count,
                        'response_time_ms': response_time,
                        'requires_handoff': needs_handoff,
                        'model_used': self.model
                    }
                )
        except Exception as e:
            logger.error(f"Error logging conversation analytics: {e}")
    
    def _handle_error_response(self, user_message: str, session_id: str, 
                             error: str) -> Dict:
        """Handle errors and provide fallback response"""
        import random
        fallback_response = random.choice(self.fallback_responses)
        
        # Store error conversation
        try:
            self.db.store_conversation(
                session_id=session_id,
                user_id='anonymous',
                question=user_message,
                answer=fallback_response,
                confidence_score=0.1,
                response_time_ms=0
            )
        except:
            pass  # Don't let storage errors prevent response
        
        return {
            'response': fallback_response,
            'confidence_score': 0.1,
            'sources_used': 0,
            'context_chunks': [],
            'requires_human_handoff': True,
            'handoff_reason': f"System error: {error}",
            'conversation_id': None,
            'response_time_ms': 0,
            'session_id': session_id,
            'error': True
        }
    
    async def continue_conversation(self, user_message: str, session_id: str,
                                  conversation_id: str = None, user_id: str = None) -> Dict:
        """Continue an existing conversation with full context"""
        try:
            # This is essentially the same as generate_response but with explicit session handling
            return await self.generate_response(user_message, session_id, user_id)
            
        except Exception as e:
            logger.error(f"Error continuing conversation: {e}")
            return self._handle_error_response(user_message, session_id, str(e))
    
    def rate_response(self, conversation_id: str, rating: int, comment: str = None) -> bool:
        """Rate a conversation response"""
        try:
            if rating < 1 or rating > 5:
                return False
            
            self.db.update_conversation_feedback(conversation_id, rating, comment)
            
            # Log feedback analytics
            with self.db.get_session() as session:
                self.db._log_analytics(
                    session,
                    'response_feedback',
                    metadata={
                        'conversation_id': conversation_id,
                        'rating': rating,
                        'has_comment': bool(comment)
                    }
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error rating response: {e}")
            return False
    
    def get_conversation_suggestions(self, session_id: str) -> List[str]:
        """Get suggested follow-up questions based on conversation history"""
        try:
            history = self.db.conversation_memory.get_conversation_history(session_id, limit=3)
            
            if not history:
                return [
                    "How can I get started?",
                    "What are your main features?",
                    "Where can I find documentation?",
                    "How do I contact support?"
                ]
            
            # Analyze recent conversation to suggest relevant follow-ups
            last_response = history[0] if history else None
            
            suggestions = []
            
            # Generic helpful follow-ups
            base_suggestions = [
                "Can you provide more details about this?",
                "What are the next steps?",
                "Are there any prerequisites?",
                "Where can I find more information?",
                "What if I encounter problems?"
            ]
            
            # Context-specific suggestions based on keywords
            if last_response:
                answer_lower = last_response.get('answer', '').lower()
                
                if 'setup' in answer_lower or 'install' in answer_lower:
                    suggestions.extend([
                        "What are the system requirements?",
                        "How do I verify the installation?",
                        "What if the setup fails?"
                    ])
                
                elif 'error' in answer_lower or 'problem' in answer_lower:
                    suggestions.extend([
                        "How can I troubleshoot this?",
                        "What logs should I check?",
                        "Who should I contact for help?"
                    ])
                
                elif 'configure' in answer_lower or 'settings' in answer_lower:
                    suggestions.extend([
                        "What are the recommended settings?",
                        "How do I backup my configuration?",
                        "Can I customize this further?"
                    ])
            
            # Combine and limit suggestions
            all_suggestions = suggestions + base_suggestions
            return all_suggestions[:5]  # Return up to 5 suggestions
            
        except Exception as e:
            logger.error(f"Error getting conversation suggestions: {e}")
            return ["How can I help you further?"]
    
    def export_conversation(self, session_id: str, format: str = 'json') -> Optional[str]:
        """Export conversation history in various formats"""
        try:
            history = self.db.conversation_memory.get_conversation_history(session_id, limit=50)
            
            if format.lower() == 'json':
                return json.dumps(history, indent=2, default=str)
            
            elif format.lower() == 'txt':
                lines = []
                for item in reversed(history):  # Chronological order
                    lines.append(f"User: {item['question']}")
                    lines.append(f"SAM: {item['answer']}")
                    lines.append(f"Time: {item['timestamp']}")
                    lines.append("---")
                return "\n".join(lines)
            
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error exporting conversation: {e}")
            return None
    
    def clear_conversation(self, session_id: str) -> bool:
        """Clear conversation history for a session"""
        try:
            self.db.conversation_memory.clear_conversation(session_id)
            
            # Log analytics
            with self.db.get_session() as session:
                self.db._log_analytics(
                    session,
                    'conversation_cleared',
                    metadata={'session_id': session_id}
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error clearing conversation: {e}")
            return False
    
    def get_conversation_analytics(self, days: int = 7) -> Dict:
        """Get conversation analytics for the specified period"""
        try:
            analytics = self.db.get_analytics_summary(days)
            
            # Add conversation-specific metrics
            with self.db.get_session() as session:
                from datetime import timedelta
                from sqlalchemy import func
                from models.database_models import Conversation
                
                since = datetime.utcnow() - timedelta(days=days)
                
                # Average confidence score
                avg_confidence = session.query(func.avg(Conversation.confidence_score)).filter(
                    Conversation.timestamp >= since,
                    Conversation.confidence_score.isnot(None)
                ).scalar()
                
                # Handoff rate
                total_convs = session.query(func.count(Conversation.id)).filter(
                    Conversation.timestamp >= since
                ).scalar()
                
                handoff_convs = session.query(func.count(Conversation.id)).filter(
                    Conversation.timestamp >= since,
                    Conversation.requires_human_handoff == True
                ).scalar()
                
                handoff_rate = (handoff_convs / total_convs * 100) if total_convs else 0
                
                # Satisfaction scores
                avg_rating = session.query(func.avg(Conversation.feedback_rating)).filter(
                    Conversation.timestamp >= since,
                    Conversation.feedback_rating.isnot(None)
                ).scalar()
                
                analytics.update({
                    'avg_confidence_score': float(avg_confidence) if avg_confidence else None,
                    'total_conversations': total_convs or 0,
                    'handoff_rate_percent': round(handoff_rate, 2),
                    'avg_satisfaction_rating': float(avg_rating) if avg_rating else None
                })
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error getting conversation analytics: {e}")
            return {}

class ConversationTemplates:
    """Manage conversation templates and responses"""
    
    def __init__(self):
        self.templates = {
            'greeting': [
                "Hello! I'm SAM, your AI assistant. How can I help you today?",
                "Hi there! I'm here to help you find the information you need. What can I assist you with?",
                "Welcome! I'm SAM, and I'm ready to help answer your questions. What would you like to know?"
            ],
            'clarification': [
                "Could you provide a bit more detail about what you're looking for?",
                "I want to make sure I understand correctly. Could you rephrase your question?",
                "Can you give me some more context about your issue?"
            ],
            'no_results': [
                "I couldn't find specific information about that in our knowledge base. Let me connect you with a human agent who can better assist you.",
                "I don't have enough information to answer that question accurately. Would you like to speak with one of our support specialists?",
                "That's outside my current knowledge. I'll transfer you to a human agent who can help."
            ],
            'closing': [
                "Is there anything else I can help you with today?",
                "I hope that was helpful! Do you have any other questions?",
                "Was I able to answer your question? Feel free to ask if you need anything else."
            ]
        }
    
    def get_template(self, template_type: str, context: Dict = None) -> str:
        """Get a template response"""
        import random
        
        templates = self.templates.get(template_type, [])
        if not templates:
            return "I'm here to help. What can I do for you?"
        
        return random.choice(templates)
    
    def customize_response(self, base_response: str, user_name: str = None, 
                         company_name: str = None) -> str:
        """Customize response with user/company information"""
        if user_name:
            base_response = base_response.replace("Hello!", f"Hello {user_name}!")
            base_response = base_response.replace("Hi there!", f"Hi {user_name}!")
        
        if company_name:
            base_response = base_response.replace("our knowledge base", f"{company_name}'s knowledge base")
            base_response = base_response.replace("our support", f"{company_name} support")
        
        return base_response
