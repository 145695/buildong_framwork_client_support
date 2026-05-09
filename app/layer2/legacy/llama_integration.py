"""
Llama model integration for Smart PM Orchestrator.

Integrates the fine-tuned Llama model running on Google Colab Gradio API.
"""

import os
import json
import logging
import requests
from gradio_client import Client
from typing import Dict, Any, Optional


class LlamaOrchestrator:
    """Fine-tuned Llama model for intent/category extraction using Colab Gradio API"""
    
    def __init__(self):
        # Colab Gradio API endpoint
        self.colab_gradio_url = "https://4c436255a3c5f74808.gradio.live"
        self.client = None
        self._load_model()
    
    def _load_model(self):
        """Load the model using gradio_client (remote access to Colab Gradio API)"""
        try:
            print(f"Connecting to Colab Gradio API: {self.colab_gradio_url}")
            print("Using remote Gradio API (no local download)")
            
            # Use gradio_client for remote access to Colab
            self.client = Client(self.colab_gradio_url)
            
            print(f"Connected successfully to Colab Gradio API: {self.colab_gradio_url}")
            return True
            
        except Exception as e:
            print(f"Error connecting to Colab Gradio API: {e}")
            print("Falling back to rule-based logic")
            return False
    
    def extract_intent_category(self, user_query: str) -> Dict[str, Any]:
        """
        Extract intent and category from user query using Colab Gradio API
        
        Args:
            user_query: User input text
            
        Returns:
            Dict with category, intent, agent_to_call, agent_prompt
        """
        if not self.client:
            # Fallback to rule-based logic
            return self._fallback_extraction(user_query)
        
        try:
            # Call the Colab Gradio API
            result = self.client.predict(
                user_query=user_query,
                api_name="/predict"
            )
            
            # Parse the result
            if isinstance(result, dict):
                return result
            elif isinstance(result, str):
                # Try to parse JSON string
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    # Fallback if JSON parsing fails
                    return self._fallback_extraction(user_query)
            else:
                return self._fallback_extraction(user_query)
                
        except Exception as e:
            print(f"Error calling Colab Gradio API: {e}")
            return self._fallback_extraction(user_query)
    
    def _fallback_extraction(self, user_query: str) -> Dict[str, Any]:
        """Fallback rule-based intent extraction"""
        query_lower = user_query.lower()
        
        # Simple rule-based logic
        if any(word in query_lower for word in ["loan", "borrow", "credit", "mortgage"]):
            return {
                'category': 'loan',
                'intent': 'loan_application',
                'agent_to_call': 'authorization',
                'agent_prompt': f'Process loan application: {user_query}',
                'extraction_method': 'fallback_rules',
                'model_used': None
            }
        elif any(word in query_lower for word in ["account", "balance", "transfer"]):
            return {
                'category': 'account',
                'intent': 'account_inquiry',
                'agent_to_call': 'knowledge_base',
                'agent_prompt': f'Handle account inquiry: {user_query}',
                'extraction_method': 'fallback_rules',
                'model_used': None
            }
        else:
            return {
                'category': 'general',
                'intent': 'general_inquiry',
                'agent_to_call': 'knowledge_base',
                'agent_prompt': f'Handle general inquiry: {user_query}',
                'extraction_method': 'fallback_rules',
                'model_used': None
            }
