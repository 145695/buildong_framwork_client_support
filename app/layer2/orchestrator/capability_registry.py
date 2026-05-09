"""
Capability Registry for Smart PM Orchestrator.

Defines worker agent capabilities, requirements, and skills for dynamic mission assignment.
"""

from typing import Dict, List, Any, Optional
from enum import Enum


class AgentCapabilityType(Enum):
    """Agent capability types"""
    KNOWLEDGE_BASE = "knowledge_base"
    LOAN = "loan"
    CLIENT_SUPPORT = "client_support"


class AgentRequirement(Enum):
    """Requirements for agent execution"""
    POLICY_ACCESS = "policy_access"
    CLIENT_DATA = "client_data"
    MULTI_TURN_CONVERSATION = "multi_turn_conversation"
    RESPONSE_SYNTHESIS = "response_synthesis"


class AgentSkill(Enum):
    """Specific skills agents possess"""
    POLICY_RETRIEVAL = "policy_retrieval"
    POLICY_INTERPRETATION = "policy_interpretation"
    LOAN_EVALUATION = "loan_evaluation"
    CLIENT_INTERVIEW = "client_interview"
    DATA_COLLECTION = "data_collection"
    RESPONSE_FORMATTING = "response_formatting"
    COMMUNICATION = "communication"
    ANSWER_SYNTHESIS = "answer_synthesis"



class AgentCapability:
    """Defines an agent's capabilities and requirements"""
    
    def __init__(
        self,
        name: str,
        capabilities: List[AgentCapabilityType],
        skills: List[AgentSkill],
        requirements: List[AgentRequirement],
        priority: int = 5,
        description: str = ""
    ):
        self.name = name
        self.capabilities = capabilities
        self.skills = skills
        self.requirements = requirements
        self.priority = priority  # Lower number = higher priority
        self.description = description
    
    def can_handle(self, intent: str, category: str, context: Dict[str, Any]) -> bool:
        """Check if agent can handle the given intent/category"""
        # This will be enhanced with smart matching logic
        return True  # Placeholder - will implement smart matching
    
    def get_mission_template(self, intent: str, category: str, context: Dict[str, Any]) -> str:
        """Generate mission brief template for this agent"""
        return f"""
        MISSION BRIEF: {self.name.upper()}
        
        OBJECTIVE:
        Process user request with intent: {intent} (category: {category})
        
        CONSTRAINTS:
        - Use your primary capabilities: {', '.join([cap.value for cap in self.capabilities])}
        - Apply your specialized skills: {', '.join([skill.value for skill in self.skills])}
        - Respect security requirements: {', '.join([req.value for req in self.requirements])}
        
        REQUIRED OUTPUT FORMAT:
        - Structured response with clear action items
        - Include confidence levels and next steps
        - Provide data for downstream agents if needed
        
        CONTEXT:
        {context}
        
        Execute mission with professional precision and user focus.
        """


