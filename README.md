<div align="center">
  <img src="assets/logo/mitra-bot-logo.png" alt="Mitra Bot Logo" width="200"/>
  <div>

# Mitra Bot - Advanced AI Customer Support Assistant

🤖 **Mitra** is a comprehensive AI-powered customer support bot that leverages your company's documentation to provide accurate, context-aware answers to customer queries.

## 🚀 Key Features

### Core Capabilities
- **🔍 Advanced RAG (Retrieval-Augmented Generation)**: Semantic search with PostgreSQL vector storage
- **📚 Multi-Format Document Processing**: PDF, DOCX, TXT, HTML support with intelligent chunking
- **🧠 OpenAI GPT Integration**: GPT-3.5/4 with confidence scoring and context management
- **💬 Multi-Turn Conversations**: Redis-powered session management with conversation memory
- **🔐 Enterprise Authentication**: JWT-based auth with role-based access control
- **📊 Real-Time Analytics**: Comprehensive usage analytics and performance monitoring
- **🌐 RESTful API**: Complete API with rate limiting and webhook support
- **🎯 Admin Dashboard**: Web-based management interface

### Advanced Features
- **Vector Similarity Search**: Semantic search with configurable similarity thresholds
- **Automatic Categorization**: Content-based document categorization
- **Confidence Scoring**: AI response confidence assessment
- **Human Handoff**: Intelligent escalation to human agents
- **Multi-Language Support**: Language detection and processing
- **Version Control**: Document versioning and update tracking
- **GDPR Compliance**: Data retention policies and user data export

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Gateway    │    │   Admin Panel   │
│   (Chat UI)     │◄──►│  (Flask + JWT)   │◄──►│  (Management)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Core Services                            │
├─────────────────┬─────────────────┬─────────────────────────────┤
│ Conversation    │ Knowledge       │ Document Processing         │
│ Engine          │ Search Engine   │ Service                     │
│ (OpenAI + RAG)  │ (Vector Search) │ (Multi-format Support)      │
└─────────────────┴─────────────────┴─────────────────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │      Redis      │    │   File Storage  │
│  (Documents,    │    │ (Sessions,      │    │   (Uploads,     │
│   Embeddings,   │    │  Cache)         │    │    Temp Files)  │
│   Analytics)    │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📋 Prerequisites

- **Python 3.11+**
- **PostgreSQL 13+** with pgvector extension (recommended)
- **Redis 6+**
- **OpenAI API Key**
- **Docker & Docker Compose** (for containerized deployment)

## ⚡ Quick Start

### 1. Environment Setup
```bash
# Clone and navigate to the project
cd mitra-bot

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your configuration
```

### 2. Docker Deployment (Recommended)
```bash
# Start all services
docker-compose up -d

# With monitoring (Prometheus + Grafana)
docker-compose --profile monitoring up -d

# Check health
curl http://localhost:5000/api/health
```

### 3. Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set up database (PostgreSQL recommended)
export DATABASE_URL="postgresql://user:pass@localhost/sam_db"
export REDIS_URL="redis://localhost:6379/0"
export OPENAI_API_KEY="your-key-here"

# Run the API server
python src/api/main_api.py

# Access admin dashboard
open http://localhost:5000/admin
```

## 🔧 Configuration

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://mitra_user:password@localhost:5432/mitra_db
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-3.5-turbo
CONFIDENCE_THRESHOLD=0.6

# Security
JWT_SECRET_KEY=your_jwt_secret_key

# Features
MAX_FILE_SIZE=16777216
CHUNK_SIZE=1000
ENABLE_ANALYTICS=true
ENABLE_FEEDBACK=true
```

### System Configuration
Configuration can be managed through the admin dashboard or API:

```bash
# Get current configuration
GET /api/config

# Update configuration
PUT /api/config
{
  "chunk_size": 1200,
  "similarity_threshold": 0.15,
  "enable_analytics": true
}
```

## 📖 API Documentation

