#!/usr/bin/env python3
"""
Comprehensive Full Pipeline Test Script
Tests all layers with realistic banking client questions
"""

import requests
import json
import time
from pathlib import Path

def test_full_pipeline():
    """Test full pipeline with realistic banking questions"""
    
    print("🏦 Testing Full Pipeline with Banking Questions")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    # Realistic banking client questions
    test_questions = [
        {
            "question": "I need to open a new bank account, what documents do I need?",
            "expected_agent": "client_support",
            "category": "account_management"
        },
        {
            "question": "What are the current interest rates for personal loans?",
            "expected_agent": "loan_agent", 
            "category": "loan_inquiry"
        },
        {
            "question": "I want to apply for a mortgage, what's the process?",
            "expected_agent": "loan_agent",
            "category": "mortgage_application"
        },
        {
            "question": "There's an unauthorized charge on my credit card, how do I dispute it?",
            "expected_agent": "client_support",
            "category": "fraud_dispute"
        },
        {
            "question": "What are the fees for international wire transfers?",
            "expected_agent": "client_support", 
            "category": "transfer_inquiry"
        },
        {
            "question": "I need information about Islamic banking products (murabaha, sukuk)",
            "expected_agent": "kb_agent",
            "category": "islamic_finance"
        },
        {
            "question": "How do I check my account balance online?",
            "expected_agent": "client_support",
            "category": "balance_inquiry"
        },
        {
            "question": "What are the requirements for business loan applications?",
            "expected_agent": "loan_agent",
            "category": "business_loan"
        },
        {
            "question": "I lost my debit card, what should I do immediately?",
            "expected_agent": "client_support",
            "category": "card_issues"
        },
        {
            "question": "What are the conditions for car financing?",
            "expected_agent": "loan_agent",
            "category": "vehicle_financing"
        }
    ]
    
    print(f"📋 Testing {len(test_questions)} realistic banking scenarios")
    print("-" * 40)
    
    results = {
        "total_tests": len(test_questions),
        "passed": 0,
        "failed": 0,
        "details": []
    }
    
    # Test each question
    for i, test_case in enumerate(test_questions, 1):
        print(f"\n🔍 Test {i}/{len(test_questions)}")
        print(f"Question: {test_case['question']}")
        print(f"Expected Agent: {test_case['expected_agent']}")
        print(f"Category: {test_case['category']}")
        print("-" * 40)
        
        try:
            # Send request to voice pipeline (simulating text input)
            start_time = time.time()
            
            response = requests.post(
                f"{base_url}/test/voice-full-pipeline",
                json={
                    "text": test_case["question"],
                    "source_language": "en"
                },
                timeout=30
            )
            
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if response is successful
                if data.get("success", False):
                    print("❌ Pipeline failed")
                    results["failed"] += 1
                    results["details"].append({
                        "test": i,
                        "question": test_case["question"],
                        "status": "failed",
                        "error": data.get("error", "Unknown error")
                    })
                else:
                    # Analyze pipeline response
                    stages = data.get("stages", {})
                    
                    # Check which agents were called
                    actual_agents = []
                    if stages.get("orchestrator"):
                        orchestrator_result = stages["orchestrator"]
                        actual_agents.append(orchestrator_result.get("selected_agent", "unknown"))
                    
                    if stages.get("knowledge_base"):
                        actual_agents.append("knowledge_base")
                    
                    if stages.get("client_support"):
                        actual_agents.append("client_support")
                    
                    # Check if expected agent was called
                    expected_found = test_case["expected_agent"] in actual_agents
                    
                    if expected_found:
                        print(f"✅ Success - Expected agent '{test_case['expected_agent']}' was called")
                        print(f"📊 Actual agents called: {', '.join(actual_agents)}")
                        print(f"⏱ Response time: {elapsed_time:.2f}s")
                        
                        results["passed"] += 1
                        results["details"].append({
                            "test": i,
                            "question": test_case["question"],
                            "status": "passed",
                            "expected_agent": test_case["expected_agent"],
                            "actual_agents": actual_agents,
                            "response_time": elapsed_time
                        })
                    else:
                        print(f"⚠️  Unexpected - Expected '{test_case['expected_agent']}' but got: {', '.join(actual_agents)}")
                        results["failed"] += 1
                        results["details"].append({
                            "test": i,
                            "question": test_case["question"],
                            "status": "unexpected_routing",
                            "expected_agent": test_case["expected_agent"],
                            "actual_agents": actual_agents,
                            "response_time": elapsed_time
                        })
                    
                    # Print stage details for debugging
                    for stage_name, stage_data in stages.items():
                        if stage_name != "knowledge_base":  # Skip KB for now
                            status = "✅" if stage_data.get("success") else "❌"
                            print(f"   {stage_name}: {status}")
                            if "answer" in stage_data:
                                answer_preview = stage_data["answer"][:100] + "..." if len(stage_data["answer"]) > 100 else stage_data["answer"]
                                print(f"      Answer: {answer_preview}")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                results["failed"] += 1
                results["details"].append({
                    "test": i,
                    "question": test_case["question"],
                    "status": "http_error",
                    "error": f"HTTP {response.status_code}"
                })
                
        except requests.exceptions.Timeout:
            print(f"⏱ Timeout after {elapsed_time:.2f}s")
            results["failed"] += 1
            results["details"].append({
                "test": i,
                "question": test_case["question"],
                "status": "timeout",
                "error": "Request timeout"
            })
            
        except Exception as e:
            print(f"❌ Exception: {e}")
            results["failed"] += 1
            results["details"].append({
                "test": i,
                "question": test_case["question"],
                "status": "exception",
                "error": str(e)
            })
        
        time.sleep(1)  # Small delay between requests
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print(f"Total Tests: {results['total_tests']}")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"Success Rate: {results['passed']/results['total_tests']*100:.1f}%")
    
    print("\n📋 DETAILED RESULTS:")
    for detail in results["details"]:
        status_icon = "✅" if detail["status"] == "passed" else "❌"
        print(f"{status_icon} Test {detail['test']}: {detail['status']}")
        print(f"   Question: {detail['question']}")
        if detail["status"] == "passed":
            print(f"   Expected: {detail['expected_agent']}")
            print(f"   Actual: {', '.join(detail['actual_agents'])}")
            print(f"   Time: {detail['response_time']:.2f}s")
        else:
            print(f"   Error: {detail['error']}")
    
    # Save results to file
    results_file = Path("test_results.json")
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {results_file}")
    print("🏁 Full Pipeline Test Complete!")

if __name__ == "__main__":
    test_full_pipeline()
