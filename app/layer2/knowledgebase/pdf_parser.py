"""
PDF Document Parser for Banking Policy Documents

Uses pdfplumber to extract text from PDF files in the policies directory.
Lightweight and efficient, no GPU required.
"""

import os
import pdfplumber
from pathlib import Path
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class PDFParser:
    """Parse PDF documents and extract text content"""
    
    def __init__(self, policies_dir: str = None):
        if policies_dir is None:
            # Default to project root policies directory
            policies_dir = Path(__file__).parent.parent.parent.parent / "policies"
        self.policies_dir = Path(policies_dir)
        self.documents = []
        
    def extract_text_from_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract text from a single PDF file"""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text_content = []
                metadata = {
                    "filename": pdf_path.name,
                    "page_count": len(pdf.pages),
                    "file_size": pdf_path.stat().st_size
                }
                
                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_content.append({
                                "page": page_num,
                                "text": page_text.strip()
                            })
                    except Exception as e:
                        logger.warning(f"Error extracting text from page {page_num} in {pdf_path.name}: {e}")
                        continue
                
                full_text = "\n\n".join([page["text"] for page in text_content])
                
                return {
                    "content": full_text,
                    "metadata": metadata,
                    "pages": text_content,
                    "source": str(pdf_path)
                }
                
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path.name}: {e}")
            return None
    
    def load_all_pdfs(self) -> List[Dict[str, Any]]:
        """Load and parse all PDF files in the policies directory"""
        if not self.policies_dir.exists():
            logger.error(f"Policies directory not found: {self.policies_dir}")
            return []
        
        pdf_files = list(self.policies_dir.glob("*.pdf"))
        if not pdf_files:
            logger.warning(f"No PDF files found in {self.policies_dir}")
            return []
        
        documents = []
        
        for pdf_path in pdf_files:
            logger.info(f"Processing PDF: {pdf_path.name}")
            doc = self.extract_text_from_pdf(pdf_path)
            if doc:
                documents.append(doc)
                logger.info(f"Successfully extracted {len(doc['pages'])} pages from {pdf_path.name}")
        
        self.documents = documents
        logger.info(f"Loaded {len(documents)} PDF documents")
        return documents
    
    def get_documents_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Filter documents by category based on filename patterns"""
        category_keywords = {
            "loans": ["loan", "credit", "financement", "قرض", "تمويل"],
            "deposits": ["deposit", "versement", "transfer", "إيداع", "تحويل", "تحويلات"],
            "cards": ["card", "carte", "بطاقة", "بطاقات"],
            "accounts": ["account", "compte", "حساب", "تغييرات"]
        }
        
        if category.lower() not in category_keywords:
            return self.documents
        
        keywords = category_keywords[category.lower()]
        filtered_docs = []
        
        for doc in self.documents:
            filename = doc["metadata"]["filename"].lower()
            content = doc["content"].lower()
            
            # Check if any keyword matches in filename or content
            if any(keyword in filename or keyword in content for keyword in keywords):
                filtered_docs.append(doc)
        
        return filtered_docs
    
    def search_documents(self, query: str) -> List[str]:
        """Simple text search across all documents"""
        query_lower = query.lower()
        matching_texts = []
        
        for doc in self.documents:
            if query_lower in doc["content"].lower():
                # Extract relevant snippets around the query
                content = doc["content"]
                start_idx = content.lower().find(query_lower)
                if start_idx != -1:
                    # Get context around the match (200 chars before and after)
                    start = max(0, start_idx - 200)
                    end = min(len(content), start_idx + len(query) + 200)
                    snippet = content[start:end].strip()
                    matching_texts.append(f"[{doc['metadata']['filename']}] {snippet}")
        
        return matching_texts


# Test function
def test_pdf_parser():
    """Test the PDF parser with the policies directory"""
    parser = PDFParser()
    documents = parser.load_all_pdfs()
    
    print(f"Loaded {len(documents)} documents:")
    for doc in documents:
        print(f"- {doc['metadata']['filename']} ({doc['metadata']['page_count']} pages)")
    
    # Test category filtering
    loan_docs = parser.get_documents_by_category("loans")
    print(f"\nFound {len(loan_docs)} loan-related documents")
    
    # Test search
    search_results = parser.search_documents("loan")
    print(f"\nSearch results for 'loan': {len(search_results)} matches")
    
    return documents


if __name__ == "__main__":
    test_pdf_parser()
