"""
Agent Registry System
Provides semantic similarity-based agent routing using sentence transformers
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import numpy as np
from sentence_transformers import SentenceTransformer
import json
import os

@dataclass
class AgentInfo:
    """Information about a registered agent"""
    agent_id: str
    description: str
    embedding: np.ndarray

class AgentRegistry:
    """Registry for agent semantic matching"""
    
    def __init__(self):
        self.agents: Dict[str, AgentInfo] = {}
        self.embedder = None
        self._load_embedder()
    
    def _load_embedder(self):
        """Load sentence transformer model"""
        try:
            # Use multilingual model for better semantic understanding
            self.embedder = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
            print(f"✅ Agent registry loaded sentence transformer: paraphrase-multilingual-MiniLM-L12-v2")
        except Exception as e:
            print(f"⚠️  Failed to load sentence transformer: {e}")
            # Fallback to simple model
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
    
    def register(self, agent_id: str, description: str):
        """Register an agent with pre-computed embedding"""
        print(f"📝 Registering agent: {agent_id}")
        
        # Pre-compute embedding for the description
        embedding = self.embedder.encode(description, convert_to_tensor=True)
        embedding = embedding.cpu().numpy()
        
        self.agents[agent_id] = AgentInfo(
            agent_id=agent_id,
            description=description,
            embedding=embedding
        )
        
        print(f"✅ Registered agent {agent_id} with embedding shape: {embedding.shape}")
    
    def resolve(self, intent_label: str) -> str:
        """Resolve intent to best matching agent using semantic similarity"""
        if not self.agents:
            print("⚠️  No agents registered, falling back to client_support")
            return "client_support"
        
        if not self.embedder:
            print("⚠️  No embedder available, falling back to client_support")
            return "client_support"
        
        # Embed the intent label
        intent_embedding = self.embedder.encode(intent_label, convert_to_tensor=True)
        intent_embedding = intent_embedding.cpu().numpy()
        
        # Compute cosine similarity with all agent descriptions
        best_agent = "client_support"
        best_score = 0.0
        
        for agent_id, agent_info in self.agents.items():
            # Compute cosine similarity
            similarity = np.dot(intent_embedding, agent_info.embedding) / (
                np.linalg.norm(intent_embedding) * np.linalg.norm(agent_info.embedding)
            )
            
            print(f"🔍 Similarity score for {agent_id}: {similarity:.4f}")
            
            if similarity > best_score:
                best_score = similarity
                best_agent = agent_id
        
        print(f"🎯 Selected agent: {best_agent} (similarity: {best_score:.4f})")
        return best_agent
    
    def get_agent_info(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent information by ID"""
        return self.agents.get(agent_id)
    
    def list_agents(self) -> List[str]:
        """List all registered agent IDs"""
        return list(self.agents.keys())

# Module-level singleton
registry = AgentRegistry()

# Register active agents
def register_active_agents():
    """Register all active agents for similarity scoring"""
    
    # Register knowledge base agent
    registry.register(
        agent_id="kb_agent",
        description="""
            Answers questions about bank policies, procedures, fees, interest rates,
            regulatory compliance, account opening conditions, document requirements,
            banking regulations, product information, service explanations, Islamic
            compliance rules, and general banking advice.
        """
    )
    
    # Register loan agent
    registry.register(
        agent_id="loan_agent",
        description="""
            Handles all loan-related requests: personal loans, mortgage, housing loans,
            car loans, Islamic loans (murabaha, sukuk), loan repayment, credit applications,
            construction financing, loan amounts, guarantees,
            loan eligibility, financing for real estate or vehicles.
        """
    )
    
    # Register client support agent
    registry.register(
        agent_id="client_support",
        description="""
            Handles operational banking requests: blocked cards, card issues,
            PIN problems, transaction disputes, fraud, lost or stolen cards,
            account management, transfers, withdrawals, balance inquiries,
            complaints, and general customer support operations.
        """
    )

# Register agents when module is imported
register_active_agents()
