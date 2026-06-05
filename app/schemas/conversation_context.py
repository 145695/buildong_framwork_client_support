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
    eligibility_declined: bool = False  # User declined eligibility test, don't ask again
    
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
