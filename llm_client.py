import json
import os
import time
import base64
from typing import Any
from urllib import request, error
from pathlib import Path


class LLMClient:
    def __init__(self, provider: str | None = None):
        config_path = Path(__file__).parent / "llm_config.json"
        with open(config_path) as f:
            self.config = json.load(f)

        self.provider = provider or self.config["default_provider"]
        self.provider_config = self.config["providers"][self.provider]

        api_key_env = self.provider_config["api_key_env"]
        self.api_key = os.getenv(api_key_env)
        if not self.api_key:
            raise ValueError(f"Missing environment variable: {api_key_env}")

        self.api_url = self.provider_config["api_url"]
        self.model = self.provider_config["model"]
        self.max_retries = self.provider_config["max_retries"]
        self.retry_delay = self.provider_config["retry_delay"]

    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64 for API"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _build_request(self, messages: list[dict[str, Any]], temperature: float = 0.7) -> dict:
        """Build request payload"""
        system_message = None
        messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                content = msg["content"]
                if isinstance(content, list):
                    # Handle multimodal content
                    content = []
                    for item in content:
                        if item["type"] == "text":
                            content.append({"type": "text", "text": item["text"]})
                        elif item["type"] == "image_url":
                            # Extract base64 from data URL
                            image_data = item["image_url"]["url"]
                            if image_data.startswith("data:"):
                                media_type, data = image_data.split(";base64,")
                                media_type = media_type.split(":")[1]
                                content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": data
                                    }
                                })
                    messages.append({"role": msg["role"], "content": content})
                else:
                    messages.append({"role": msg["role"], "content": content})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": temperature
        }

        if system_message:
            payload["system"] = system_message

        return payload

    def _make_request(self, messages: list[dict[str, Any]], temperature: float = 0.7) -> str:
        """Make HTTP request to LLM API"""
        # Build request based on provider
        payload = self._build_request(messages, temperature)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        req = request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        with request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))

        return result["choices"][0]["message"]

    def _call(self, messages: list[dict[str, Any]], temperature: float = 0.7) -> str:
        """Call LLM API with retry logic"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return self._make_request(messages, temperature)
            except error.HTTPError as e:
                last_error = e
                error_body = e.read().decode("utf-8")
                print(f"HTTP Error {e.code}: {error_body}")

                # Don't retry on 4xx errors (except rate limits)
                if 400 <= e.code < 500 and e.code != 429:
                    raise

                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    print(f"Retrying in {wait_time}s... (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
            except Exception as e:
                last_error = e
                print(f"Error: {type(e).__name__}: {e}")

                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    print(f"Retrying in {wait_time}s... (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)

        raise Exception(f"Failed after {self.max_retries} attempts. Last error: {last_error}")

    def call_with_images(self, prompt: str, image_paths: list[str], temperature: float = 0.7) -> str:
        """Call LLM with text and images"""
        if len(image_paths) > 0 and not self.provider_config["supports_vision"]:
            raise ValueError(f"Provider {self.provider} does not support vision")

        content = [{"type": "text", "text": prompt}]

        for img_path in image_paths:
            # Determine image type
            ext = Path(img_path).suffix.lower()
            media_type = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp"
            }.get(ext, "image/jpeg")

            image_b64 = self._encode_image(img_path)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{image_b64}"
                }
            })

        messages = [{"role": "user", "content": content}]
        return self._call(messages, temperature)
