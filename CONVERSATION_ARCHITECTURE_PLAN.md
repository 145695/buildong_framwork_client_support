# Full Implementation Plan: Real Conversation Architecture

## Problem Statement
Currently, each new user message triggers re-processing of the entire conversation history through the pipeline:
- Turn 1: "I want loan" → Ingestion("I want loan")
- Turn 2: "yes" → Ingestion("I want loan" + "yes") ← **Reprocesses turn 1!**

This wastes compute and prevents stateful agent conversations.

---

## Solution Overview: Turn-Based Conversation Model

Each turn should be **independent**, but agents can **read previous turns from session**.

```
Session contains:
├── Turn 1
│   ├── user_input: "I want loan"
│   ├── agent_routed_to: "loan_agent"
│   ├── agent_response: "Test eligibility?"
│   ├── intent: "check_loan_eligibility"
│   └── metadata: {language, confidence, timestamp}
│
├── Turn 2
│   ├── user_input: "yes"
│   ├── routing_logic: "eligibility_answer_detected"
│   ├── agent_routed_to: "eligibility_handler" (special)
│   ├── agent_response: "[Redirect to URL]"
│   └── conversation_ended: true
│
└── Current State
    ├── waiting_for: "eligibility_answer"
    ├── current_agent: "loan_agent"
    ├── allow_turn_3: true/false
```

---

## Implementation Plan (Phase-by-Phase)

### Phase 1: Conversation Context Structure

**File**: `app/schemas/conversation_context.py` (NEW)

```python
from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel

class TurnRecord(BaseModel):
    """Single turn in conversation"""
    turn_number: int
    user_input: str                    # Raw message from user
    user_input_normalized: str         # English-normalized version
    user_language: str                 # Language detected
    agent_routed_to: str               # Which agent processed this turn
    agent_response: str                # What agent said
    intent: Optional[str] = None       # Detected intent
    confidence: float = 0.0
    routing_reason: str = ""           # Why routed to this agent
    metadata: Dict = {}                # Custom data per turn
    timestamp: datetime = None

    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now()
        super().__init__(**data)


class ConversationContext(BaseModel):
    """Full conversation state"""
    session_id: str
    turns: List[TurnRecord] = []       # All turns so far
    current_turn: int = 0              # Which turn we're on
    
    # Conversation Flow State
    waiting_for_response_from: Optional[str] = None  # Agent name
    waiting_for_input_type: Optional[str] = None     # "eligibility_answer", "free_form", etc.
    conversation_active: bool = True
    
    # Agent-specific context
    active_agent: Optional[str] = None # Current agent processing
    agent_context: Dict = {}           # Agent-specific data (eligibility_asked, etc.)
    
    # Metadata
    language: str = "en"
    created_at: datetime = None
    last_turn_at: datetime = None

    def __init__(self, **data):
        if 'created_at' not in data:
            data['created_at'] = datetime.now()
        super().__init__(**data)
    
    def add_turn(self, turn: TurnRecord):
        """Record a turn"""
        self.turns.append(turn)
        self.current_turn = len(self.turns)
        self.last_turn_at = datetime.now()
    
    def get_previous_turns(self, n: int = 5) -> List[TurnRecord]:
        """Get last N turns for agent context"""
        return self.turns[-n:] if self.turns else []
    
    def get_last_turn(self) -> Optional[TurnRecord]:
        """Get most recent turn"""
        return self.turns[-1] if self.turns else None
    
    def get_agent_history(self, agent_name: str) -> List[TurnRecord]:
        """Get all turns where this agent was active"""
        return [t for t in self.turns if t.agent_routed_to == agent_name]
```

---

### Phase 2: Update Session Manager

**File**: `app/layer2/shared/session_manager.py`

**Changes**:
1. Import `ConversationContext` and `TurnRecord`
2. Add conversation context to session storage
3. Provide helper methods