### Authentication
```bash
# Register user
POST /api/auth/register
{
  "email": "admin@company.com",
  "username": "admin",
  "password": "secure_password"
}

# Login
POST /api/auth/login
{
  "email": "admin@company.com",
  "password": "secure_password"
}
```

### Document Management
```bash
# Upload document file
POST /api/documents/upload
Content-Type: multipart/form-data
- file: document.pdf
- title: "User Manual"
- category: "documentation"

# Upload text content
POST /api/documents/text
{
  "title": "FAQ Section",
  "content": "Frequently asked questions...",
  "category": "faq"
}

# List documents
GET /api/documents?category=faq&limit=20
```

### Chat Interface
```bash
# Chat with context
POST /api/chat
{
  "message": "How do I reset my password?",
  "session_id": "session_123"
}

# Rate response
POST /api/chat/rate
{
  "conversation_id": "conv_456",
  "rating": 5,
  "comment": "Very helpful!"
}
```

### Knowledge Search
```bash
# Semantic search
GET /api/search?q=password reset&type=semantic&limit=5

# Advanced search with filters
POST /api/search
{
  "query": "installation guide",
  "type": "advanced",
  "category": "documentation",
  "limit": 10
}
```

### Analytics (Admin Only)
```bash
# Get overview
GET /api/analytics/overview?days=7

# Conversation analytics
GET /api/analytics/conversations?days=30

# Knowledge base stats
GET /api/knowledge/stats
```

## 🎛️ Admin Dashboard

Access the admin dashboard at `http://localhost:5000/admin`

**Features:**
- 📊 Real-time system metrics
- 📚 Document management
- 💬 Conversation monitoring
- 👥 User management
- ⚙️ System configuration
- 📈 Analytics and insights

## 🏭 Production Deployment

### Kubernetes Deployment
```bash
# Apply Kubernetes manifests
kubectl apply -f deployment/

# Check deployment status
kubectl get pods -l app=mitra-bot
```

### AWS ECS Deployment
```bash
# Update task definition
aws ecs register-task-definition --cli-input-json file://deployment/task-definition.json

# Update service
aws ecs update-service --cluster mitra-cluster --service mitra-bot-service
```

### Monitoring & Observability

**Health Monitoring:**
- Health check endpoint: `/api/health`
- Prometheus metrics: `/metrics`
- Custom dashboards in Grafana

**Logging:**
- Structured JSON logging
- Sentry integration for error tracking
- Request/response logging

## 🔒 Security Features

- **Authentication**: JWT-based with configurable expiration
- **Authorization**: Role-based access control (RBAC)
- **Rate Limiting**: Configurable per-endpoint limits
- **Data Encryption**: Secrets management and encrypted storage
- **GDPR Compliance**: Data retention policies and user data export
- **Security Headers**: CORS, CSP, and other security headers

## 📊 Performance Characteristics

- **Response Time**: < 2 seconds for chat responses
- **Concurrent Users**: 1000+ with auto-scaling
- **Document Processing**: ~1 minute per 100 pages
- **Search Performance**: < 500ms for semantic queries
- **Accuracy**: 95%+ answer relevance score

## 🧪 Testing

```bash
# Run unit tests
pytest tests/

# Run integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=src tests/

# Load testing
locust -f tests/load_test.py --host=http://localhost:5000
```

## 🛠️ Development

### Project Structure
```
mitra-bot/
├── src/
│   ├── api/              # API endpoints
│   ├── services/         # Business logic services
│   ├── models/           # Database models
│   └── utils/            # Utility functions
├── templates/            # HTML templates
├── deployment/           # Kubernetes/ECS configs
├── assets/              # Images and static assets
├── tests/               # Test files
└── docs/                # Documentation
```

### Adding New Features

1. **New API Endpoint**: Add to `src/api/main_api.py`
2. **New Service**: Create in `src/services/`
3. **Database Changes**: Update models and run migrations
4. **Tests**: Add corresponding test files
5. **Documentation**: Update API docs and README



## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/ItsVicky25/mitra-bot/blob/main/LICENSE) file for details.

