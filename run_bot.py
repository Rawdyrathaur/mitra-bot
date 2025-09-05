#!/usr/bin/env python3
"""
Safe launcher for SAM Bot with proper input handling
"""
import sys
import os

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from app import SAMBot

def main():
    """Run SAM Bot with safe input handling"""
    print("SAM Bot is starting...")
    bot = SAMBot()
    print("SAM Bot is ready! Type 'quit' to exit.\n")
    
    while True:
        try:
            # Use a more robust input method
            print("You: ", end="", flush=True)
            user_input = input().strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
                print("Goodbye!")
                break
            
            if not user_input:
                continue
            
            response = bot.process_message(user_input)
            print(f"SAM: {response}\n")
            
        except EOFError:
            print("\nGoodbye!")
            break
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            print("Please try again.\n")

if __name__ == "__main__":
    main()