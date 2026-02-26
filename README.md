# DocuChat Backend — Enterprise Chatbot API

**Production-ready FastAPI backend for document-based chatbots with RAG and AI integration.**

![Architecture](architecture.png)

## What It Does

DocuChat Backend provides the API layer for building enterprise chatbots that can answer questions from your documents. Upload PDFs, ask questions, get accurate answers with citations.

**Why it matters:** Most chatbots hallucinate. This one uses RAG (Retrieval-Augmented Generation) to ground answers in your actual documents, with full auditability.

## Quick Start

```bash
# Clone
git clone https://github.com/avishek15/docuchat-backend.git
cd docuchat-backend

# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Add your OPENAI_API_KEY

# Run
uvicorn app.main:app --reload
```

## Features

- **RAG pipeline:** Retrieve relevant docs before answering
- **Citations:** Every answer links to source documents
- **Multi-format support:** PDF, DOCX, TXT, Markdown
- **Conversation memory:** Context-aware responses
- **Audit logs:** Track all queries and responses
- **Rate limiting:** Prevent abuse

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/upload` | POST | Upload documents |
| `/chat` | POST | Send message, get response |
| `/documents` | GET | List uploaded documents |
| `/health` | GET | Health check |

### Example: Chat with Documents

```bash
# Upload a document
curl -X POST "http://localhost:8000/upload" \
  -F "file=@report.pdf"

# Ask a question
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the key findings?", "session_id": "abc123"}'
```

**Response:**
```json
{
  "response": "The key findings are...",
  "citations": [
    {"page": 5, "text": "Relevant excerpt..."}
  ],
  "confidence": 0.92
}
```

## Tech Stack

- **Python 3.10+**
- **FastAPI** — Async API framework
- **LangChain** — LLM orchestration
- **ChromaDB** — Vector database
- **OpenAI** — LLM provider

## Architecture

```
User Query
    ↓
Embedding (OpenAI)
    ↓
Vector Search (ChromaDB)
    ↓
Context Retrieval
    ↓
LLM Response (GPT-4)
    ↓
Answer + Citations
```

## Use Cases

| Use Case | How It Helps |
|----------|--------------|
| **Internal knowledge base** | Employees query company docs |
| **Customer support** | Auto-answer from help docs |
| **Legal/compliance** | Search contracts and policies |
| **Research** | Query academic papers |

## Configuration

```env
# .env
OPENAI_API_KEY=sk-...
CHROMA_PERSIST_DIR=./chroma_db
MAX_TOKENS=2000
TEMPERATURE=0.7
```

## Roadmap

- [ ] Multi-tenant support
- [ ] RBAC (role-based access control)
- [ ] Webhook integrations
- [ ] Fine-tuning support

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT License - see [LICENSE](LICENSE)

## Author

Built by [Avishek Majumder](https://invaritech.ai)

- X: [@AviMajumder1503](https://x.com/AviMajumder1503)
- LinkedIn: [avishek-majumder](https://linkedin.com/in/avishek-majumder)

---

**Used in production at [Invaritech](https://invaritech.ai)** — Enterprise AI chatbots with governance.
