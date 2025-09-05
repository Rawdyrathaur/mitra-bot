#!/usr/bin/env python3
"""
Setup script for SAM Bot
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(command, description):
    """Run a shell command and handle errors"""
    print(f"📦 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e.stderr}")
        return None

def check_requirements():
    """Check if required tools are installed"""
    print("🔍 Checking requirements...")
    
    requirements = {
        'python': 'python --version',
        'pip': 'pip --version',
        'docker': 'docker --version',
        'docker-compose': 'docker-compose --version'
    }
    
    missing = []
    for tool, command in requirements.items():
        if not run_command(command, f"Checking {tool}"):
            missing.append(tool)
    
    if missing:
        print(f"❌ Missing required tools: {', '.join(missing)}")
        print("Please install the missing tools and try again.")
        return False
    
    print("✅ All requirements satisfied")
    return True

def setup_environment():
    """Set up the environment file"""
    print("🔧 Setting up environment...")
    
    env_file = Path('.env')
    env_example = Path('.env.example')
    
    if not env_file.exists():
        if env_example.exists():
            shutil.copy(env_example, env_file)
            print("✅ Created .env file from .env.example")
            print("📝 Please edit .env file with your actual configuration values")
        else:
            print("❌ .env.example file not found")
            return False
    else:
        print("✅ .env file already exists")
    
    return True

def setup_database():
    """Set up the database using Docker Compose"""
    print("🗄️  Setting up database...")
    
    # Start PostgreSQL and Redis
    if not run_command('docker-compose up -d postgres redis', 'Starting PostgreSQL and Redis'):
        return False
    
    # Wait for services to be ready
    import time
    print("⏳ Waiting for services to be ready...")
    time.sleep(10)
    
    return True

def install_dependencies():
    """Install Python dependencies"""
    print("📚 Installing Python dependencies...")
    
    # Create virtual environment if it doesn't exist
    if not Path('venv').exists():
        if not run_command('python -m venv venv', 'Creating virtual environment'):
            return False
    
    # Activate virtual environment and install dependencies
    if os.name == 'nt':  # Windows
        activate_cmd = 'venv\\Scripts\\activate'
    else:  # Unix/Linux/MacOS
        activate_cmd = 'source venv/bin/activate'
    
    install_cmd = f'{activate_cmd} && pip install -r requirements.txt'
    if not run_command(install_cmd, 'Installing dependencies'):
        return False
    
    return True

def run_tests():
    """Run basic tests to verify installation"""
    print("🧪 Running tests...")
    
    # Test API health endpoint
    if not run_command('python src/advanced_api.py &', 'Starting API server'):
        return False
    
    # Wait for server to start
    import time
    time.sleep(5)
    
    # Test health endpoint
    try:
        import requests
        response = requests.get('http://localhost:5000/api/health', timeout=10)
        if response.status_code == 200:
            print("✅ API health check passed")
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API health check failed: {e}")
        return False
    finally:
        # Stop the server
        run_command('pkill -f advanced_api.py', 'Stopping API server')
    
    return True

def main():
    """Main setup function"""
    print("🚀 Setting up SAM Bot...")
    print("=" * 50)
    
    steps = [
        ("Checking requirements", check_requirements),
        ("Setting up environment", setup_environment),
        ("Installing dependencies", install_dependencies),
        ("Setting up database", setup_database),
    ]
    
    for description, func in steps:
        if not func():
            print(f"\n❌ Setup failed at step: {description}")
            sys.exit(1)
        print()
    
    print("🎉 SAM Bot setup completed successfully!")
    print("\nNext steps:")
    print("1. Edit .env file with your API keys and configuration")
    print("2. Run: docker-compose up --build")
    print("3. Open http://localhost:5000 in your browser")
    print("\nFor development:")
    print("1. Activate virtual environment: source venv/bin/activate (Linux/Mac) or venv\\Scripts\\activate (Windows)")
    print("2. Run: python src/advanced_api.py")

if __name__ == "__main__":
    main()