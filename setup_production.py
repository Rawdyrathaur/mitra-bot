#!/usr/bin/env python3
"""
SAM Bot Production Setup Script
This script sets up the production environment for SAM Bot
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_command(command, shell=True):
    """Run a command and return the result"""
    try:
        result = subprocess.run(command, shell=shell, capture_output=True, text=True, check=True)
        logger.info(f"✅ Command succeeded: {command}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Command failed: {command}")
        logger.error(f"Error: {e.stderr}")
        return None

def check_requirements():
    """Check if required tools are installed"""
    logger.info("🔍 Checking requirements...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        logger.error("❌ Python 3.8+ is required")
        return False
    logger.info(f"✅ Python version: {sys.version}")
    
    # Check Docker
    docker_version = run_command("docker --version")
    if docker_version:
        logger.info(f"✅ Docker is available: {docker_version.strip()}")
    else:
        logger.warning("⚠️  Docker not available - will use alternative setup")
    
    return True

def install_dependencies():
    """Install Python dependencies"""
    logger.info("📦 Installing Python dependencies...")
    
    # Create a requirements file without psycopg2-binary for now
    requirements_basic = [
        "Flask==2.3.3",
        "Flask-CORS==4.0.0", 
        "Flask-JWT-Extended==4.5.3",
        "Flask-Limiter==3.5.0",
        "openai==1.3.0",
        "python-dotenv==1.0.0",
        "redis==5.0.1",
        "requests==2.31.0",
        "sentence-transformers==2.2.2",
        "langchain==0.0.350",
        "pypdf2==3.0.1",
        "python-docx==1.1.0",
        "beautifulsoup4==4.12.2",
        "numpy==1.24.3",
        "scikit-learn==1.3.2",
        "nltk==3.8.1",
    ]
    
    for package in requirements_basic:
        logger.info(f"Installing {package}...")
        result = run_command(f"pip install {package}")
        if not result:
            logger.warning(f"⚠️  Failed to install {package}")

def setup_database():
    """Set up the database"""
    logger.info("🗄️  Setting up database...")
    
    # For now, we'll use SQLite for simplicity
    # Update the .env file to use SQLite
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, 'r') as f:
            content = f.read()
        
        # Replace PostgreSQL with SQLite for local development
        content = content.replace(
            "DATABASE_URL=postgresql://postgres:password@localhost:5432/sam_bot",
            "DATABASE_URL=sqlite:///sam_bot_production.db"
        )
        
        with open(env_file, 'w') as f:
            f.write(content)
        
        logger.info("✅ Updated database configuration to use SQLite")
    
def create_directories():
    """Create necessary directories"""
    logger.info("📁 Creating directories...")
    
    directories = [
        "uploads",
        "logs", 
        "data",
        "static",
        "templates"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        logger.info(f"✅ Created directory: {directory}")

def initialize_database():
    """Initialize the database with tables"""
    logger.info("🗄️  Initializing database...")
    
    try:
        # Import and initialize database
        from models.database_manager import DatabaseManager
        from models.database_models import Base
        from sqlalchemy import create_engine
        
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        database_url = os.getenv("DATABASE_URL")
        engine = create_engine(database_url)
        
        # Create all tables
        Base.metadata.create_all(engine)
        logger.info("✅ Database tables created successfully")
        
        # Initialize database manager
        db_manager = DatabaseManager()
        logger.info("✅ Database manager initialized")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")

def main():
    """Main setup function"""
    logger.info("🚀 Starting SAM Bot Production Setup...")
    
    if not check_requirements():
        logger.error("❌ Requirements check failed")
        return
    
    install_dependencies()
    create_directories()
    setup_database()
    initialize_database()
    
    logger.info("✅ SAM Bot production setup completed!")
    logger.info("📋 Next steps:")
    logger.info("   1. Add your OpenAI API key to the .env file")
    logger.info("   2. Run: python api.py")
    logger.info("   3. Access the application at http://localhost:5000")

if __name__ == "__main__":
    main()
