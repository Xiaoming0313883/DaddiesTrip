import requests
import json
import re
import os
from dotenv import load_dotenv

load_dotenv()

class BaseAgent:
    def __init__(self, model=None):
        self.api_key = os.getenv("Z_AI_API_KEY", "")
        self.api_url = os.getenv("Z_AI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
        self.model = model or os.getenv("Z_AI_MODEL", "glm-4")

    def query(self, system_prompt, user_prompt, format_json=True):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            if not self.api_key or self.api_key == "your_zai_api_key_here":
                raise ValueError("Missing valid Z.AI API key. Please configure .env context.")

            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if format_json:
                json_match = re.search(r'(\{.*\})', text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    raise ValueError(f"Agent failed to return valid JSON. Output was: {text[:100]}...")
            return text
        except Exception as e:
            print(f"Error in {self.__class__.__name__}: {e}")
            raise e
