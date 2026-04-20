import math
import os
import json
import re
import requests

class OrchestratorAgent:
    def __init__(self):
        self.ollama_url = "http://127.0.0.1:11434/api/generate"
        self.model = "deepseek-r1:8b" 

    def process_prompt(self, prompt: str) -> dict:
        word_count = len(prompt.split())
        if word_count > 1500:
            print(f"Triggering chunking array for {word_count} words")
            
        system_prompt = """
        You are a travel orchestrator agent for DaddiesTrip.
        The user will provide a travel prompt. You must extract and generate a structured itinerary and cost estimate.
        
        CRITICAL INSTRUCTION: WEB SEARCH
        - You have access to the internet. You MUST use your web search capability to look up the CURRENT, LIVE prices for flights, hotels, attractions, and real-time currency exchange rates before finalizing your budget.
        - Do not guess the prices. Base your budget strictly on the live search results.
        
        BUDGETING RULES:
        - Your cost estimations MUST be highly realistic and reflect actual market rates found via your web search.
        - ALWAYS factor in the cost of international/domestic flights, which alone can be $800-$1500 per person.
        - Factor in realistic nightly accommodation costs ($100-$300/night), daily food, and transportation.
        - For example, a 1-week trip to Japan should generally cost a minimum of $2000-$3000 USD per person.
        
        You MUST respond ONLY with a valid JSON object matching this schema exactly:
        {
            "itinerary": [
                {
                    "day": 1,
                    "location": "City Name",
                    "activities": [
                        {"name": "Attraction Name", "cost": 50, "source": "example.com"}
                    ],
                    "daily_hotel_cost": 150,
                    "daily_food_cost": 80,
                    "daily_transport_cost": 20
                }
            ],
            "flights": {
                "cost": 1200,
                "source": "skyscanner.com"
            },
            "estimated_total_cost": 2500,
            "currency": "USD",
            "participants": ["Participant 1", "Participant 2"],
            "budget_recommendation": {
                "is_sufficient": false,
                "message": "Your budget of $1000 is too low. Flights alone cost $1200. We recommend a budget of $2500."
            }
        }
        Do not include markdown blocks or any other text outside the JSON. Ensure estimated_total_cost is a number.
        """

        full_prompt = f"{system_prompt}\n\nUser Request: {prompt}"

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "num_predict": 8192,
                "temperature": 0.3
            }
        }

        try:
            # Local Ollama requests might take a bit longer depending on hardware, setting a safe timeout
            response = requests.post(self.ollama_url, json=payload, timeout=300)
            response.raise_for_status()
            
            data = response.json()
            text = data.get("response", "")
            
            # Deepseek-r1 outputs <think> tags for chain-of-thought, we must strip them out
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
            
            # Extract JSON robustly, ignoring conversational filler before/after
            json_match = re.search(r'(\{.*\})', text, re.DOTALL)
            if json_match:
                text = json_match.group(1)
            else:
                raise ValueError("No JSON object found in AI response.")
            
            # Parse the JSON response
            result = json.loads(text)
            
            # Basic validation
            if "estimated_total_cost" not in result or "itinerary" not in result:
                 raise ValueError("AI returned malformed data.")
                 
            return result
        except requests.exceptions.RequestException as e:
            print(f"Ollama API Connection Error: {e}")
            raise ValueError(f"Failed to connect to local Ollama instance (ensure Ollama is running): {str(e)}")
        except json.JSONDecodeError as e:
            print(f"JSON Parsing Error: {e}\nExtracted text: {text}")
            raise ValueError("Ambiguous destination or AI returned invalid format.")
        except Exception as e:
            print(f"Agent Error: {e}")
            raise ValueError(f"AI Agent Error: {str(e)}")
