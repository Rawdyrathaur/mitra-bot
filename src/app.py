#!/usr/bin/env python3
"""
SAM Bot - A simple AI-powered chatbot
"""
import os
import logging
from typing import Optional
from database import DatabaseManager
from embeddings import EmbeddingProcessor
from models import ChatModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SAMBot:
    def __init__(self):
        self.db = DatabaseManager()
        self.embeddings = EmbeddingProcessor()
        self.chat_model = ChatModel()
        logger.info("SAM Bot initialized successfully")
    
    def process_message(self, message: str, user_id: Optional[str] = None) -> str:
        """Process a user message and return a response"""
        try:
            # Store message in database
            self.db.store_message(user_id, message, "user")
            
            # Generate embedding for semantic search
            embedding = self.embeddings.get_embedding(message)
            
            # Get response from chat model
            response = self.chat_model.generate_response(message, embedding)
            
            # Store response
            self.db.store_message(user_id, response, "bot")
            
            return response
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return "I'm sorry, I encountered an error processing your message."
    
    def run(self):
        """Run the bot in interactive mode"""
        print("SAM Bot is ready! Type 'quit' to exit.")
        
        while True:
            try:
                user_input = input("\nYou: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                response = self.process_message(user_input)
                print(f"SAM: {response}")
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                print("An error occurred. Please try again.")

if __name__ == "__main__":
    bot = SAMBot()
    bot.run()