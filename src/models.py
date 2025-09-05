"""
Chat model for SAM Bot with OpenAI integration
"""
import logging
import random
import os
from typing import Optional
import openai

logger = logging.getLogger(__name__)

class ChatModel:
    def __init__(self):
        """Initialize the chat model with OpenAI integration"""
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if self.openai_api_key:
            openai.api_key = self.openai_api_key
            logger.info("OpenAI integration enabled")
        else:
            logger.warning("OpenAI API key not found, using fallback responses")
        
        self.responses = {
            "greeting": [
                "Hello! How can I help you today?",
                "Hi there! What can I do for you?",
                "Hello! I'm SAM, your assistant. How may I assist you?"
            ],
            "farewell": [
                "Goodbye! Have a great day!",
                "See you later!",
                "Take care!"
            ],
            "default": [
                "That's interesting! Can you tell me more?",
                "I understand. What would you like to know?",
                "Thanks for sharing that with me.",
                "I'm here to help. What else can I do for you?",
                "That's a good question. Let me think about that."
            ],
            "help": [
                "I'm SAM, your AI assistant. I can chat with you and help answer questions!",
                "I'm here to help! You can ask me questions or just have a conversation.",
                "I'm SAM Bot! I can assist you with various topics and have conversations."
            ]
        }
        logger.info("Chat model initialized")
    
    def classify_intent(self, message: str) -> str:
        """Classify the intent of a message"""
        message_lower = message.lower()
        
        greetings = ["hello", "hi", "hey", "good morning", "good afternoon"]
        farewells = ["bye", "goodbye", "see you", "farewell"]
        help_keywords = ["help", "what can you do", "who are you", "what are you"]
        
        if any(greeting in message_lower for greeting in greetings):
            return "greeting"
        elif any(farewell in message_lower for farewell in farewells):
            return "farewell"
        elif any(help_word in message_lower for help_word in help_keywords):
            return "help"
        else:
            return "default"
    
    def generate_response(self, message: str, context: Optional[list] = None) -> str:
        """Generate a response to the user message using OpenAI and RAG context"""
        try:
            intent = self.classify_intent(message)
            
            # Try OpenAI first if available and we have context or it's a question
            if (self.openai_api_key and context and len(context) > 0) or self._is_question(message):
                openai_response = self.generate_openai_response(message, context)
                if openai_response:
                    return openai_response
            
            # If we have relevant context, use it to generate a more informed response
            if context and len(context) > 0:
                context_response = self.generate_context_aware_response(message, context, intent)
                if context_response:
                    return context_response
            
            # Fallback to intent-based responses
            if intent in self.responses:
                response = random.choice(self.responses[intent])
            else:
                response = random.choice(self.responses["default"])
            
            logger.info(f"Generated response for intent: {intent}")
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I'm sorry, I'm having trouble processing that right now."
    
    def generate_openai_response(self, question: str, context: Optional[list] = None) -> Optional[str]:
        """Generate answer using OpenAI with context"""
        try:
            if not self.openai_api_key:
                return None
            
            # Build context string
            context_str = ""
            if context and len(context) > 0:
                context_str = "\n".join(context[:3])  # Use top 3 contexts
                context_str = f"Context information:\n{context_str}\n\n"
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are SAM, a helpful support assistant. Use the provided context to answer questions accurately. If the context doesn't contain relevant information, say so and provide a general helpful response."
                    },
                    {
                        "role": "user", 
                        "content": f"{context_str}Question: {question}"
                    }
                ],
                max_tokens=300,
                temperature=0.7
            )
            
            answer = response.choices[0].message.content.strip()
            logger.info("Generated OpenAI response")
            return answer
            
        except Exception as e:
            logger.error(f"Error generating OpenAI response: {e}")
            return None
    
    def generate_context_aware_response(self, message: str, context: list, intent: str) -> str:
        """Generate response using retrieved context"""
        try:
            # Simple context-aware response generation
            if intent == "help" or self._is_question(message):
                # Question-answering mode
                context_info = "\n".join(context[:2])  # Use top 2 contexts
                return f"Based on the available information: {context_info[:300]}..."
            
            elif intent == "greeting":
                return random.choice(self.responses["greeting"]) + " I have access to knowledge that might help you."
            
            elif len(context) > 0:
                # General context-aware response
                relevant_info = context[0][:200]  # First 200 chars of most relevant context
                return f"I found some relevant information: {relevant_info}... Would you like me to elaborate?"
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating context-aware response: {e}")
            return None
    
    def _is_question(self, message: str) -> bool:
        """Check if message is a question"""
        question_words = ["what", "how", "why", "when", "where", "who", "which", "can", "could", "would", "should"]
        message_lower = message.lower()
        return any(word in message_lower for word in question_words) or message.endswith('?')
    
    def add_custom_response(self, intent: str, response: str):
        """Add a custom response for an intent"""
        if intent not in self.responses:
            self.responses[intent] = []
        self.responses[intent].append(response)
        logger.info(f"Added custom response for intent: {intent}")