```python
# In create_session():
sessions[session_id] = {
    "history": [],
    "last_active": time.time(),
    "created_at": time.time(),
    "audio_state": "IDLE",
    "is_audio_session": False,
    "conversation_context": ConversationContext(session_id=session_id),
    "waiting_for_eligibility": False,
    "eligibility_language": "en",
}

# New methods:
def get_conversation_context(session_id: str) -> ConversationContext:
    """Retrieve conversation context"""
    session = get_session(session_id)
    if not session:
        return None
    return session.get("conversation_context", ConversationContext(session_id=session_id))

def add_turn_record(session_id: str, turn: TurnRecord):
    """Record a new turn in conversation"""
    session = get_session(session_id)
    if session:
        ctx = session.get("conversation_context", ConversationContext(session_id=session_id))
        ctx.add_turn(turn)
        session["conversation_context"] = ctx
        session["last_active"] = time.time()
        print(f"📝 TURN {turn.turn_number}: User='{turn.user_input[:40]}' Agent={turn.agent_routed_to}")

def set_agent_waiting_state(session_id: str, agent_name: str, input_type: str, context_data: Dict = None):
    """Set what agent is expecting next"""
    session = get_session(session_id)
    if session:
        ctx = session.get("conversation_context", ConversationContext(session_id=session_id))
        ctx.active_agent = agent_name
        ctx.waiting_for_response_from = agent_name
        ctx.waiting_for_input_type = input_type
        if context_data:
            ctx.agent_context.update(context_data)
        session["conversation_context"] = ctx
        print(f"⏳ WAITING: {agent_name} expects {input_type}")
```

---

### Phase 3: Update Voice Router - Only Process Current Message

**File**: `app/routers/voice.py`

**Key Change**: Process ONLY the current transcription, not history

**Before** (❌):
```python
text_for_ingestion = get_full_conversation_history(session_id) + new_transcription
state = ingest_chat_request(ChatRequest(message=text_for_ingestion, ...))
```

**After** (✅):
```python
# STEP 1: Check if we're in a special state (eligibility, etc.)
conv_context = get_conversation_context(session_id)

if conv_context.waiting_for_input_type == "eligibility_answer":
    # Handle eligibility interception (already implemented)
    # ...
    return results

# STEP 2: Process ONLY the current message
state = ingest_chat_request(ChatRequest(
    message=transcription,  # Only new message!
    source_language=detected_language,
    source_channel=SourceChannel.VOICE,
    conversation_id=session_id
))

# STEP 3: Pass history to orchestrator for context
state.conversation_history = conv_context.get_previous_turns(n=3)
```

---

### Phase 4: Update Orchestrator to Use Conversation History

**File**: `app/layer2/smart_pm_routing.py` (or wherever orchestrator is)

**Add history context**:
```python
def smart_pm_routing(state: ConversationState) -> ConversationState:
    """Route to appropriate agent"""
    
    # Get conversation history if available
    previous_turns = getattr(state, 'conversation_history', [])
    
    # Build context string for LLM
    history_context = ""
    if previous_turns:
        history_context = "Previous conversation:\n"
        for turn in previous_turns:
            history_context += f"User: {turn.user_input}\n"
            history_context += f"Agent: {turn.agent_response}\n"
    
    # Use history in intent detection
    full_context = history_context + f"Current: {state.normalized_text_en}"
    
    # Pass to intent detector with full context
    intent = detect_intent(full_context)  # Instead of just current message
    
    return state
```

---

### Phase 5: Update Agents to Read History

**File**: `app/layer2/loan/agent.py`

