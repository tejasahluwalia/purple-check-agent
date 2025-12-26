import libsql
import os
import json
import subprocess
import tempfile
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from .llm_client import LLMClient

load_dotenv()

url = os.getenv("TURSO_DATABASE_URL")
auth_token = os.getenv("TURSO_AUTH_TOKEN")

conn = libsql.connect("../data/db/purple-check.db", sync_url=url, auth_token=auth_token)  # type: ignore[unresolved-attribute]
conn.sync()

# Initialize LLM client
llm = LLMClient()

# Progress tracking
PROGRESS_FILE = "../data/processed/progress.json"


def load_progress():
    """Load processed post IDs from progress file"""
    if Path(PROGRESS_FILE).exists():
        with open(PROGRESS_FILE) as f:
            return set(json.load(f))
    return set()


def save_progress(processed_ids: set):
    """Save processed post IDs to progress file"""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(list(processed_ids), f)


def fetch_comments(permalink: str) -> list[dict]:
    """Fetch comments from Reddit using curlfire"""
    url = "https://www.reddit.com" + permalink + ".json"

    try:
        result = subprocess.run(
            ["../tools/curlfire", url],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        data = json.loads(result.stdout)

        # Reddit returns [post_data, comments_data]
        if len(data) < 2:
            return []

        comments_data = data[1]
        comments = []

        def extract_comments(item):
            """Recursively extract comments from nested structure"""
            if isinstance(item, dict):
                if item.get("kind") == "t1":  # Comment
                    comment_data = item.get("data", {})
                    body = comment_data.get("body", "")
                    author = comment_data.get("author", "")

                    # Skip deleted/removed comments
                    if body not in ["[deleted]", "[removed]"] and author != "[deleted]":
                        comments.append(
                            {
                                "author": author,
                                "body": body,
                                "score": comment_data.get("score", 0),
                            }
                        )

                    # Process replies
                    replies = comment_data.get("replies")
                    if isinstance(replies, dict):
                        extract_comments(replies)

                elif item.get("kind") == "Listing":
                    children = item.get("data", {}).get("children", [])
                    for child in children:
                        extract_comments(child)

        extract_comments(comments_data)
        return comments

    except subprocess.CalledProcessError as e:
        print(f"Failed to fetch comments: {e.stderr}")
        raise
    except subprocess.TimeoutExpired:
        print(f"Timeout fetching comments for {permalink}")
        raise
    except Exception as e:
        print(f"Error fetching comments: {e}")
        raise


def download_image(url: str, temp_dir: str) -> str | None:
    """Download image using curlfire to temp directory"""
    try:
        # Generate filename from URL
        filename = url.split("/")[-1].split("?")[0]
        if not any(
            filename.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]
        ):
            filename += ".jpg"

        output_path = Path(temp_dir) / filename

        result = subprocess.run(
            ["../tools/curlfire", "-o", str(output_path), url],
            capture_output=True,
            timeout=30,
            check=True,
        )

        if output_path.exists() and output_path.stat().st_size > 0:
            return str(output_path)
        return None

    except Exception as e:
        print(f"Failed to download image {url}: {e}")
        return None


def extract_images_from_post(post: dict, temp_dir: str) -> list[str]:
    """Extract and download images from Reddit post"""
    image_paths = []

    # Check gallery_data first
    if post.get("gallery_data"):
        media_metadata = post.get("media_metadata", {})
        for item in post["gallery_data"].get("items", []):
            media_id = item.get("media_id")
            if media_id and media_id in media_metadata:
                image_url = media_metadata[media_id].get("s", {}).get("u")
                if image_url:
                    # Decode HTML entities
                    image_url = image_url.replace("&amp;", "&")
                    path = download_image(image_url, temp_dir)
                    if path:
                        image_paths.append(path)

    # Check preview images
    elif post.get("preview"):
        images = post["preview"].get("images", [])
        for image in images:
            image_url = image.get("source", {}).get("url")
            if image_url:
                image_url = image_url.replace("&amp;", "&")
                path = download_image(image_url, temp_dir)
                if path:
                    image_paths.append(path)

    return image_paths


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


