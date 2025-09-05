# SAM Bot - Advanced RAG-Based AI Assistant

A production-ready Flask-based AI chatbot with advanced Retrieval-Augmented Generation (RAG) capabilities, PostgreSQL database, Redis caching, and OpenAI integration.

## 🚀 Features

- **Advanced RAG**: Retrieval-Augmented Generation with semantic search
- **OpenAI Integration**: GPT-3.5-turbo for intelligent responses
- **PostgreSQL Database**: Production-ready data storage
- **Redis Caching**: Fast conversation memory and session management
- **Document Processing**: Support for PDF, DOCX, TXT, and MD files
- **Vector Embeddings**: Sentence-transformers for semantic similarity
- **REST API**: Comprehensive API with multiple endpoints
- **Web Interface**: Modern, responsive chat interface
- **Docker Support**: Full containerization with Docker Compose
- **Kubernetes Ready**: Production deployment configurations
- **CI/CD Pipeline**: Jenkins pipeline for automated deployment

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │   Flask API     │    │   PostgreSQL    │
│   (HTML/JS/CSS) │◄──►│   (Python)      │◄──►│   Database      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Redis Cache   │    │   OpenAI API    │
                       │   (Memory)      │◄──►│   (GPT-3.5)     │
                       └─────────────────┘    └─────────────────┘
                                │
                       ┌─────────────────────────────────────────┐
                       │        Document Processor              │
                       │   • LangChain • SentenceTransformers   │
                       │   • PDF/DOCX • Vector Embeddings       │
                       └─────────────────────────────────────────┘
```

## 📦 Quick Start

### Prerequisites
- Python 3.9+
- Docker & Docker Compose
- Git

### Method 1: Automated Setup
```bash
# Clone the repository
git clone <repository-url>
cd sam-bot

# Run the setup script
python setup.py

# Start all services
docker-compose up --build
```

### Method 2: Manual Setup
```bash
# 1. Environment setup
cp .env.example .env
# Edit .env with your OpenAI API key

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start services
docker-compose up -d postgres redis

# 4. Run the application
python src/advanced_api.py
```

### Method 3: Docker Only
```bash
# Start everything with Docker
docker-compose up --build

# Access the application
open http://localhost:5000
```

## 🔧 Configuration

### Environment Variables
```bash
# Database Configuration
DATABASE_URL=postgresql://sam_user:sam_password@postgres:5432/sam_db

# Redis Configuration  
REDIS_URL=redis://redis:6379/0

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Flask Configuration
FLASK_ENV=production
PORT=5000
```

## 📚 API Documentation

### Health Check
```bash
GET /api/health
```
Returns system health status including database, Redis, and OpenAI connectivity.

### Chat Endpoint
```bash
POST /api/chat
{
  "message": "How does RAG work?",
  "user_id": "user123",
  "session_id": "session456"
}
```

### Document Upload
```bash
# File upload
POST /api/upload
Content-Type: multipart/form-data
- file: [PDF/DOCX/TXT file]

# Text content upload
POST /api/upload
{
  "title": "Document Title",
  "content": "Document content..."
}
```

### Knowledge Base
```bash
GET /api/knowledge
```

### Conversation History
```bash
GET /api/conversations/{user_id}?session_id={session_id}&limit=10
```

### Clear Session
```bash
DELETE /api/sessions/{session_id}/clear
```

## 🗂️ Project Structure

```
sam-bot/
├── src/
│   ├── advanced_api.py          # Main Flask application
│   ├── document_processor.py    # Document processing & embeddings
│   ├── models/
│   │   ├── database_models.py   # SQLAlchemy models
│   │   └── chat_model.py        # OpenAI chat integration
│   ├── api.py                   # Original API (legacy)
│   └── ...
├── templates/
│   └── index.html               # Web interface
├── deployment/
│   ├── sam-deployment.yaml      # Kubernetes deployment
│   └── task-definition.json     # AWS ECS task definition
├── docker-compose.yml           # Docker Compose configuration
├── Dockerfile                   # Docker image definition
├── Jenkinsfile                  # CI/CD pipeline
├── requirements.txt             # Python dependencies
├── setup.py                     # Automated setup script
└── README.md                    # This file
```

## 🐳 Docker Deployment

### Local Development
```bash
# Start all services
docker-compose up --build

# View logs
docker-compose logs -f sam-bot

# Stop services
docker-compose down
```

### Production Build
```bash
# Build production image
docker build -t sam-bot:production .

# Run with custom configuration
docker run -d \
  -p 5000:5000 \
  -e DATABASE_URL="your_db_url" \
  -e REDIS_URL="your_redis_url" \
  -e OPENAI_API_KEY="your_key" \
  sam-bot:production
```

## ☸️ Kubernetes Deployment

```bash
# Apply Kubernetes configurations
kubectl apply -f deployment/sam-deployment.yaml

# Check deployment status
kubectl get pods -l app=sam-bot

# Get service URL
kubectl get service sam-bot-service
```

## 🚀 AWS ECS Deployment

```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://deployment/task-definition.json

# Create or update service
aws ecs create-service \
  --cluster sam-bot-cluster \
  --service-name sam-bot-service \
  --task-definition sam-bot:1 \
  --desired-count 2
```

## 🧪 Testing

### API Testing
```bash
# Health check
curl http://localhost:5000/api/health

# Chat test
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello SAM!", "user_id": "test-user"}'

# Upload test
curl -X POST http://localhost:5000/api/upload \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Doc", "content": "This is test content."}'
```

### Automated Testing
```bash
# Run tests (when available)
python -m pytest tests/

# Load testing
# Use tools like Apache Bench, wrk, or Locust
```

## 📈 Monitoring & Logging

### Health Monitoring
- Health endpoint: `/api/health`
- Docker health checks included
- Kubernetes liveness/readiness probes configured

### Logging
- Structured logging to stdout
- Docker log aggregation
- CloudWatch integration for AWS deployments

## 🔒 Security

### API Security
- Input validation on all endpoints
- File upload restrictions
- Error handling without information leakage

### Infrastructure Security
- Non-root Docker container
- Secrets management via environment variables
- Network isolation in Docker Compose

## 🚦 CI/CD Pipeline

The Jenkins pipeline includes:
1. **Build**: Docker image creation
2. **Test**: Automated testing (when available)
3. **Security Scan**: Container vulnerability scanning
4. **Deploy**: Automated deployment to ECS/Kubernetes
5. **Notification**: Slack integration for deployment status

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Commit changes: `git commit -am 'Add new feature'`
4. Push to branch: `git push origin feature/new-feature`
5. Submit a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔧 Troubleshooting

### Common Issues

**Database Connection Failed**
```bash
# Check PostgreSQL status
docker-compose ps postgres

# View PostgreSQL logs
docker-compose logs postgres
```

**Redis Connection Failed**
```bash
# Check Redis status
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping
```

**OpenAI API Issues**
- Verify API key is set in `.env` file
- Check API key validity and credits
- Review OpenAI API status page

**Docker Issues**
```bash
# Rebuild without cache
docker-compose build --no-cache

# Reset Docker environment
docker-compose down -v
docker system prune -a
```

## 📞 Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section above
- Review logs: `docker-compose logs -f sam-bot`

---

**SAM Bot** - Bringing the power of AI-driven conversation with knowledge retrieval to your applications! 🤖✨