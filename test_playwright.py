#!/usr/bin/env python3
"""
OxData Playwright Test - Chat Flow Testing
Uses venv Python for Streamlit
"""

import os
import sys
import time
import subprocess
import json
from pathlib import Path

# Get venv streamlit
VENV_STREAMLIT = str(Path(__file__).parent / ".venv" / "Scripts" / "streamlit.exe")
VENV_PYTHON = str(Path(__file__).parent / ".venv" / "Scripts" / "python.exe")

# Test questions that simulate a conversation with context
TEST_CONVERSATION = [
    "compare crompton and bajaj nps",  # First question
    "what is Crompton NPS?",           # Follow-up - should maintain context
    "show me the promoters for Bajaj", # Another follow-up
]

def start_streamlit():
    """Start streamlit and return the process"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent)
    
    proc = subprocess.Popen(
        [VENV_STREAMLIT, "run", "app.py", 
         "--server.headless=true", 
         "--server.port=8501",
         "--server.address=127.0.0.1"],
        cwd=str(Path(__file__).parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    )
    return proc

def run_playwright_tests():
    from playwright.sync_api import sync_playwright
    
    results = []
    
    print("Starting Streamlit with venv Python...")
    proc = start_streamlit()
    
    # Wait for Streamlit to start
    print("Waiting 20 seconds for Streamlit to initialize...")
    time.sleep(20)
    
    # Check if process is running
    if proc.poll() is not None:
        print("Streamlit process died!")
        stdout, _ = proc.communicate()
        print("STDOUT:", stdout[-2000:] if stdout else "No output")
        return results
    
    print("Streamlit should be running, connecting with Playwright...")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1400, "height": 900}
            )
            page = context.new_page()
            
            for i, question in enumerate(TEST_CONVERSATION):
                print(f"\n--- Question {i+1}: {question} ---")
                
                try:
                    # Navigate to app
                    page.goto("http://127.0.0.1:8501", timeout=30000)
                    page.wait_for_load_state("networkidle", timeout=15000)
                    print("Page loaded")
                    
                    # Wait for chat input
                    page.wait_for_selector("input[type=text]", timeout=10000)
                    print("Input found")
                    
                    # Type question
                    page.fill("input[type=text]", question)
                    print("Question typed")
                    
                    # Press enter
                    page.press("input[type=text]", "Enter")
                    print("Question submitted")
                    
                    # Wait for response - longer for LLM processing
                    time.sleep(12)
                    
                    # Check for errors
                    errors = page.locator(".stException, .stError").all()
                    if errors:
                        error_text = errors[0].inner_text()
                        results.append({
                            "question": question,
                            "status": "error",
                            "error": error_text[:200]
                        })
                        print(f"ERROR: {error_text[:100]}")
                        continue
                    
                    # Get response content
                    tables = page.locator("table").all()
                    metrics = page.locator("[data-testid='stMetricValue']").all()
                    
                    response_data = {
                        "tables_found": len(tables),
                        "metrics_found": len(metrics)
                    }
                    
                    if tables or metrics:
                        results.append({
                            "question": question,
                            "status": "success",
                            "data": response_data
                        })
                        print(f"SUCCESS - Tables: {len(tables)}, Metrics: {len(metrics)}")
                    else:
                        main_content = page.locator("main").inner_text()[:200] if page.locator("main").count() else ""
                        results.append({
                            "question": question,
                            "status": "no_data",
                            "content": main_content
                        })
                        print(f"No data found. Content: {main_content[:100]}")
                    
                except Exception as e:
                    results.append({
                        "question": question,
                        "status": "error",
                        "error": str(e)[:200]
                    })
                    print(f"ERROR: {str(e)[:100]}")
                
                if i < len(TEST_CONVERSATION) - 1:
                    print("Waiting 5 seconds before next question...")
                    time.sleep(5)
            
            browser.close()
            
    except Exception as e:
        print(f"Playwright error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\nStopping Streamlit...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except:
            proc.kill()
    
    return results

def main():
    print("=" * 60)
    print("OxData Playwright Test - Chat Flow")
    print("=" * 60)
    print(f"Using venv Streamlit: {VENV_STREAMLIT}")
    
    results = run_playwright_tests()
    
    output_file = Path(__file__).parent / "test_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    
    success = sum(1 for r in results if r["status"] == "success")
    errors = sum(1 for r in results if r["status"] == "error")
    no_data = sum(1 for r in results if r["status"] == "no_data")
    
    print(f"Total: {len(results)}")
    print(f"Success: {success}")
    print(f"Errors: {errors}")
    print(f"No Data: {no_data}")
    
    print("\nDetails:")
    for r in results:
        print(f"  [{r['status']}] {r['question']}")
        if r['status'] == 'error':
            print(f"    Error: {r.get('error', 'N/A')[:80]}")
    
    print(f"\nResults saved to: {output_file}")

if __name__ == "__main__":
    main()