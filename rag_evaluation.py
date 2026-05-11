"""
RAG Evaluation System for BNA Knowledge Base
Evaluates Retrieval-Augmented Generation pipeline with comprehensive metrics
"""

import asyncio
import time
import csv
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple
import logging

# Add project root to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# Import RAG system
from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem
from app.layer2.knowledgebase.mistral_llm import MistralLLM

# Test questions based on actual policy content
TEST_QUESTIONS = [
    # Account Opening & Fees (7 questions)
    "What are the fees for opening a checking account for individuals?",
    "How much does it cost annually to maintain a savings account?",
    "What are the fees for account management for junior savings accounts?",
    "What are the charges for dormant accounts without transactions?",
    "How much does it cost to request an account history statement?",
    "What are the fees for closing an account?",
    "How much do bank transfers cost between agencies?",
    
    # Cash Operations & Services (6 questions)
    "What are the fees for cash withdrawals at other branches?",
    "How much do cash deposits to savings accounts cost?",
    "What are the fees for check opposition and cash book stops?",
    "How much does it cost to process succession documents?",
    "What are the charges for document photocopying at the bank?",
    "How much do account research fees cost per document?",
    
    # Mortgage Loans (7 questions)
    "What is the maximum financing percentage for real estate loans?",
    "What are the interest rates for real estate loans without bonuses?",
    "What interest rates apply to saving customers for real estate loans?",
    "What are the interest rates for borrowers under 40 years old?",
    "What is the maximum duration for real estate loans?",
    "How long does it take to process a real estate loan application?",
    "What is the maximum amount for 100% financing for young borrowers?",
    
    # Loan Eligibility & Conditions (6 questions)
    "What are the eligibility criteria for real estate loans?",
    "What is the age limit for real estate loan applicants?",
    "What income requirements exist for real estate loans?",
    "What repayment deferral periods are available for different loan types?",
    "Can co-borrowers be included to increase loan capacity?",
    "What are the fees for consumer and real estate loan applications?"
]

