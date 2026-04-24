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
            timeout=180.0
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

    @staticmethod
    def _count_open_brackets(s):
        """Count unmatched { and [ in a JSON string, respecting string literals."""
        stack = []
        in_string = False
        escape = False
        for ch in s:
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in ('{', '['):
                stack.append(ch)
            elif ch == '}' and stack and stack[-1] == '{':
                stack.pop()
            elif ch == ']' and stack and stack[-1] == '[':
                stack.pop()
        return stack

    @staticmethod
    def _parse_json_robust(text):
        """
        Parse JSON from LLM output with repair for common issues:
        - Trailing commas before } or ]
        - Truncated output (missing closing brackets/braces)
        - Markdown code fences (```json ... ```)
        """
        # Strip markdown code fences if present
        text = re.sub(r'```(?:json)?\s*', '', text).strip()

        # Extract the outermost JSON object
        json_match = re.search(r'(\{.*)', text, re.DOTALL)
        if not json_match:
            raise ValueError(f"No JSON object found in output: {text[:200]}...")

        raw = json_match.group(1)

        # Try parsing as-is first
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Repair step 1: Remove trailing commas before } or ]
        repaired = re.sub(r',\s*([}\]])', r'\1', raw)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Repair step 2: Close any unclosed strings, remove trailing junk, close brackets
        # If we're inside an unclosed string, close it
        quote_count = 0
        esc = False
        for ch in repaired:
            if esc:
                esc = False
                continue
            if ch == '\\':
                esc = True
                continue
            if ch == '"':
                quote_count += 1
        if quote_count % 2 == 1:
            repaired += '"'

        # Remove trailing partial tokens (e.g. a key without value, or dangling comma)
        repaired = re.sub(r',\s*"[^"]*"\s*:\s*$', '', repaired)  # trailing "key":
        repaired = re.sub(r',\s*"[^"]*"\s*$', '', repaired)      # trailing "key"
        repaired = re.sub(r',\s*$', '', repaired)                 # trailing comma
        repaired = re.sub(r':\s*$', ': null', repaired)           # trailing colon → null

        # Close unclosed brackets/braces (in reverse stack order)
        stack = BaseAgent._count_open_brackets(repaired)
        for opener in reversed(stack):
            repaired += '}' if opener == '{' else ']'

        # Remove trailing commas again (closing may have created new ones)
        repaired = re.sub(r',\s*([}\]])', r'\1', repaired)

        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON repair failed ({e}). Raw output: {raw[:300]}...")

    def query(self, system_prompt, user_prompt, format_json=True, max_retries=1, max_tokens=4096):
        """
        Query the LLM using STREAMING mode.
        
        Streaming keeps the HTTP connection alive by receiving tokens incrementally.
        This prevents Cloudflare/gateway 504 timeouts which occur when the server
        waits too long for the first byte of a non-streamed response.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        if not self.api_key or self.api_key == "your_zai_api_key_here":
            raise AgentAPIError("Missing valid API key. Please configure your .env file.")

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                # Use streaming to prevent gateway timeouts.
                # With stream=True, tokens arrive incrementally, keeping the
                # connection alive even if full generation takes 60+ seconds.
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=max_tokens,
                    stream=False
                )

                text = response.choices[0].message.content if response.choices else ""

                if not text.strip():
                    # Treat as retryable — don't hard-fail
                    raise ValueError("LLM returned empty response.")

                if format_json:
                    return self._parse_json_robust(text)
                return text
            except AgentAPIError:
                raise
            except (APITimeoutError, APIConnectionError, APIStatusError) as e:
                last_error = self._friendly_error(e)
                print(f"API Error in {self.__class__.__name__} (attempt {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries:
                    time.sleep(2 * (attempt + 1))
            except Exception as e:
                last_error = self._friendly_error(e)
                print(f"Error in {self.__class__.__name__} (attempt {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries:
                    time.sleep(2 * (attempt + 1))
        raise last_error