**Add context reading**:
```python
def run_loan_agent(state: ConversationState) -> ConversationState:
    """Loan agent - now context-aware"""
    
    # Get conversation context from session
    from app.layer2.shared.session_manager import get_conversation_context
    conv_ctx = get_conversation_context(state.conversation_id)
    
    # Check if THIS agent was the last active agent
    last_turn = conv_ctx.get_last_turn()
    agent_history = conv_ctx.get_agent_history("loan_agent")
    
    # Build agent memory
    agent_memory = ""
    if agent_history:
        agent_memory = "Your previous responses in this conversation:\n"
        for turn in agent_history:
            agent_memory += f"- You said: {turn.agent_response}\n"
    
    # Use memory in response generation
    prompt = agent_memory + f"New user input: {state.normalized_text_en}"
    
    # Generate response
    response = generate_response(prompt)
    
    # Record this turn
    from app.layer2.shared.session_manager import add_turn_record
    turn = TurnRecord(
        turn_number=conv_ctx.current_turn + 1,
        user_input=state.original_text,
        user_input_normalized=state.normalized_text_en,
        user_language=state.source_language,
        agent_routed_to="loan_agent",
        agent_response=response,
        intent=state.intent,
        confidence=state.orchestrator_context.get("confidence", 0),
        routing_reason="Loan intent detected",
    )
    add_turn_record(state.conversation_id, turn)
    
    # If asking eligibility, set waiting state
    if "eligibility" in response.lower():
        from app.layer2.shared.session_manager import set_agent_waiting_state
        set_agent_waiting_state(
            state.conversation_id, 
            agent_name="loan_agent",
            input_type="eligibility_answer",
            context_data={"asked_turn": conv_ctx.current_turn}
        )
    
    return state
```

---

### Phase 6: Update Voice Router - Record Turns

**File**: `app/routers/voice.py`

**At the end of pipeline, record the turn**:
```python
# STEP 6: After agent processing, record turn
from app.layer2.shared.session_manager import add_turn_record
from app.schemas.conversation_context import TurnRecord

if results.get("agent_response"):
    turn = TurnRecord(
        turn_number=conv_context.current_turn + 1,
        user_input=transcription,
        user_input_normalized=state.normalized_text_en,
        user_language=detected_language,
        agent_routed_to=results.get("selected_agent", "unknown"),
        agent_response=results["agent_response"],
        intent=state.intent,
        confidence=state.orchestrator_context.get("confidence", 0),
        metadata={
            "audio_duration": audio_duration,
            "tts_model": results.get("audio_model_used"),
        }
    )
    add_turn_record(session_id, turn)
```

---

### Phase 7: Update Eligibility Handler

**File**: `app/routers/voice.py`

**When handling eligibility yes/no, record it**:
```python
if is_waiting_for_eligibility_answer(session_id):
    # ... check yes/no ...
    
    if any(word in user_response for word in yes_patterns):
        # Record this turn
        turn = TurnRecord(
            turn_number=conv_context.current_turn + 1,
            user_input=transcription,
            user_input_normalized=user_response,
            user_language=eligibility_language,
            agent_routed_to="eligibility_handler",
            agent_response="[Redirecting to eligibility test]",
            routing_reason="Eligibility yes detected",
            metadata={"redirect_url": "https://bna-loan-eligibility-test.com"}
        )
        add_turn_record(session_id, turn)
        clear_eligibility_flag(session_id)
```

---

## Data Flow Diagram

```
TURN 1: "I want a loan"
├─ Ingestion: "I want a loan" (current msg only)
├─ Orchestrator: Intent=loan
├─ Route: → loan_agent
├─ Response: "Test eligibility?"
├─ Record Turn:
│  └─ TurnRecord(turn=1, user="I want a loan", agent=loan, response="Test?")
└─ Set Waiting: waiting_for=eligibility_answer

TURN 2: "yes"
├─ Check Session: "waiting_for_eligibility_answer" = TRUE
├─ Ingestion: "yes" (current msg only)
├─ Router Interception:
│  ├─ Detect pattern: "yes"
│  ├─ Generate response: "[Redirect]"
│  └─ Record Turn:
│     └─ TurnRecord(turn=2, user="yes", agent=eligibility_handler, response="[Redirect]")
└─ Return redirect + end
```

---

## Database/Session Storage Diagram

```
sessions = {
    "session-123": {
        "history": [                          ← Old model (keep for backward compat)
            {user: "I want loan", avatar: "Test?"},
        ],
        "conversation_context": {             ← New model
            "session_id": "session-123",
            "turns": [
                {
                    "turn_number": 1,
                    "user_input": "I want a loan",
                    "agent_routed_to": "loan_agent",
                    "agent_response": "Test eligibility?",
                    "intent": "check_loan_eligibility",
                    ...
                },
                {
                    "turn_number": 2,
                    "user_input": "yes",
                    "agent_routed_to": "eligibility_handler",
                    "agent_response": "[Redirect URL]",
                    ...
                }
            ],
            "current_turn": 2,
            "active_agent": "eligibility_handler",
            "waiting_for_response_from": null,
            "conversation_active": false,
            ...
        },
        "waiting_for_eligibility": false,
        ...
    }
}
```

