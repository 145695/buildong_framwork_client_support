"""
Knowledge Base Service - Handles document loading and searching.
Runs on its own CPU so KB search NEVER blocks audio or LLM processing.
This is THE fix for your bottleneck.
"""
import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import asyncio

logger = logging.getLogger(__name__)

app = FastAPI(title="MACES Knowledge Base Service")

# Pre-load documents at startup - THIS IS THE KEY FIX
kb_system = None

@app.on_event("startup")
async def startup():
    """Load KB documents at startup, not during requests"""
    global kb_system
    try:
        from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem
        kb_system = IntelligentRAGSystem()
        
        # Load documents NOW, not when a request comes in
        if asyncio.iscoroutinefunction(kb_system.load_documents):
            await kb_system.load_documents()
        else:
            kb_system.load_documents()
        
        print("[KB Service] Documents pre-loaded successfully")
    except Exception as e:
        print(f"[KB Service] Startup failed: {e}")


class KBQueryRequest(BaseModel):
    query: str
    language: str = "fr"


class KBQueryResponse(BaseModel):
    answer: str
    confidence: float
    documents_found: int
    sources: List[str] = []


@app.post("/search", response_model=KBQueryResponse)
async def search_knowledge_base(req: KBQueryRequest):
    """Search the knowledge base - runs on dedicated CPU"""
    if not kb_system:
        raise HTTPException(503, "Knowledge base not initialized")
    
    try:
        if asyncio.iscoroutinefunction(kb_system.ask_question):
            result = await kb_system.ask_question(req.query)
        else:
            result = kb_system.ask_question(req.query)
        
        return KBQueryResponse(
            answer=result.get("answer", "No answer available"),
            confidence=result.get("confidence", 0.0),
            documents_found=result.get("documents_found", 0),
            sources=result.get("sources", [])
        )
    except Exception as e:
        raise HTTPException(500, f"KB search failed: {str(e)}")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "kb-service",
        "documents_loaded": kb_system is not None
    }