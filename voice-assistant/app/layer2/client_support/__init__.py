"""
Client Support Agent Module

Provides customer service functionality for BNA banking queries.
Uses LLaMA model to generate helpful responses based on knowledge base results.
"""

from .agent import client_support_node

__all__ = ['client_support_node']
