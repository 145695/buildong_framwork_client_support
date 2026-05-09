# Orchestrator & LangGraph Analysis

## Current Routing Logic

### 1. LLM Output Parsing
**Function**: `_llama_intent_extraction()`

**Two Response Formats**:
- **New Format**: `{'agent_to_call', 'agent_prompt', 'intent', 'category'}`
- **Old Format**: `{'intent', 'category', 'confidence'}`

**Agent Mapping**:
```python
agent_mapping = {
    'security_layer1': 'knowledge_base',
    'security_layer2': 'loan', 
    'authorization': 'loan',
    'support': 'client_support',
    'channel_refinement': 'client_support'
}
```

### 2. Agent Selection Logic
**Function**: `smart_pm_routing()`

**Process**:
1. Extract intent/category from Llama
2. Map agent names to standardized names
3. Find suitable agents via capability registry
4. Select primary agent (highest priority)
5. Generate mission briefs for ALL agents

**Priority System**:
- Primary agent = first in suitable_agents list
- Fallback = "client_support" if no agents found
- Always includes client_support for planning

### 3. Node Decision Flow
**No LangGraph Implementation** - Uses traditional function calls:

```
Input → Llama Extraction → Agent Selection → Mission Brief Generation → Planning Summary
```

**Key Functions**:
- `_llama_intent_extraction()` - LLM parsing
- `smart_pm_routing()` - Main orchestrator logic
- `analyze_agent_feedback()` - Multi-turn handling
- `route_intent()` - Entry point

### 4. Agent Capability Registry
**Agent Types**:
- `knowledge_base` - Policy retrieval
- `loan` - Loan evaluation  
- `client_support` - Response formatting

**Skills**:
- Policy retrieval/interpretation
- Loan evaluation
- Client interview
- Response synthesis

### 5. Multi-Turn Logic
**Special Handling for Loan Agent**:
- Awaits client info if needed
- Calls client_support after evaluation
- Manages conversation state

## Current Limitations
- No actual LangGraph implementation
- Planning mode only (no execution)
- Static agent mapping
- Limited feedback loops
