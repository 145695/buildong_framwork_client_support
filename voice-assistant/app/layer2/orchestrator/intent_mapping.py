"""
Simple intent-to-agent mapping using your existing dataset format.
This converts your intent/category data to required agents.
"""

# Map your categories to required agents
# Updated architecture: knowledge_base, loan, client_support
CATEGORY_TO_AGENTS = {
    "security": ["knowledge_base", "client_support"], # Policy knowledge needed
    "fraud": ["knowledge_base", "client_support"], # Policy knowledge needed
    "account": ["client_support"], # General support
    "balance": ["client_support"], # General support
    "transaction": ["client_support"], # General support
    "loan": ["loan", "client_support"], # Loan specialist + support
    "credit": ["loan", "client_support"], # Loan specialist + support
    "general": ["client_support"], # Support only
    "policy": ["knowledge_base", "client_support"], # Policy knowledge needed
    "help": ["client_support"] # Support only
}

# Map specific intents to categories (fallback if not provided)
INTENT_TO_CATEGORY = {
    "fraud_report": "security",
    "lost_card": "security", 
    "compromised_account": "security",
    "check_balance": "balance",
    "account_inquiry": "account",
    "transaction_history": "transaction",
    "loan_application": "loan",
    "credit_inquiry": "credit",
    "policy_question": "policy",
    "general_help": "general"
}

def get_required_agents(intent: str, category: str = None) -> list[str]:
    """
    Convert your intent/category to required agents.
    
    Args:
        intent: Your intent from dataset
        category: Your category from dataset (optional)
    
    Returns:
        List of agent names to execute
    """
    # Use category if provided, otherwise map from intent
    if category:
        category = category.lower()
    else:
        category = INTENT_TO_CATEGORY.get(intent.lower(), "general")
    
    # Get agents for this category
    agents = CATEGORY_TO_AGENTS.get(category, ["client_support"])
    
    return agents

def get_priority(category: str) -> str:
    """Get priority based on category"""
    if category in ["loan", "credit"]:
        return "high"  # Loan applications are high priority
    elif category in ["security", "fraud", "policy"]:
        return "medium"  # Policy questions are medium priority
    else:
        return "low"  # General inquiries are low priority

def create_orchestrator_decision(intent: str, category: str = None) -> dict:
    """
    Create orchestrator decision from your intent/category data.
    
    This replaces the complex LLM with simple mapping.
    """
    if not category:
        category = INTENT_TO_CATEGORY.get(intent.lower(), "general")
    
    required_agents = get_required_agents(intent, category)
    priority = get_priority(category)
    
    return {
        "intent": intent,
        "category": category,
        "required_agents": required_agents,
        "priority": priority,
        "confidence": 0.85,  # Based on your dataset quality
        "extraction_method": "dataset_mapping"
    }