def insert_feedback(
    post: dict,
    username: str | None,
    sentiment: str,
    confidence: str,
    comments: list[dict],
):
    """Insert feedback into database"""
    giver = post.get("author", "unknown")
    receiver = username if username else "unknown_instagram_user"

    # Create comment text
    title = post.get("title", "")
    selftext = post.get("selftext", "")
    permalink = post.get("permalink", "")

    comment_parts = [f"Title: {title}"]
    if selftext:
        comment_parts.append(f"Post: {selftext[:500]}")

    if comments:
        comment_parts.append(f"\nTop comments ({len(comments)}):")
        for c in comments[:5]:
            comment_parts.append(f"- {c['body'][:150]}")

    comment_parts.append(f"\nReddit link: https://reddit.com{permalink}")
    comment_parts.append(f"Confidence: {confidence}")

    comment_text = "\n".join(comment_parts)

    # Map sentiment to rating
    rating_map = {"positive": "POSITIVE", "negative": "NEGATIVE", "neutral": "NEUTRAL"}
    rating = rating_map.get(sentiment, "NEUTRAL")

    try:
        # Try to insert, if duplicate exists, update
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO feedback (giver, receiver, rating, comment, platform, medium, source, giver_role, receiver_role)
            VALUES (?, ?, ?, ?, 'INSTAGRAM', 'DIRECT', 'REDDIT', 'buyer', 'seller')
            ON CONFLICT(giver, receiver) DO UPDATE SET
                rating = excluded.rating,
                comment = excluded.comment,
                updated_at = CURRENT_TIMESTAMP
        """,
            (giver, receiver, rating, comment_text),
        )

        conn.commit()
        print(f"✓ Inserted feedback: {giver} -> {receiver} ({rating})")

    except Exception as e:
        print(f"Error inserting feedback: {e}")
        raise


def process_posts(limit: int | None = None):
    """Main processing loop"""
    # Load posts
    with open("../data/processed/merged_posts.json") as f:
        all_posts = json.load(f)

    # Load progress
    processed_ids = load_progress()
    print(f"Loaded {len(processed_ids)} previously processed posts")

    # Filter unprocessed posts
    posts_to_process = [p for p in all_posts if p.get("id") not in processed_ids]

    if limit:
        posts_to_process = posts_to_process[:limit]

    print(f"Processing {len(posts_to_process)} posts...")

    for idx, post in enumerate(posts_to_process, 1):
        post_id = post.get("id")
        title = post.get("title", "")[:60]

        print(f"\n[{idx}/{len(posts_to_process)}] Processing: {post_id} - {title}...")

        temp_dir = tempfile.mkdtemp(prefix="reddit_images_")

        try:
            # Download images
            print("  Downloading images...")
            image_paths = extract_images_from_post(post, temp_dir)
            print(f"  Downloaded {len(image_paths)} images")

            # Check relevance and extract username
            print("  Checking relevance...")
            is_relevant, username = extract_instagram_username(post, image_paths)

            if not is_relevant:
                print(f"  ✗ Not relevant, skipping")
                processed_ids.add(post_id)
                continue

            print(f"  ✓ Relevant! Instagram: {username or 'unknown'}")

            # Fetch comments
            print("  Fetching comments...")
            try:
                comments = fetch_comments(post.get("permalink", ""))
                print(f"  Found {len(comments)} comments")
            except Exception as e:
                print(f"  ✗ Failed to fetch comments: {e}")
                # Stop on Reddit API failure as requested
                raise

            # Analyze sentiment
            print("  Analyzing sentiment...")
            sentiment, confidence = analyze_sentiment(post, comments, image_paths)
            print(f"  Sentiment: {sentiment} ({confidence} confidence)")

            # Insert to database
            print("  Saving to database...")
            insert_feedback(post, username, sentiment, confidence, comments)

            # Mark as processed
            processed_ids.add(post_id)

            # Save progress periodically
            if idx % 5 == 0:
                save_progress(processed_ids)
                print(f"  Progress saved ({len(processed_ids)} total)")

        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Saving progress...")
            save_progress(processed_ids)
            raise

        except Exception as e:
            print(f"  ✗ Error processing post: {e}")
            # Save progress before stopping
            save_progress(processed_ids)
            raise

        finally:
            # Cleanup temp images
            import shutil

            if Path(temp_dir).exists():
                shutil.rmtree(temp_dir)

    # Final save
    save_progress(processed_ids)
    print(f"\n✓ Complete! Processed {len(processed_ids)} total posts")
    conn.sync()


def main():
    print("Purple Check Agent - Reddit Post Processor")
    print("=" * 50)

    # Process 5 posts as initial test
    process_posts(limit=5)


if __name__ == "__main__":
    main()
