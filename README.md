# DocuChat Backend

**Enterprise Chatbot API with RAG + AI Memory**

[![Build Status](https://github.com/avishek15/docuchat-backend/actions/workflows/main.yml/badge.svg)](https://github.com/avishek15/docuchat-backend/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/avishek15/docuchat-backend.svg)](https://github.com/avishek15/docuchat-backend/stargazers)

![Architecture](docs/architecture.png)

## What It Does

FastAPI backend for building enterprise chatbots with:
- **RAG (Retrieval-Augmented Generation)** — Chat with your documents
- **AI Memory** — Context-aware conversations
- **Vector Search** — Pinecone-powered semantic search
- **Multi-tenant** — Supports multiple organizations

## Why It Matters

Most chatbot backends are either:
- Too simple (no RAG, no memory)
- Too complex (requires 10+ services)

DocuChat sits in the middle: production-ready RAG without the complexity.

## Quick Start

```bash
# Clone
git clone https://github.com/avishek15/docuchat-backend.git
cd docuchat-backend

# Install
pip install -e .

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Run
python main.py
```

API runs at `http://localhost:8000`

## Features

### RAG Pipeline
- Upload documents → automatic chunking + embedding
- Query documents → semantic search + LLM response
- Cite sources → show which document chunk was used

### AI Memory
- Conversation history stored in SQLModel
- Context window management
- Multi-turn conversations

### Vector Search
- Pinecone integration
- Automatic embedding (OpenAI)
- Hybrid search (keyword + semantic)

### Multi-tenant
- Organization-level data isolation
- User authentication (ready)
- Role-based access (ready)

## Tech Stack

| Layer | Technology |
|-------|------------|
| **API** | FastAPI |
| **Database** | SQLModel + LibSQL |
| **Vector DB** | Pinecone |
| **AI/LLM** | LangChain + LangGraph + OpenAI |
| **Deployment** | AWS Lambda (serverless) |

## API Endpoints

### Chat

```bash
POST /api/chat
{
  "message": "What is our refund policy?",
  "conversation_id": "abc123"
}

Response:
{
  "response": "Our refund policy allows...",
  "sources": [
    {"document": "policy.pdf", "chunk": 5, "text": "..."}
  ],
  "conversation_id": "abc123"
}
```

### Documents

```bash
# Upload document
POST /api/documents/upload
Content-Type: multipart/form-data
file: document.pdf

# List documents
GET /api/documents

# Delete document
DELETE /api/documents/{id}
```

### Health

```bash
GET /health
```

## Project Structure

```
docuchat-backend/
├── app/
│   ├── api/          # API routes
│   ├── business/     # Business logic
│   ├── core/         # Config, security
│   ├── db/           # Database models
│   ├── models/       # Pydantic models
│   ├── services/     # RAG, embeddings, etc.
│   └── utils/        # Helpers
├── tests/            # Test suite
├── main.py           # Entry point
└── lambda_handler.py # AWS Lambda handler
```

## Configuration

Create `.env` file:

```env
# Required
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_ENVIRONMENT=...
PINECONE_INDEX=...

# Database
DATABASE_URL=libsql://...

# Optional
LOG_LEVEL=INFO
ENVIRONMENT=development
```

## Deployment

### AWS Lambda

```bash
# Build
pip install -e .

# Deploy with SAM/Serverless Framework
# (config not included)
```

### Docker

```bash
docker build -t docuchat-backend .
docker run -p 8000:8000 docuchat-backend
```

### Traditional Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Use Cases

### 1. Internal Knowledge Base
Upload company docs → employees chat with knowledge base

### 2. Customer Support
Upload FAQs + manuals → customers get instant answers

### 3. Document Q&A
Upload contracts/legal docs → query specific clauses

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md)

### Development Setup

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT License - see [LICENSE](LICENSE)

## Author

Built by **Avishek Majumder**

- 🌐 [invaritech.ai](https://invaritech.ai)
- 🐦 [@AviMajumder1503](https://x.com/AviMajumder1503)
- 💼 [LinkedIn](https://linkedin.com/in/avishek-majumder)
- 🐙 [GitHub](https://github.com/avishek15)

---

**Star ⭐ this repo if you find it useful!**