---

## Implementation Steps (Order)

1. ✅ Create `ConversationContext` schema
2. ✅ Update session manager with new functions
3. ✅ Modify voice router to process current message only
4. ✅ Update orchestrator to use history
5. ✅ Update agents to read/write turn records
6. ✅ Update eligibility handler to record turns
7. ✅ Add conversation viewer endpoint (optional - for debugging)

---

## Benefits of This Approach

| Benefit | How |
|---------|-----|
| **No re-processing** | Each turn processes only new message |
| **Agent awareness** | Agents read full conversation from session |
| **Stateful conversations** | Each agent knows what happened before |
| **Efficient** | Linear processing, not exponential |
| **Debuggable** | Full turn history visible in session |
| **Scalable** | Agents don't need to store history themselves |
| **Language-aware** | Each turn tracks language |
| **Handles interruptions** | Can switch agents mid-conversation |

---

## Example: Complete Flow with New Architecture

```
Session Created
├─ ConversationContext initialized
│  └─ turns: []
│  └─ current_turn: 0

User says: "I want a loan"
├─ Turn 1 Starts
├─ Ingestion: "I want a loan" (ONLY THIS)
├─ Orchestrator gets context: previous_turns=[] (no history)
├─ Intent detected: "check_loan_eligibility"
├─ Route: loan_agent
├─ Loan agent processes: "I want a loan"
│  └─ Response: "Test eligibility? Yes or No?"
├─ TurnRecord created:
│  ├─ turn_number: 1
│  ├─ user_input: "I want a loan"
│  ├─ agent_routed_to: "loan_agent"
│  ├─ agent_response: "Test eligibility? Yes or No?"
│  └─ Added to conversation_context.turns
├─ Session state updated:
│  └─ waiting_for_input_type: "eligibility_answer"
│  └─ active_agent: "loan_agent"
└─ Turn 1 Complete

User says: "yes"
├─ Turn 2 Starts
├─ Check Session: waiting_for_input_type="eligibility_answer" ✓
├─ Ingestion: "yes" (ONLY THIS, NOT TURN 1!)
├─ Early Interception (NO orchestrator needed):
│  ├─ Detect: "yes" matches eligibility pattern
│  ├─ Generate: Redirect response + URL
├─ TurnRecord created:
│  ├─ turn_number: 2
│  ├─ user_input: "yes"
│  ├─ agent_routed_to: "eligibility_handler"
│  ├─ agent_response: "Click here: https://..."
│  └─ Added to conversation_context.turns
├─ Session state updated:
│  └─ conversation_active: false
│  └─ waiting_for_input_type: null
└─ Turn 2 Complete - End Call

ConversationContext stored:
├─ turns: [TurnRecord 1, TurnRecord 2]
├─ current_turn: 2
├─ conversation_active: false
└─ Can be replayed for debugging, analytics, or history
```

---

## Questions Answered

**Q: What if user asks something unrelated in turn 3?**
- ConversationContext not waiting for eligibility
- Message goes through full orchestrator
- Gets routed to KB or another agent
- New turn record created

**Q: What if app crashes and restarts?**
- Session persists in memory
- ConversationContext is in session
- On reconnect, user continues where they left off

**Q: What if user switches from loan to credit queries?**
- Turn records show full flow
- Each turn independent
- Orchestrator routes based on current intent + previous agent

**Q: How to prevent infinite loops?**
- Each TurnRecord has turn_number
- Can check: if same agent + same intent for 3 turns → escalate
- ConversationContext can track "max_turns_per_agent"

---

## Summary

This architecture transforms your system from **stateless message concatenation** to **stateful turn-based conversations**:

- ✅ Only current message processed through pipeline
- ✅ Full conversation available to agents who need it
- ✅ Each turn recorded for debugging/analytics
- ✅ Agents can make decisions based on conversation flow
- ✅ Eligibility detection works at router level, not re-analyzed

Ready to implement? I can start with any phase! 🎯
