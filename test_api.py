from backend.agents.base_agent import BaseAgent
import sys
import asyncio

try:
    agent = BaseAgent()
    print("API Key loaded:", repr(agent.api_key))
    print("Base URL loaded:", repr(agent.base_url))
    print("Model loaded:", repr(agent.model))
    
    # Try a simple query
    print("\nTesting simple query...")
    result = agent.query(
        system_prompt="You are a helpful assistant.",
        user_prompt="Say 'Hello, World!' in JSON format: {\"message\": \"...\"}",
        format_json=True
    )
    print("\nSuccess! Result:", result)
except Exception as e:
    print(f"\nError: {type(e).__name__}: {e}")
    sys.exit(1)
