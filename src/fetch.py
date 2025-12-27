import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .posts_db import (
    count_posts,
    insert_post,
)

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
FETCH_STATE_FILE = DATA_DIR / "processed" / "fetch_state.json"
CURLFIRE_PATH = BASE_DIR / "lib" / "curlfire"

REDDIT_BASE_URL = "https://www.reddit.com"
REQUEST_LIMIT = 100
MAX_RETRIES = 3
RETRY_DELAY = 5


def load_fetch_state():
    if FETCH_STATE_FILE.exists():
        with open(FETCH_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_fetch_state(state):
    with open(FETCH_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def make_reddit_request(url, retry_count=0):
    try:
        result = subprocess.run(
            [str(CURLFIRE_PATH), url],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"  HTTP error: {e.stderr[:200]}")
        if retry_count < MAX_RETRIES:
            print(f"  Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)
            return make_reddit_request(url, retry_count + 1)
        raise
    except subprocess.TimeoutExpired:
        print("  Timeout after 30 seconds")
        if retry_count < MAX_RETRIES:
            print(f"  Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)
            return make_reddit_request(url, retry_count + 1)
        raise
    except json.JSONDecodeError as e:
        print(f"  JSON decode error: {e}")
        raise


def extract_image_urls(post):
    urls = []

    if post.get("gallery_data"):
        media_metadata = post.get("media_metadata") or {}
        for item in post["gallery_data"].get("items", []):
            media_id = item.get("media_id")
            if media_id and media_id in media_metadata:
                image_url = media_metadata[media_id].get("s", {}).get("u")
                if image_url:
                    urls.append(image_url.replace("&amp;", "&"))

    elif post.get("preview"):
        images = post["preview"].get("images", [])
        for image in images:
            image_url = image.get("source", {}).get("url")
            if image_url:
                urls.append(image_url.replace("&amp;", "&"))

    return urls


def fetch_post_comments(permalink):
    url = "https://www.reddit.com" + permalink + ".json"

    try:
        result = subprocess.run(
            [str(CURLFIRE_PATH), url],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        data = json.loads(result.stdout)

        if len(data) < 2:
            return []

        comments_data = data[1]
        comments = []

        def extract_comments(item):
            if isinstance(item, dict):
                if item.get("kind") == "t1":
                    comment_data = item.get("data", {})
                    body = comment_data.get("body", "")
                    author = comment_data.get("author", "")

                    if body not in ["[deleted]", "[removed]"] and author != "[deleted]":
                        comments.append(
                            {
                                "author": author,
                                "body": body,
                                "score": comment_data.get("score", 0),
                            }
                        )

                    replies = comment_data.get("replies")
                    if isinstance(replies, dict):
                        extract_comments(replies)

                elif item.get("kind") == "Listing":
                    children = item.get("data", {}).get("children", [])
                    for child in children:
                        extract_comments(child)

        extract_comments(comments_data)
        return comments

    except Exception as e:
        print(f"Failed to fetch comments: {e}")
        raise


def fetch_subreddit_posts(subreddit, last_post_id):
    print(f"  Fetching posts newer than {last_post_id}...")

    all_new_posts = []
    after_token = None
    newest_post_id = last_post_id
    newest_timestamp = 0

    while True:
        if after_token:
            url = f"{REDDIT_BASE_URL}/r/{subreddit}/new.json?after={after_token}&limit={REQUEST_LIMIT}&raw_json=1"
            print(f"    Fetching next page (after={after_token})...")
        else:
            url = f"{REDDIT_BASE_URL}/r/{subreddit}/new.json?before={last_post_id}&limit={REQUEST_LIMIT}&raw_json=1"
            print(f"    First request (before={last_post_id})...")

        try:
            response = make_reddit_request(url)

            if "data" not in response or "children" not in response["data"]:
                print("    No posts in response")
                break

            posts = response["data"]["children"]
            print(f"    Received {len(posts)} posts")

            if not posts:
                print("    No more posts")
                break

            for post in posts:
                if post["kind"] == "t3":
                    post_data = post["data"]
                    post_id = post_data.get("name")

                    if post_id:
                        all_new_posts.append(post_data)

                        post_timestamp = post_data.get("created_utc", 0)
                        if post_timestamp > newest_timestamp:
                            newest_timestamp = post_timestamp
                            newest_post_id = post_id

            after_token = response["data"].get("after")
            if not after_token:
                print("    No more pages (after=null)")
                break

            time.sleep(1)

        except Exception as e:
            print(f"    Error fetching page: {e}")
            break

    return all_new_posts, newest_post_id, newest_timestamp


def fetch_and_save_posts(subreddit):
    """Fetch new posts and save directly to database"""
    state = load_fetch_state()
    subreddit_state = state.get(subreddit, {})
    last_post_id = subreddit_state.get("last_post_id")

    if not last_post_id:
        print(f"  No last_post_id found for {subreddit}, skipping")
        return 0

    new_posts, newest_post_id, newest_timestamp = fetch_subreddit_posts(
        subreddit, last_post_id
    )

    if not new_posts:
        print("  No new posts found")
        return 0

    print(f"  Found {len(new_posts)} new posts")

    for post_data in new_posts:
        image_urls = extract_image_urls(post_data)
        insert_post(post_data, image_urls)

    state[subreddit] = {
        "last_post_id": newest_post_id,
        "last_post_timestamp": newest_timestamp,
        "last_fetch_time": datetime.now(timezone.utc).isoformat(),
        "total_posts_fetched": subreddit_state.get("total_posts_fetched", 0)
        + len(new_posts),
    }

    save_fetch_state(state)
    return len(new_posts)


def main():
    print("Reddit Post Fetcher")
    print("=" * 60)

    state = load_fetch_state()
    print(f"\nLoaded fetch state for {len(state)} subreddits")

    total_new_posts = 0

    for subreddit in ["InstagramShops", "InstaShoppingFails"]:
        print(f"\nProcessing r/{subreddit}:")
        print("-" * 40)

        subreddit_state = state.get(subreddit, {})
        last_post_id = subreddit_state.get("last_post_id")

        if not last_post_id:
            print(f"  No last_post_id found for {subreddit}, skipping")
            continue

        try:
            new_count = fetch_and_save_posts(subreddit)
            total_new_posts += new_count

            if new_count > 0:
                print(f"  ✓ Fetched and saved {new_count} new posts")

        except Exception as e:
            print(f"  ✗ Error fetching {subreddit}: {e}")
            continue

    final_count = count_posts()

    print(f"\n{'=' * 60}")
    print("Summary:")
    print(f"  - Total posts in database: {final_count}")
    print(f"  - New posts fetched: {total_new_posts}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
