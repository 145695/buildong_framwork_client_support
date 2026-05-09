# Knowledge Base Text Extraction & Usage

## Overview
The knowledge base system extracts text from documents, processes it intelligently, and uses it for question answering through RAG (Retrieval-Augmented Generation).

## Text Extraction Process

### 1. Document Loading
```python
async def load_documents(self):
    """Load and intelligently process documents from text files"""
```

**Source Files**: Text files in `text_dir` (converted from PDFs)
- Looks for `*.txt` files
- Requires minimum 50 characters to be useful
- Preserves original PDF filename mapping

### 2. Text Chunking
```python
chunks = self._create_chunks(content)
```

**Chunking Strategy**:
- Splits large documents into manageable pieces
- Maintains context coherence
- Optimized for vector search

### 3. Intelligent Filtering
```python
useful_chunks = await self._filter_useful_chunks(chunks)
```

**LLM-Based Filtering**:
- Uses Mistral LLM to evaluate chunk usefulness
- Filters out irrelevant content
- Keeps only meaningful information

### 4. Document Profiling
```python
profile = await self._profile_document(useful_chunks)
```

**Document Analysis**:
- Creates document profile/metadata
- Identifies document type and purpose
- Categorizes content for better retrieval

## Vector Index Creation

### 1. Embedding Generation
```python
embeddings = self.embedder.encode(texts, show_progress_bar=True)
```

**Sentence Transformers**:
- Converts text chunks to vector embeddings
- Captures semantic meaning
- Enables similarity search

### 2. FAISS Index Building
```python
self.faiss_index = faiss.IndexFlatIP(dim)
self.faiss_index.add(embeddings)
```

**Vector Database**:
- Fast similarity search
- L2 normalization for accuracy
- Efficient retrieval

## Query Processing

### 1. Question Embedding
- User question converted to vector
- Semantic similarity search
- Finds relevant document chunks

### 2. Context Retrieval
```python
relevant_chunks = self._retrieve_relevant_chunks(question)
```

**Retrieval Process**:
- Vector similarity search
- Top-k most relevant chunks
- Context assembly

### 3. Answer Generation
```python
response = await self.llm.ainvoke(prompt)
```

**LLM Reasoning**:
- Uses retrieved context
- Generates comprehensive answer
- Cites sources properly

## Data Flow

```
PDF Files → Text Extraction → Chunking → LLM Filtering → Profiling → Embedding → FAISS Index → Query → Retrieval → Answer Generation
```

## Key Features

### Intelligent Processing
- **LLM-powered filtering**: Only keeps useful content
- **Document profiling**: Understands document types
- **Semantic chunking**: Maintains context coherence

### Efficient Search
- **Vector embeddings**: Semantic similarity
- **FAISS indexing**: Fast retrieval
- **Context ranking**: Most relevant first

### Quality Answers
- **Retrieval-augmented**: Uses actual documents
- **Source attribution**: References original content
- **Confidence scoring**: Answer reliability

## File Structure

```
knowledge_base/
├── text_files/           # Extracted text from PDFs
├── document_chunks/      # Processed chunks
├── vector_index/         # FAISS index
└── profiles/            # Document metadata
```

## Usage in Voice Pipeline

When a voice query comes through:

1. **Transcription**: Voice → Text
2. **Query Processing**: Text → Vector
3. **Retrieval**: Vector → Relevant Chunks
4. **Answer Generation**: Chunks + LLM → Response
5. **Response Formatting**: Include sources and confidence

This ensures accurate, context-aware answers from the knowledge base.
