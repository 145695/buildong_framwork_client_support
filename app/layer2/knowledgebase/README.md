# Banking Knowledge Base RAG System

A complete Retrieval-Augmented Generation (RAG) system for answering client questions about banking policies, loans, deposits, cards, and account changes.

## 🎯 Goal

Build a banking assistant that reads PDF policy documents and answers client questions about:
- **Loans (قروض)** - Personal loans, eligibility, application procedures
- **Versements / Deposits (تحويلات / إيداعات)** - Money transfers, deposit limits, procedures
- **Cards (بطاقات)** - Credit cards, debit cards, application processes
- **Account changes (تغييرات)** - Account modifications, documentation requirements

## 🛠️ Tech Stack (Free, no local CPU required)

- **PDF parsing**: `pdfplumber` (lightweight, no GPU)
- **Embeddings**: HuggingFace Inference API (free tier) OR local `sentence-transformers`
- **Vector store**: `ChromaDB` (runs locally, extremely lightweight)
- **LLM**: `Groq API` (free tier - Llama3 or Mixtral) via `langchain-groq`
- **Framework**: `LangChain`
- **Interface**: FastAPI REST endpoint + CLI mode

## 📁 Project Structure

```
app/layer2/knowledgebase/
├── __init__.py              # Package initialization
├── pdf_parser.py           # PDF document parsing with pdfplumber
├── embeddings.py           # Text embeddings (HF API + local fallback)
├── vector_store.py         # ChromaDB vector database
├── llm.py                # Groq API LLM integration
├── rag_agent.py           # Main RAG agent class
├── api.py                # FastAPI REST endpoint
├── cli.py                # Command line interface
└── README.md              # This file

policies/                 # PDF policy documents (layer2/policies/)
chroma_db/               # ChromaDB storage (created automatically)
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create/update `.env` file:

```bash
# Required for LLM
GROQ_API_KEY=your_groq_api_key_here

# Optional for embeddings (higher rate limits)
HUGGINGFACE_API_TOKEN=your_hf_token_here
```

Get API keys:
- **Groq API**: https://console.groq.com/ (free tier available)
- **HuggingFace**: https://huggingface.co/settings/tokens (optional, for higher rate limits)

### 3. Prepare Policy Documents

Place PDF policy documents in `app/layer2/policies/` directory:

```
app/layer2/policies/
├── loan_policies.pdf
├── deposit_regulations.pdf
├── card_guidelines.pdf
└── account_procedures.pdf
```

### 4. Initialize Knowledge Base

```bash
# Using CLI
python app/layer2/knowledgebase/cli.py --init

# Or rebuild from scratch
python app/layer2/knowledgebase/cli.py --init --rebuild
```

## 💻 Usage

### CLI Interface

```bash
# Interactive mode (recommended)
python app/layer2/knowledgebase/cli.py --init --interactive

# Single query
python app/layer2/knowledgebase/cli.py --query "What are loan requirements?"

# Show statistics
python app/layer2/knowledgebase/cli.py --stats

# Run system test
python app/layer2/knowledgebase/cli.py --test
```

### REST API

```bash
# Start API server
python app/layer2/knowledgebase/api.py --host 0.0.0.0 --port 8000

# Or with auto-reload for development
python app/layer2/knowledgebase/api.py --reload
```

API Endpoints:
- `GET /` - API information
- `GET /health` - Health check
- `POST /initialize` - Initialize knowledge base
- `POST /query` - Ask questions
- `GET /stats` - Get statistics
- `POST /rebuild` - Rebuild knowledge base
- `GET /test` - Test system components

### Python Integration

```python
from app.layer2.knowledgebase import KnowledgeBaseAgent

# Initialize agent
agent = KnowledgeBaseAgent()
agent.initialize()

# Query knowledge base
result = agent.query("What are the requirements for a personal loan?")
print(result['answer'])
```

## 🌍 Multilingual Support

The system supports queries in:
- **English** - Full support
- **French** - Full support  
- **Arabic** - Full support

Example queries:
- "What are the requirements for a bank loan?"
- "Quelles sont les exigences pour un prêt bancaire?"
- "ما هي متطلبات الحصول على قرض بنكي؟"

## 🔧 Configuration Options

### Embeddings
- **Default**: HuggingFace Inference API (free tier)
- **Fallback**: Local sentence-transformers
- **Models**: Multilingual embeddings for Arabic/French/English

### LLM
- **Primary**: Groq API with Llama3-8B or Mixtral
- **Fallback**: Direct API calls
- **Temperature**: 0.1 (for consistent responses)

### Vector Store
- **Database**: ChromaDB (local, persistent)
- **Dimensions**: 384 (standard for sentence-transformers)
- **Similarity**: Cosine similarity

## 📊 Features

### ✅ Core Features
- [x] PDF parsing with text extraction
- [x] Multilingual text embeddings
- [x] Vector similarity search
- [x] RAG-powered question answering
- [x] REST API interface
- [x] Interactive CLI
- [x] System health monitoring
- [x] Error handling and fallbacks

### 🔒 Security & Privacy
- [x] All processing can be done locally
- [x] No data sent to third parties (except API calls)
- [x] Persistent local storage
- [x] API key protection via environment variables

### 🚀 Performance
- [x] Lightweight ChromaDB storage
- [x] Efficient PDF parsing
- [x] Batch embedding processing
- [x] Fast API responses
- [x] Background processing for large datasets

## 🧪 Testing

```bash
# Test individual components
python app/layer2/knowledgebase/pdf_parser.py
python app/layer2/knowledgebase/embeddings.py
python app/layer2/knowledgebase/llm.py
python app/layer2/knowledgebase/vector_store.py

# Test complete system
python app/layer2/knowledgebase/rag_agent.py

# Test API
python app/layer2/knowledgebase/api.py --test

# Full system test
python app/layer2/knowledgebase/cli.py --init --test
```

## 🔍 Troubleshooting

### Common Issues

1. **"GROQ_API_KEY not found"**
   - Set GROQ_API_KEY in .env file
   - Get free key from https://console.groq.com/

2. **"No PDF files found"**
   - Check policies directory path
   - Ensure PDF files are in `app/layer2/policies/`

3. **"Embedding generation failed"**
   - Check internet connection for HF API
   - Try local embeddings with `--local-embeddings`

4. **"ChromaDB initialization failed"**
   - Check write permissions
   - Ensure disk space available

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📈 Performance

### Expected Performance
- **Initialization**: 2-5 minutes (depends on PDF count)
- **Query response**: 1-3 seconds
- **Memory usage**: <500MB (including embeddings)
- **Storage**: ~10MB per 100 PDF pages

### Optimization Tips
- Use local embeddings for better privacy
- Batch process large document sets
- Regularly rebuild vector store for updated policies

## 🤝 Contributing

1. Add new PDF policies to `policies/` directory
2. Rebuild knowledge base: `--init --rebuild`
3. Test with sample queries
4. Update documentation

## 📄 License

This project is part of the banking framework and follows the same license terms.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Run system test: `--test`
3. Check logs for error details
4. Verify API keys and network connectivity