class RAGEvaluator:
    """Comprehensive RAG evaluation system"""
    
    def __init__(self):
        self.rag_system = None
        self.llm = None
        self.results = []
        
    async def initialize(self):
        """Initialize RAG system and LLM"""
        print("🚀 Initializing RAG evaluation system...")
        
        # Initialize RAG system
        self.rag_system = IntelligentRAGSystem()
        await self.rag_system.load_documents()
        
        # Initialize LLM for evaluation
        self.llm = MistralLLM(model_name="mistral-small", temperature=0)
        
        print(f"✅ RAG system ready with {len(self.rag_system.document_chunks)} chunks")
        print(f"✅ LLM evaluator ready")
        
    async def evaluate_retrieval_precision(self, question: str, retrieved_chunks: List[Dict], k: int = 5) -> float:
        """Evaluate Retrieval Precision@k using LLM relevance judgment"""
        relevant_count = 0
        
        for i, chunk in enumerate(retrieved_chunks[:k]):
            chunk_content = chunk.get('content', '')[:500]  # Limit content length
            
            prompt = f"""Is this chunk relevant to the question? Answer yes or no.

Question: {question}

Chunk: {chunk_content}

Answer only: yes or no"""
            
            try:
                response = await self.llm.ainvoke(prompt)
                answer = response.content.strip().lower()
                if answer == 'yes':
                    relevant_count += 1
                    print(f"  Chunk {i+1}: ✅ Relevant")
                else:
                    print(f"  Chunk {i+1}: ❌ Not relevant")
                    
            except Exception as e:
                print(f"  Chunk {i+1}: ⚠️ Error evaluating: {e}")
                # Conservative approach: count as not relevant
                continue
        
        precision = relevant_count / k if k > 0 else 0.0
        print(f"  Precision@{k}: {relevant_count}/{k} = {precision:.3f}")
        return precision
    
    async def evaluate_answer_relevance(self, question: str, answer: str) -> float:
        """Evaluate Answer Relevance Score using LLM rating (1-5 scale)"""
        if not answer or answer.strip() == "":
            return 0.0
            
        prompt = f"""On a scale of 1 to 5, how relevant is this answer to the question?
1 = Not relevant at all
2 = Slightly relevant
3 = Moderately relevant
4 = Highly relevant
5 = Perfectly relevant

Question: {question}

Answer: {answer}

Reply with only a number from 1 to 5."""
        
        try:
            response = await self.llm.ainvoke(prompt)
            score_text = response.content.strip()
            
            # Extract number from response
            import re
            match = re.search(r'\d+', score_text)
            if match:
                score = int(match.group())
                # Normalize to 0-1 scale
                normalized_score = (score - 1) / 4
                print(f"  Relevance Score: {score}/5 = {normalized_score:.3f}")
                return normalized_score
            else:
                print(f"  ⚠️ Could not parse relevance score: {score_text}")
                return 0.5  # Default to middle value
                
        except Exception as e:
            print(f"  ⚠️ Error evaluating relevance: {e}")
            return 0.5
    
    async def evaluate_faithfulness(self, answer: str, retrieved_chunks: List[Dict]) -> bool:
        """Evaluate Faithfulness Score using context grounding check"""
        if not answer or answer.strip() == "":
            return False
            
        # Combine retrieved chunks for context
        context = "\n\n".join([
            f"Document {i+1}: {chunk.get('content', '')[:300]}"
            for i, chunk in enumerate(retrieved_chunks[:5])
        ])
        
        prompt = f"""Is this answer fully supported by the following context?
Answer yes only if the answer is completely based on the provided context.
Answer no if the answer contains information not present in the context.

Context:
{context}

Answer: {answer}

Reply with only: yes or no"""
        
        try:
            response = await self.llm.ainvoke(prompt)
            answer_text = response.content.strip().lower()
            is_faithful = answer_text == 'yes'
            print(f"  Faithfulness: {'✅ Faithful' if is_faithful else '❌ Not faithful'}")
            return is_faithful
            
        except Exception as e:
            print(f"  ⚠️ Error evaluating faithfulness: {e}")
            return False
    
    async def run_single_evaluation(self, question: str, question_id: int) -> Dict[str, Any]:
        """Run full RAG evaluation for a single question"""
        print(f"\n📝 Evaluating Question {question_id}: {question}")
        print("-" * 80)
        
        # Measure latency
        start_time = time.time()
        
        try:
            # Run RAG pipeline
            result = await self.rag_system.ask_question(question)
            
            # Extract retrieved chunks from RAG system
            retrieved_chunks = result.get('retrieved_chunks', [])
            if not retrieved_chunks and 'sources' in result and result['sources']:
                # Fallback if retrieved_chunks not available
                for source in result['sources'][:5]:
                    retrieved_chunks.append({
                        'filename': source,
                        'content': f"Content from {source}"  # Placeholder
                    })
            
            # Get answer
            answer = result.get('answer', '')
            
            # Measure latency
            end_time = time.time()
            latency = end_time - start_time
            
            print(f"  ⏱️  Latency: {latency:.3f} seconds")
            print(f"  📄 Answer: {answer[:200]}...")
            print(f"  📚 Sources: {result.get('sources', [])}")
            
            # Evaluate metrics
            print("\n🔍 Evaluating metrics...")
            
            # Retrieval Precision@k (using k=5)
            precision_score = await self.evaluate_retrieval_precision(question, retrieved_chunks, k=5)
            
            # Answer Relevance Score
            relevance_score = await self.evaluate_answer_relevance(question, answer)
            
            # Faithfulness Score
            faithfulness_score = await self.evaluate_faithfulness(answer, retrieved_chunks)
            
            # Compile results
            evaluation_result = {
                'question_id': question_id,
                'question': question,
                'answer': answer,
                'sources': result.get('sources', []),
                'confidence': result.get('confidence', 0.0),
                'documents_found': result.get('documents_found', 0),
                'latency_seconds': latency,
                'retrieval_precision_at_5': precision_score,
                'answer_relevance_score': relevance_score,
                'faithfulness_score': faithfulness_score,
                'retrieved_chunks_count': len(retrieved_chunks)
            }
            
            self.results.append(evaluation_result)
            return evaluation_result
            
        except Exception as e:
            print(f"  ❌ Error evaluating question {question_id}: {e}")
            error_result = {
                'question_id': question_id,
                'question': question,
                'answer': '',
                'sources': [],
                'confidence': 0.0,
                'documents_found': 0,
                'latency_seconds': 0.0,
                'retrieval_precision_at_5': 0.0,
                'answer_relevance_score': 0.0,
                'faithfulness_score': False,
                'retrieved_chunks_count': 0,
                'error': str(e)
            }
            self.results.append(error_result)
            return error_result
    
    async def run_full_evaluation(self):
        """Run evaluation on all test questions"""
        print("🎯 Starting RAG Evaluation on 20 Banking Questions")
        print("=" * 80)
        
        for i, question in enumerate(TEST_QUESTIONS, 1):
            await self.run_single_evaluation(question, i)
            
            # Add small delay to avoid API rate limits
            await asyncio.sleep(0.5)
        
        print("\n" + "=" * 80)
        print("✅ Evaluation Complete!")
    
    def compute_summary_metrics(self) -> Dict[str, Any]:
        """Compute summary statistics from all results"""
        if not self.results:
            return {}
        
        # Filter out error results
        valid_results = [r for r in self.results if 'error' not in r]
        
        if not valid_results:
            return {
                'retrieval_precision_at_5': 0.0,
                'answer_relevance_score': 0.0,
                'faithfulness_score': 0.0,
                'avg_latency_seconds': 0.0,
                'total_questions': len(self.results),
                'successful_evaluations': 0
            }
        
        # Compute averages
        retrieval_precision = np.mean([r['retrieval_precision_at_5'] for r in valid_results])
        answer_relevance = np.mean([r['answer_relevance_score'] for r in valid_results])
        faithfulness = np.mean([r['faithfulness_score'] for r in valid_results]) * 100  # Convert to percentage
        latencies = [r['latency_seconds'] for r in valid_results]
        avg_latency = np.mean(latencies)
        std_latency = np.std(latencies)
        
        return {
            'retrieval_precision_at_5': retrieval_precision,
            'answer_relevance_score': answer_relevance,
            'faithfulness_score': faithfulness,
            'avg_latency_seconds': avg_latency,
            'std_latency_seconds': std_latency,
            'total_questions': len(self.results),
            'successful_evaluations': len(valid_results)
        }
    
    def print_summary_table(self, metrics: Dict[str, Any]):
        """Print formatted summary table"""
        print("\n" + "=" * 80)
        print("📊 RAG EVALUATION SUMMARY")
        print("=" * 80)
        print(f"{'Metric':<25} | {'Value':<10} | {'Notes'}")
        print("-" * 80)
        print(f"{'Retrieval Precision@5':<25} | {metrics['retrieval_precision_at_5']:<10.3f} | k=5, avg over {metrics['successful_evaluations']} questions")
        print(f"{'Answer Relevance Score':<25} | {metrics['answer_relevance_score']:<10.3f} | scale 0-1, avg over {metrics['successful_evaluations']} questions")
        print(f"{'Faithfulness Score':<25} | {metrics['faithfulness_score']:<10.1f}% | % answers grounded in context")
        print(f"{'Avg Response Latency':<25} | {metrics['avg_latency_seconds']:<10.3f}s | mean ± {metrics['std_latency_seconds']:.3f}s over {metrics['successful_evaluations']} questions")
        print("-" * 80)
        print(f"Total Questions: {metrics['total_questions']}")
        print(f"Successful Evaluations: {metrics['successful_evaluations']}")
        if metrics['total_questions'] > metrics['successful_evaluations']:
            failed = metrics['total_questions'] - metrics['successful_evaluations']
            print(f"Failed Evaluations: {failed}")
    
    def save_results_to_csv(self, filename: str = "rag_evaluation_results.csv"):
        """Save detailed results to CSV file"""
        if not self.results:
            print("❌ No results to save")
            return
        
        fieldnames = [
            'question_id', 'question', 'answer', 'sources', 'confidence',
            'documents_found', 'latency_seconds', 'retrieval_precision_at_5',
            'answer_relevance_score', 'faithfulness_score', 'retrieved_chunks_count'
        ]
        
        # Add error field if present
        if any('error' in r for r in self.results):
            fieldnames.append('error')
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in self.results:
                # Convert lists to strings for CSV
                row = result.copy()
                if 'sources' in row:
                    row['sources'] = '; '.join(row['sources'])
                writer.writerow(row)
        
        print(f"✅ Results saved to {filename}")

async def main():
    """Main evaluation function"""
    evaluator = RAGEvaluator()
    
    try:
        # Initialize systems
        await evaluator.initialize()
        
        # Run full evaluation
        await evaluator.run_full_evaluation()
        
        # Compute and display summary
        metrics = evaluator.compute_summary_metrics()
        evaluator.print_summary_table(metrics)
        
        # Save detailed results
        evaluator.save_results_to_csv()
        
    except Exception as e:
        print(f"❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