# Registry of all available agents with their capabilities
CAPABILITY_REGISTRY = {
    "knowledge_base": AgentCapability(
        name="knowledge_base",
        capabilities=[AgentCapabilityType.KNOWLEDGE_BASE],
        skills=[AgentSkill.POLICY_RETRIEVAL, AgentSkill.POLICY_INTERPRETATION],
        requirements=[AgentRequirement.POLICY_ACCESS],
        priority=1,  # Highest priority for policy questions
        description="Knows all banking policies and procedures"
    ),
    
    "loan": AgentCapability(
        name="loan", 
        capabilities=[AgentCapabilityType.LOAN],
        skills=[AgentSkill.LOAN_EVALUATION, AgentSkill.CLIENT_INTERVIEW, AgentSkill.DATA_COLLECTION],
        requirements=[AgentRequirement.CLIENT_DATA, AgentRequirement.MULTI_TURN_CONVERSATION],
        priority=2,  # Second priority
        description="Specialized in loan approval decisions with multi-turn info collection"
    ),
    
    "loan_agent": AgentCapability(
        name="loan_agent", 
        capabilities=[AgentCapabilityType.LOAN],
        skills=[AgentSkill.LOAN_EVALUATION, AgentSkill.CLIENT_INTERVIEW, AgentSkill.DATA_COLLECTION],
        requirements=[AgentRequirement.CLIENT_DATA, AgentRequirement.MULTI_TURN_CONVERSATION],
        priority=2,  # Second priority
        description="Specialized in loan approval decisions with multi-turn info collection"
    ),
    
    "client_support": AgentCapability(
        name="client_support",
        capabilities=[AgentCapabilityType.CLIENT_SUPPORT],
        skills=[AgentSkill.RESPONSE_FORMATTING, AgentSkill.COMMUNICATION, AgentSkill.ANSWER_SYNTHESIS],
        requirements=[AgentRequirement.RESPONSE_SYNTHESIS],
        priority=3,  # Always included, runs last
        description="Manages operational banking requests: card issues, account management, transfers, withdrawals, complaints, identity verification, blocked cards, account unblocking, transaction disputes, PIN issues, balance inquiries, and general customer support"
    ),
}


def get_agent_capability(agent_name: str) -> Optional[AgentCapability]:
    """Get agent capability from registry"""
    return CAPABILITY_REGISTRY.get(agent_name)


def find_suitable_agents(
    intent: str, 
    category: str, 
    context: Dict[str, Any]
) -> List[AgentCapability]:
    """Find agents suitable for handling the given intent/category"""
    suitable_agents = []
    
    for agent_name, agent_cap in CAPABILITY_REGISTRY.items():
        if agent_cap.can_handle(intent, category, context):
            suitable_agents.append(agent_cap)
    
    # Sort by priority (lower number = higher priority)
    suitable_agents.sort(key=lambda x: x.priority)
    return suitable_agents


def get_required_agents_for_intent(intent: str, category: str) -> List[str]:
    """Get list of agent names required for an intent"""
    # Smart matching based on intent patterns
    policy_keywords = ["policy", "procedure", "regulation", "rule", "guideline"]
    loan_keywords = ["loan", "credit", "approve", "application", "mortgage", "financing"]
    card_keywords = ["card", "block", "blocked", "unblock", "pin", "transaction", "dispute", "fraud", "lost", "stolen"]
    account_keywords = ["account", "balance", "statement", "transfer", "withdrawal", "deposit", "inquiry"]
    support_keywords = ["help", "question", "issue", "problem", "complaint", "assistance"]
    
    intent_lower = intent.lower()
    category_lower = category.lower()
    
    if any(keyword in intent_lower for keyword in policy_keywords):
        return ["knowledge_base", "client_support"]
    elif any(keyword in intent_lower for keyword in loan_keywords):
        return ["loan", "client_support"]
    elif any(keyword in intent_lower for keyword in card_keywords):
        return ["client_support"]
    elif any(keyword in intent_lower for keyword in account_keywords):
        return ["client_support"]
    elif any(keyword in intent_lower for keyword in support_keywords):
        return ["client_support"]
    else:
        return ["client_support"]


def generate_mission_brief(
    agent_name: str,
    intent: str,
    category: str,
    context: Dict[str, Any],
    previous_feedback: Dict[str, Any] = None
) -> str:
    """Generate dynamic mission brief for an agent"""
    agent_cap = get_agent_capability(agent_name)
    if not agent_cap:
        return f"MISSION: Execute {agent_name} for intent: {intent}"
    
    # Include feedback from previous agents if available
    feedback_context = ""
    if previous_feedback:
        feedback_context = f"""
        
        PREVIOUS AGENT FEEDBACK:
        {previous_feedback}
        
        ADJUST MISSION BASED ON FEEDBACK:
        - Address any gaps or issues identified
        - Build upon previous results
        - Ensure seamless handoff
        """
    
    return agent_cap.get_mission_template(intent, category, context) + feedback_context
