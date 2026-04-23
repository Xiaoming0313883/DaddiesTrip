import json
import re
import os
import time
from dotenv import load_dotenv
from openai import OpenAI, APITimeoutError, APIConnectionError, APIStatusError

load_dotenv()

class AgentAPIError(Exception):
    """Wraps LLM API errors with a user-friendly message."""
    def __init__(self, user_message, detail=None):
        self.user_message = user_message
        self.detail = detail
        super().__init__(user_message)

class BaseAgent:
    def __init__(self, model=None):
        self.api_key = os.getenv("Z_AI_API_KEY", "")
        api_url = os.getenv("Z_AI_BASE_URL", "https://api.ilmu.ai/v1/chat/completions")

        # OpenAI client expects the base URL, not the full completions endpoint
        self.base_url = api_url.replace("/chat/completions", "") if api_url.endswith("/chat/completions") else api_url

        self.model = model or os.getenv("Z_AI_MODEL", "glm-4")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=120.0
        )

    @staticmethod
    def _friendly_error(e):
        """Convert API exceptions into user-friendly messages."""
        if isinstance(e, APITimeoutError):
            return AgentAPIError("The AI service timed out. Please try again with a shorter or simpler prompt.", detail=str(e))
        if isinstance(e, APIConnectionError):
            return AgentAPIError("Unable to reach the AI service. Please check your internet connection and try again.", detail=str(e))
        if isinstance(e, APIStatusError):
            code = e.status_code
            if code == 504 or code == 502:
                return AgentAPIError("The AI service is temporarily unavailable (gateway timeout). Please wait a moment and try again.", detail=str(e))
            if code == 429:
                return AgentAPIError("Too many requests. Please wait a moment and try again.", detail=str(e))
            if code == 401:
                return AgentAPIError("API key is invalid. Please check your configuration.", detail=str(e))
            if code >= 500:
                return AgentAPIError(f"The AI service returned an error (HTTP {code}). Please try again later.", detail=str(e))
            return AgentAPIError(f"AI service error (HTTP {code}). Please try again.", detail=str(e))
        if isinstance(e, AgentAPIError):
            return e
        return AgentAPIError("An unexpected error occurred. Please try again.", detail=str(e))

    def query(self, system_prompt, user_prompt, format_json=True, max_retries=2):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        if not self.api_key or self.api_key == "your_zai_api_key_here":
            raise AgentAPIError("Missing valid API key. Please configure your .env file.")

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3
                )

                text = response.choices[0].message.content
                if format_json:
                    json_match = re.search(r'(\{.*\})', text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group(1))
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        raise ValueError(f"Agent failed to return valid JSON. Output was: {text[:100]}...")
                return text
            except AgentAPIError:
                raise
            except (APITimeoutError, APIConnectionError, APIStatusError) as e:
                last_error = self._friendly_error(e)
                print(f"API Error in {self.__class__.__name__} (attempt {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries:
                    time.sleep(3 * (attempt + 1))
            except Exception as e:
                last_error = self._friendly_error(e)
                print(f"Error in {self.__class__.__name__} (attempt {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries:
                    time.sleep(2 * (attempt + 1))
        raise last_error
