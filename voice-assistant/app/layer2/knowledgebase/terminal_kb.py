"""
Terminal Interface for French Banking Knowledge Base
Interactive command-line interface for testing
"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from intelligent_rag_system import IntelligentRAGSystem

def main():
    """Interactive terminal interface"""
    print("=" * 60)
    print("[TERMINAL] TERMINAL - BASE DE CONNAISSANCE BANCAIRE")
    print("=" * 60)
    print("Posez vos questions en français sur les sujets bancaires:")
    print("- Prêts et crédits")
    print("- Virements et transferts") 
    print("- Cartes bancaires")
    print("- Changements de compte")
    print("- Tapes 'quitter' pour sortir")
    print("=" * 60)
    
    try:
        # Initialize knowledge base
        print("Chargement de la base de connaissances...")
        kb = IntelligentRAGSystem()
        
        # Load documents asynchronously
        asyncio.run(kb.load_documents())
        
        print(f"[TERMINAL] {len(kb.documents)} documents chargés")
        print(f"[TERMINAL] {len(kb.document_chunks)} chunks traités")
        print(f"[TERMINAL] {len(kb.document_profiles)} profils générés")
        print()
        
        while True:
            try:
                # Get user input
                question = input("[TERMINAL] Votre question: ").strip()
                
                if question.lower() in ['quitter', 'exit', 'q', 'sortir']:
                    print("[TERMINAL] Au revoir!")
                    break
                
                if not question:
                    continue
                
                print(f"\n[TERMINAL] Recherche: {question}")
                print("-" * 40)
                
                # Process question (async)
                result = asyncio.run(kb.ask_question(question))
                
                # Display answer
                if result.get('needs_clarification'):
                    print(f"� Clarification: {result['answer']}")
                else:
                    print(f"�💡 Réponse: {result['answer']}")
                    print(f"[TERMINAL] Sources:")
                    for i, source in enumerate(result['sources'], 1):
                        print(f"   {i}. {source}")
                    print(f"[TERMINAL] Confiance: {result['confidence']:.0%}")
                    print(f"[TERMINAL] Documents trouves: {result['documents_found']}")
                
                # Display confidence
                confidence = result['confidence']
                if confidence > 0.7:
                    confidence_icon = "HIGH"
                elif confidence > 0.4:
                    confidence_icon = "MEDIUM"
                else:
                    confidence_icon = "LOW"
                
                print(f"\n[TERMINAL] Confiance: {confidence:.2f} {confidence_icon}")
                print(f"[TERMINAL] Documents trouves: {result['documents_found']}")
                print("=" * 60)
                
            except KeyboardInterrupt:
                print("\n[TERMINAL] Au revoir!")
                break
            except Exception as e:
                print(f"[TERMINAL] ERROR: Erreur: {e}")
                print("Veuillez réessayer.")
                print()
                
    except Exception as e:
        print(f"[TERMINAL] ERROR: Erreur d'initialisation: {e}")
        print("Vérifiez que le dossier 'policies' existe et contient des fichiers PDF.")

if __name__ == "__main__":
    main()
