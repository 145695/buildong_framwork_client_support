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
    
    # Check if loan eligibility test
    loan_intents = ["check_loan_eligibility", "apply_for_loan", "loan_status", "apply_for_mortgage"]
    eligibility_test_asked = state.orchestrator_context.get("eligibility_test_asked", False)
    eligibility_answer = state.orchestrator_context.get("eligibility_test_answer", None)
    
    # Skip KB if we're in loan eligibility test mode
    should_skip_kb = state.intent in loan_intents or eligibility_test_asked
    
    # Execute agents based on orchestrator selection
    if "knowledge_base" in state.required_agents and not should_skip_kb:
        state = knowledge_base_node(state)

    if "loan" in state.required_agents:
        state = run_loan_agent(state)
        # If eligibility test is answered, skip client_support
        if eligibility_answer is not None:
            state.trace.append("layer2:loan_eligibility_test:answered:skipping_client_support")
            state.trace.append("layer2:runtime:fallback")
            state.trace.append("layer2:complete")
            return state

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
        # Check if we're waiting for eligibility test answer
        eligibility_test_asked = current.orchestrator_context.get("eligibility_test_asked", False)
        print(f"🔍 Graph Routing DEBUG: eligibility_test_asked={eligibility_test_asked}, intent={current.intent}")
        
        if eligibility_test_asked:
            print("🔍 Graph Routing: Waiting for eligibility test answer, routing to loan_agent")
            return "loan_agent"
        
        # Check if loan eligibility test
        loan_intents = ["check_loan_eligibility", "apply_for_loan", "loan_status", "apply_for_mortgage", "check_mortgage_payments"]
        print(f"🔍 Graph Routing DEBUG: intent '{current.intent}' in loan_intents {loan_intents}: {current.intent in loan_intents}")
        
        if current.intent in loan_intents:
            # Route loan intents directly to loan agent, skip knowledge_base
            print("🔍 Graph Routing: Loan intent detected, routing directly to loan_agent (skipping KB)")
            return "loan_agent"
        else:
            # Non-loan queries go through knowledge_base first
            print("🔍 Graph Routing: Using pre-computed intent, routing to knowledge_base")
            return "knowledge_base"

    # Route from knowledge_base to client_support (no loan here anymore, they go directly to loan_agent)
    def choose_after_knowledge_base(current: ConversationState) -> str:
        print("🔍 Graph Routing: Knowledge base complete, routing to client_support")
        return "client_support"

    # Route from loan to client_support only if needed
    def choose_after_loan(current: ConversationState) -> str:
        # Check if eligibility test is complete (answered yes or no)
        eligibility_answer = current.orchestrator_context.get("eligibility_test_answer", None)
        
        if eligibility_answer is not None:
            # Eligibility test has been answered, skip client_support and end layer2
            print("🔍 Graph Routing: Loan eligibility test answered, ending layer2 pipeline")
            return END
        else:
            # Eligibility test still pending, go to client_support for synthesis
            print("🔍 Graph Routing: Loan eligibility test pending, routing to client_support")
            return "client_support"

    # Loan agent node
    def loan_agent_node(state: ConversationState) -> ConversationState:
        print("🔍 Loan Agent: Processing loan eligibility test")
        state = run_loan_agent(state)
        return state

    # client_support_node is now defined outside this function

    # Register new nodes
    graph.add_node("loan_agent", loan_agent_node)
    graph.add_node("client_support", client_support_node)

    # Updated graph edges - start can go to knowledge_base or loan_agent
    graph.add_conditional_edges(
        START,
        choose_after_start,
        {
            "knowledge_base": "knowledge_base",
            "loan_agent": "loan_agent",
        },
    )

    graph.add_conditional_edges("knowledge_base", choose_after_knowledge_base, {
        "client_support": "client_support",
    })

    graph.add_conditional_edges("loan_agent", choose_after_loan, {
        "client_support": "client_support",
        END: END,
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
