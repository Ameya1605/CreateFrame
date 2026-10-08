import os
import json
import re
import logging
from typing import List, Dict, Any, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("llm_client")


class LLMClient:
    """
    Provider-agnostic LLM client supporting Groq, OpenAI, Anthropic, and Ollama.
    Supports structured output (JSON mode / schemas) and graceful fallbacks.
    """

    PROVIDERS = {
        "groq": {
            "base_url": "https://api.groq.com/openai/v1",
            "default_model": os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
            "fallback_models": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"],
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "default_model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "fallback_models": ["gpt-4o-mini", "gpt-4o"],
        },
        "anthropic": {
            "base_url": "https://api.anthropic.com/v1",
            "default_model": os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
            "fallback_models": ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"],
        },
        "ollama": {
            "base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            "default_model": os.environ.get("OLLAMA_MODEL", "llama3.2"),
            "fallback_models": ["llama3.2", "qwen2.5"],
        },
    }

    def __init__(
        self,
        provider: str = "groq",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.provider = provider.lower() if provider else "groq"
        if self.provider not in self.PROVIDERS:
            self.provider = "groq"

        config = self.PROVIDERS[self.provider]
        self.base_url = base_url or config["base_url"]
        self.model = model or config["default_model"]
        self.fallback_models = config.get("fallback_models", [self.model])

        # Resolve API key
        if api_key:
            self.api_key = api_key
        elif self.provider == "groq":
            self.api_key = os.environ.get("GROQ_API_KEY", "")
        elif self.provider == "openai":
            self.api_key = os.environ.get("OPENAI_API_KEY", "")
        elif self.provider == "anthropic":
            self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        elif self.provider == "ollama":
            self.api_key = "ollama"  # Ollama local doesn't require a real key
        else:
            self.api_key = ""

    def is_configured(self) -> bool:
        if self.provider == "ollama":
            return True
        return bool(self.api_key)

    @staticmethod
    def extract_json(raw_text: str) -> Any:
        """
        Robust JSON extractor that handles markdown fences, leading/trailing prose,
        and returns parsed JSON structure.
        """
        text = raw_text.strip()
        # 1. Try direct json parse
        try:
            return json.loads(text)
        except Exception:
            pass

        # 2. Extract from ```json ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if fence_match:
            try:
                return json.loads(fence_match.group(1).strip())
            except Exception:
                pass

        # 3. Find outermost { ... } or [ ... ]
        first_curly = text.find("{")
        last_curly = text.rfind("}")
        if first_curly != -1 and last_curly != -1 and last_curly > first_curly:
            try:
                return json.loads(text[first_curly : last_curly + 1])
            except Exception:
                pass

        first_bracket = text.find("[")
        last_bracket = text.rfind("]")
        if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
            try:
                return json.loads(text[first_bracket : last_bracket + 1])
            except Exception:
                pass

        raise ValueError(f"Could not parse valid JSON from response: {raw_text[:200]}...")

    def complete(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.1,
        model: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate completion across configured provider with automatic model fallback.
        """
        if not self.is_configured():
            raise RuntimeError(f"API key not configured for LLM provider '{self.provider}'")

        chosen_model = model or self.model
        models_to_try = [chosen_model] + [m for m in self.fallback_models if m != chosen_model]

        last_err = None
        for m in models_to_try:
            try:
                if self.provider == "anthropic":
                    return self._call_anthropic(messages, model=m, temperature=temperature, json_schema=json_schema)
                else:
                    return self._call_openai_compatible(
                        messages,
                        model=m,
                        temperature=temperature,
                        response_format=response_format,
                        json_schema=json_schema,
                    )
            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                if any(x in err_str for x in ("model_not_found", "does not exist", "404", "rate_limit")):
                    log.warning("Model %s failed with %s, attempting next fallback...", m, e)
                    continue
                raise e

        if last_err:
            raise last_err
        raise RuntimeError("No model candidates could be completed")

    def _call_openai_compatible(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        response_format: Optional[Dict[str, Any]] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response_schema", "schema": json_schema},
            }
        elif response_format:
            payload["response_format"] = response_format

        with httpx.Client(timeout=60.0) as client:
            res = client.post(url, headers=headers, json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"HTTP {res.status_code} from {self.provider}: {res.text}")
            data = res.json()
            return data["choices"][0]["message"]["content"]

    def _call_anthropic(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        url = f"{self.base_url.rstrip('/')}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        # Separate system message if present
        system_content = ""
        user_assistant_messages = []
        for m in messages:
            if m["role"] == "system":
                system_content += m["content"] + "\n"
            else:
                user_assistant_messages.append({"role": m["role"], "content": m["content"]})

        payload: Dict[str, Any] = {
            "model": model,
            "messages": user_assistant_messages,
            "max_tokens": 4096,
            "temperature": temperature,
        }
        if system_content.strip():
            payload["system"] = system_content.strip()

        with httpx.Client(timeout=60.0) as client:
            res = client.post(url, headers=headers, json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"HTTP {res.status_code} from Anthropic: {res.text}")
            data = res.json()
            content_blocks = data.get("content", [])
            return "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
