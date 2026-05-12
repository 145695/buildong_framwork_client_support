import os
import logging
from dotenv import load_dotenv
from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem
from app.layer2.loan.agent import run_loan_agent
from app.layer2.orchestrator import route_intent
from app.layer2.client_support import client_support_node
from app.schemas.conversation import ConversationState

# Load environment variables from .env file
load_dotenv()

# Settings for different model API keys
class settings:
    NVIDIA_API_KEY_LLAMA = os.getenv("NVIDIA_API_KEY_LLAMA", "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")
    NVIDIA_API_KEY_MISTRAL = os.getenv("NVIDIA_API_KEY_MISTRAL", "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")

# Module-level RAG singleton
_rag_instance = None

async def get_rag_system() -> IntelligentRAGSystem:
    """Get or initialize the RAG system singleton"""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = IntelligentRAGSystem()
        await _rag_instance.load_documents()
    return _rag_instance

logger = logging.getLogger(__name__)

def knowledge_base_node(state: ConversationState) -> ConversationState:
    """Knowledge Base node using real RAG system"""
    import asyncio
    import concurrent.futures
    
    # Get RAG system singleton and process question
    def run_async_tasks():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            rag = loop.run_until_complete(get_rag_system())
            # Use reconstructed_query if available, fallback to normalized_text_en
            query = getattr(state, "reconstructed_query", None) or state.normalized_text_en or state.original_text or ""
            print(f"KB searching: {query}")
            result = loop.run_until_complete(rag.ask_question(query))
            return result
        finally:
            loop.close()
    
    # Run in separate thread to avoid event loop conflicts
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_async_tasks)
        result = future.result()
    
    # Store RAG result in state
    state.kb_result = result.get("answer", "")
    # Note: kb_sources and kb_confidence are not valid ConversationState fields
    
    # Update state with agent feedback
    state.agent_feedback = {
        "knowledge_base": {
            "status": "completed",
            "response": result.get("answer", ""),
            "confidence": result.get("confidence", 0.0),
            "analysis": {
                "needs_more_work": False,
                "next_agent_suggested": "client_support"
            }
        }
    }
    
    state.trace.append("knowledge_base:completed:rag_response")
    return state

# client_support_node is now imported from app.layer2.client_support module


async def _run_without_langgraph(state: ConversationState) -> ConversationState:
    # Check if we're in planning mode - stop after orchestrator
    if state.orchestrator_context.get("planning_mode", False):
        state.trace.append("layer2:planning_mode:stopping_after_orchestrator")
        state.trace.append("layer2:complete")
        return state
    
    # Deterministic fallback so framework can run before dependencies are ready.
    state = route_intent(state)
    
    # Execute agents based on orchestrator selection
    if "knowledge_base" in state.required_agents:
        state = knowledge_base_node(state)

    if "loan" in state.required_agents:
        state = run_loan_agent(state)

    if "client_support" in state.required_agents:
        state = client_support_node(state)
    
    state.trace.append("layer2:runtime:fallback")
    state.trace.append("layer2:complete")
    return state


from langgraph.graph import END, START, StateGraph
from app.schemas.conversation import ConversationState

def _run_with_langgraph(state: ConversationState) -> ConversationState:
    graph = StateGraph(ConversationState)
    # Skip orchestrator node - intent already computed in voice.py
    graph.add_node("knowledge_base", knowledge_base_node)
    # Remove old loan nodes - will add new ones below
    
    def choose_after_start(current: ConversationState) -> str:
        # Always route to knowledge_base first (intent already computed)
        print("🔍 Graph Routing: Using pre-computed intent, routing to knowledge_base")
        return "knowledge_base"

    # Route from knowledge_base to loan (conditional) or client_support
    def choose_after_knowledge_base(current: ConversationState) -> str:
        # Check if loan evaluation is needed
        loan_intents = ["check_loan_eligibility", "apply_for_loan", "loan_status"]
        if current.intent in loan_intents:
            print("🔍 Graph Routing: Loan intent detected, routing to loan_agent")
            return "loan_agent"
        else:
            print("🔍 Graph Routing: No loan intent, routing to client_support")
            return "client_support"

    # Route from loan to client_support (always)
    def choose_after_loan(current: ConversationState) -> str:
        print("🔍 Graph Routing: Loan complete, routing to client_support")
        return "client_support"

    # Placeholder nodes
    def loan_agent_node(state: ConversationState) -> ConversationState:
        print("🔍 Loan Agent: Processing loan evaluation (placeholder)")
        state.loan_result = None  # placeholder
        return state

    # client_support_node is now defined outside this function

    # Register new nodes
    graph.add_node("loan_agent", loan_agent_node)
    graph.add_node("client_support", client_support_node)

    # Updated graph edges - start directly to knowledge_base
    graph.add_conditional_edges(
        START,
        choose_after_start,
        {
            "knowledge_base": "knowledge_base",
        },
    )

    graph.add_conditional_edges("knowledge_base", choose_after_knowledge_base, {
        "loan_agent": "loan_agent",
        "client_support": "client_support",
    })

    graph.add_conditional_edges("loan_agent", choose_after_loan, {
        "client_support": "client_support",
    })

    # client_support goes to END
    graph.add_edge("client_support", END)

    # Add LangSmith observability with data anonymization
    from langsmith import Client
    from langsmith.anonymizer import create_anonymizer
    from langchain_core.tracers.langchain import LangChainTracer

    anonymizer = create_anonymizer([
        {"pattern": r"\b\d{10,20}\b", "replace": "<account_number>"},
        {"pattern": r"\b0\d{9}\b",    "replace": "<phone_number>"},
        {"pattern": r"\b\d{16}\b",    "replace": "<card_number>"},
    ])

    tracer_client = Client(anonymizer=anonymizer)
    tracer = LangChainTracer(client=tracer_client)

    compiled = graph.compile().with_config({"callbacks": [tracer]})
    result = compiled.invoke(state)
    
    # Ensure result is a ConversationState object with trace
    if hasattr(result, 'trace'):
        result.trace.append("layer2:runtime:langgraph")
        result.trace.append("layer2:complete")
    else:
        # If result is dict, convert back to ConversationState
        if isinstance(result, dict):
            result = ConversationState(**result)
            result.trace.append("layer2:runtime:langgraph")
            result.trace.append("layer2:complete")
    
    return result


def run_multi_agent_core(state: ConversationState) -> ConversationState:
    try:
        return _run_with_langgraph(state)
    except Exception as exc:  # pragma: no cover
        state.trace.append(f"layer2:langgraph_unavailable:{type(exc).__name__}")
        return _run_without_langgraph(state)
