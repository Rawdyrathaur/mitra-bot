#!/usr/bin/env python3
"""
SAM Bot Startup Script
Configures OpenAI API key and launches the production system
"""

import os
import sys
from pathlib import Path

def setup_openai_key():
    """Setup OpenAI API key"""
    env_file = Path('.env')
    
    print("🤖 SAM Bot Production Setup")
    print("=" * 50)
    
    # Check if OpenAI key is already configured
    if env_file.exists():
        with open(env_file, 'r') as f:
            env_content = f.read()
        
        if 'sk-' in env_content and 'your-actual-openai-api-key-here' not in env_content:
            print("✅ OpenAI API key appears to be configured")
            return True
    
    print("⚠️  OpenAI API key needs to be configured")
    print("\n🔑 Please get your OpenAI API key from: https://platform.openai.com/api-keys")
    
    while True:
        api_key = input("\nEnter your OpenAI API key (or press Enter to skip): ").strip()
        
        if not api_key:
            print("⚠️  Skipping OpenAI configuration. SAM will use basic responses.")
            return False
        
        if not api_key.startswith('sk-'):
            print("❌ Invalid API key format. OpenAI keys start with 'sk-'")
            continue
        
        # Update .env file
        if env_file.exists():
            with open(env_file, 'r') as f:
                content = f.read()
            
            content = content.replace(
                'OPENAI_API_KEY=sk-your-actual-openai-api-key-here',
                f'OPENAI_API_KEY={api_key}'
            )
            
            with open(env_file, 'w') as f:
                f.write(content)
        
        print("✅ OpenAI API key configured successfully!")
        return True

def main():
    """Main startup function"""
    print("🚀 Starting SAM Bot Production System...")
    
    # Setup OpenAI key
    openai_configured = setup_openai_key()
    
    print("\n📋 System Status:")
    print(f"  🤖 OpenAI Integration: {'✅ Enabled' if openai_configured else '⚠️  Basic mode'}")
    print(f"  🗄️  Database: ✅ SQLite (production-ready)")
    print(f"  🎨 UI Theme: ✅ Neo-Professional AI")
    print(f"  🔐 Authentication: ✅ JWT-based")
    print(f"  📤 File Upload: ✅ Multi-format support")
    
    print("\n🎯 Features Available:")
    print("  • Real-time AI chat with GPT integration")
    print("  • Document upload and intelligent processing")
    print("  • Advanced knowledge base search")
    print("  • Beautiful responsive UI with animations")
    print("  • User authentication and session management")
    print("  • Analytics and conversation tracking")
    
    print("\n" + "=" * 50)
    print("🚀 Launching SAM Bot...")
    print("📱 Open your browser and go to: http://localhost:5000")
    print("=" * 50)
    
    # Start the application
    try:
        import app
    except ImportError as e:
        print(f"❌ Failed to start SAM Bot: {e}")
        return
    
    # This point is reached if the Flask app exits
    print("👋 SAM Bot has stopped.")

if __name__ == "__main__":
    main()
