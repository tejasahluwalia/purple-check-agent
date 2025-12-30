from typing import List, Literal

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from .check_username import check_username_exists

load_dotenv()
client = genai.Client()


def extract_instagram_username(post: dict, images: list[str] = []) -> tuple[bool, str]:
    """Use LLM to determine if post is relevant and extract Instagram username"""

    title = post["title"]
    selftext = post["selftext"]

    prompt = f"""
Analyze this Reddit post to determine if it refers to an Instagram shopping page or account. The post is relevant if the author is talking about any individual Instagram based shop, either sharing their experience, or asking for others' opinions.

Title: {title}

Text: {selftext}

Images: Attached at the end.

Instructions:
1. Determine if this post is about an Instagram shop or seller by checking the text and images
2. If yes, extract the exact Instagram username (handle)
3. Use the `check_username_exists` tool to verify if the username is a valid and active instagram account
4. Return ONLY a JSON object with this format:
{{"is_relevant": true/false, "username": "extracted_username_or_null"}}

If no clear Instagram username can be extracted, set username to null but is_relevant can still be true if it clearly refers to Instagram.
Remove @ symbol from username if present. Return lowercase username.
"""
    try:

        class Response(BaseModel):
            is_relevant: bool = Field(
                description="Whether the post is relevant to a particular instagram shopping page or not."
            )
            username: str = Field(
                description="Instagram username of the page mentioned in the post."
            )

        config = types.GenerateContentConfig(
            tools=[check_username_exists],
            response_mime_type="application/json",
            response_schema=Response.model_json_schema(),
        )

        contents = []
        contents.append(prompt)

        for image_path in images:
            image_bytes = requests.get(image_path).content
            image = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            contents.append(image)

        response = client.models.generate_content(
            model="gemini-3-flash-preview", contents=contents, config=config
        )

        if response.text:
            result = Response.model_validate_json(response.text)
            return result.is_relevant, result.username

        return False, ""

    except Exception as e:
        print(f"Error in Instagram username extraction: {e}")
        return False, ""


def analyze_sentiment(
    shop_username: str, post: dict, comments: list[dict], images: list[str] = []
) -> list[dict[str, str]]:
    """Use LLM to analyze sentiment of feedback for each comment"""
    title = post.get("title", "")
    selftext = post.get("selftext", "")
    permalink = post.get("permalink", "")
    post_author = post.get("author", "")

    comments_text = "\n".join(
        [
            f"- Comment {i + 1} by {c['author']} (score {c['score']}): {c['body']}"
            for i, c in enumerate(comments)
        ]
    )

    prompt = f"""
Analyze this Reddit post and its comments and extract all relevant sentiments about the Instagram page {shop_username} left by Reddit users including sentiment from the post author and commentors.
There must be only one sentiment per username.
"""
    post_text = f"""
Title: {title}

By: {post_author}

Post: {selftext}

Images: Attached below
"""
    comments_section = f"""
Comments:
{comments_text if comments_text else "No comments"}

Instructions:
Return ONLY a JSON array with this format:
 [
  {{"author": "comment_author", "sentiment": "positive/negative/neutral"}},
  ...
 ]

Consider:
- Words like scam, fraud, fake, disappointed = negative
- Words like genuine, great, recommend, satisfied = positive
- Complaints about product quality, delivery, refunds = negative
- Praise about service, product, communication = positive
"""

    try:

        class Sentiment(BaseModel):
            author: str = Field(
                description="Username of the author of the post or comments with this sentiment"
            )
            sentiment: Literal["positive", "negative"] = Field(
                description="Positive or negative sentiment displayed by the user towards the Instagram shop/page"
            )

        class Response(BaseModel):
            sentiments: List[Sentiment] = Field(
                description="List of all the user sentiments present in the post"
            )

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Response.model_json_schema(),
        )

        contents = []
        contents.append(prompt)
        contents.append(post_text)

        for image_path in images:
            image_bytes = requests.get(image_path).content
            image = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            contents.append(image)

        contents.append(comments_section)

        response = client.models.generate_content(
            model="gemini-3-flash-preview", contents=contents, config=config
        )

        if response.text:
            result = Response.model_validate_json(response.text)
            sentiments = []
            for item in result.sentiments:
                author = item.author
                sentiment = item.sentiment
                sentiments.append(
                    {
                        "author": author,
                        "sentiment": sentiment,
                        "permalink": permalink,
                    }
                )
            return sentiments

        return []

    except Exception as e:
        print(f"Error in sentiment analysis: {e}")
        return []
