import base64
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib import error, request


class LLMClient:
    def __init__(self, provider: str | None = None):
        config_path = Path(__file__).parent.parent / "config" / "llm_config.json"
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

    def _build_request(
        self, messages: list[dict[str, Any]], temperature: float = 0.7
    ) -> dict:
        """Build request payload"""
        system_message = None
        processed_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                content = msg["content"]
                if isinstance(content, list):
                    # Handle multimodal content
                    processed_content = []
                    for item in content:
                        if item["type"] == "text":
                            processed_content.append(
                                {"type": "text", "text": item["text"]}
                            )
                        elif item["type"] == "image_url":
                            # Extract base64 from data URL
                            image_data = item["image_url"]["url"]
                            if image_data.startswith("data:"):
                                media_type, data = image_data.split(";base64,")
                                media_type = media_type.split(":")[1]
                                processed_content.append(
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": media_type,
                                            "data": data,
                                        },
                                    }
                                )
                    processed_messages.append(
                        {"role": msg["role"], "content": processed_content}
                    )
                else:
                    processed_messages.append({"role": msg["role"], "content": content})

        payload = {
            "model": self.model,
            "messages": processed_messages,
            "max_tokens": 4096,
            "temperature": temperature,
        }

        if system_message:
            payload["system"] = system_message

        return payload

    def _make_request(
        self, messages: list[dict[str, Any]], temperature: float = 0.7
    ) -> str:
        """Make HTTP request to LLM API"""
        # Build request based on provider
        payload = self._build_request(messages, temperature)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        req = request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
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
                    wait_time = self.retry_delay * (2**attempt)  # Exponential backoff
                    print(
                        f"Retrying in {wait_time}s... (attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)
            except Exception as e:
                last_error = e
                print(f"Error: {type(e).__name__}: {e}")

                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2**attempt)
                    print(
                        f"Retrying in {wait_time}s... (attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)

        raise Exception(
            f"Failed after {self.max_retries} attempts. Last error: {last_error}"
        )

    def call_with_images(
        self, prompt: str, image_paths: list[str], temperature: float = 0.7
    ) -> str:
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
                ".webp": "image/webp",
            }.get(ext, "image/jpeg")

            image_b64 = self._encode_image(img_path)
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
                }
            )

        messages = [{"role": "user", "content": content}]
        return self._call(messages, temperature)

    def call(self, messages: list[dict[str, Any]], temperature: float = 0.7) -> str:
        """Call LLM with text messages only"""
        return self._call(messages, temperature)


def extract_instagram_username(
    post: dict, image_paths: list[str]
) -> tuple[bool, str | None]:
    """Use LLM to determine if post is relevant and extract Instagram username"""
    title = post.get("title", "")
    selftext = post.get("selftext", "")

    prompt = f"""Analyze this Reddit post to determine if it refers to an Instagram page/account.

Title: {title}

Text: {selftext}

Instructions:
1. Determine if this post is about an Instagram page, shop, or seller
2. If yes, extract the Instagram username (handle)
3. Look for patterns like: @username, instagram.com/username, "bought from username", account names mentioned
4. Return ONLY a JSON object with this exact format:
{{"is_relevant": true/false, "username": "extracted_username_or_null"}}

If no clear Instagram username can be extracted, set username to null but is_relevant can still be true if it clearly refers to Instagram.
Remove @ symbol from username if present. Return lowercase username."""
    llm = LLMClient()

    try:
        if image_paths:
            response = llm.call_with_images(prompt, image_paths, temperature=0.3)
        else:
            response = llm.call([{"role": "user", "content": prompt}], temperature=0.3)

        # Extract JSON from response
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            is_relevant = result.get("is_relevant", False)
            username = result.get("username")

            # Normalize username
            if username:
                username = username.strip().lower().replace("@", "")

            return is_relevant, username

        return False, None

    except Exception as e:
        print(f"Error in Instagram username extraction: {e}")
        return False, None


def analyze_sentiment(
    post: dict, comments: list[dict], image_paths: list[str]
) -> tuple[str, str]:
    """Use LLM to analyze sentiment of the feedback"""
    llm = LLMClient()

    title = post.get("title", "")
    selftext = post.get("selftext", "")

    comments_text = "\n".join(
        [
            f"- {c['author']} (score {c['score']}): {c['body'][:200]}"
            for c in comments[:10]  # Limit to top 10 comments
        ]
    )

    prompt = f"""Analyze the sentiment of this feedback about an Instagram seller.

Title: {title}

Post: {selftext}

Comments:
{comments_text if comments_text else "No comments"}

Instructions:
Determine if this is positive, negative, or neutral feedback about the Instagram seller.
Return ONLY a JSON object with this exact format:
{{"sentiment": "positive/negative/neutral", "confidence": "high/medium/low"}}

Consider:
- Words like scam, fraud, fake, disappointed = negative
- Words like genuine, great, recommend, satisfied = positive
- Complaints about product quality, delivery, refunds = negative
- Praise about service, product, communication = positive"""

    try:
        if image_paths:
            response = llm.call_with_images(prompt, image_paths[:3], temperature=0.3)
        else:
            response = llm.call([{"role": "user", "content": prompt}], temperature=0.3)

        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            sentiment = result.get("sentiment", "neutral")
            confidence = result.get("confidence", "low")
            return sentiment, confidence

        return "neutral", "low"

    except Exception as e:
        print(f"Error in sentiment analysis: {e}")
        return "neutral", "low"
