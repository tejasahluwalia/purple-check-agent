"""
Fetch new posts from Reddit subreddits incrementally.
Uses curlfire for authenticated requests and tracks last fetched post per subreddit.
"""

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

# Configuration
DATA_DIR = Path("../data")
FETCH_STATE_FILE = DATA_DIR / "processed" / "fetch_state.json"
CURLFIRE_PATH = Path("../tools/curlfire")

# Reddit API configuration
REDDIT_BASE_URL = "https://www.reddit.com"
REQUEST_LIMIT = 100  # Max posts per request (Reddit limit)
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def load_fetch_state():
    """Load the fetch state from JSON file"""
    if FETCH_STATE_FILE.exists():
        with open(FETCH_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_fetch_state(state):
    """Save the fetch state to JSON file"""
    with open(FETCH_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def make_reddit_request(url, retry_count=0):
    """Make a request to Reddit API using curlfire"""
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


def fetch_subreddit_posts(subreddit, last_post_id):
    """
    Fetch posts newer than last_post_id from a subreddit.
    Returns list of new posts and the newest post ID found.
    """
    print(f"  Fetching posts newer than {last_post_id}...")

    all_new_posts = []
    after_token = None
    newest_post_id = last_post_id
    newest_timestamp = 0

    while True:
        # Build URL with pagination
        if after_token:
            # Getting older posts (further back in time)
            url = f"{REDDIT_BASE_URL}/r/{subreddit}/new.json?after={after_token}&limit={REQUEST_LIMIT}&raw_json=1"
            print(f"    Fetching next page (after={after_token})...")
        else:
            # First request: get posts newer than last_post_id
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

            # Process posts
            for post in posts:
                if post["kind"] == "t3":  # t3 = link (post)
                    post_data = post["data"]
                    post_id = post_data.get("name")

                    if post_id:
                        all_new_posts.append(post_data)

                        # Track newest post
                        post_timestamp = post_data.get("created_utc", 0)
                        if post_timestamp > newest_timestamp:
                            newest_timestamp = post_timestamp
                            newest_post_id = post_id

            # Check for more pages
            after_token = response["data"].get("after")
            if not after_token:
                print("    No more pages (after=null)")
                break

            # Small delay to be polite to Reddit API
            time.sleep(1)

        except Exception as e:
            print(f"    Error fetching page: {e}")
            break

    return all_new_posts, newest_post_id, newest_timestamp


def update_subreddit_posts_file(subreddit, new_posts):
    """
    Update the subreddit's posts.json file with new posts.
    Loads existing posts, adds new ones, sorts by timestamp, and saves.
    """
    subreddit_dir = DATA_DIR / "raw" / subreddit
    subreddit_dir.mkdir(exist_ok=True)

    posts_file = subreddit_dir / "posts.json"
    existing_posts = []

    # Load existing posts if file exists
    if posts_file.exists():
        try:
            with open(posts_file, "r", encoding="utf-8") as f:
                existing_posts = json.load(f)
        except json.JSONDecodeError:
            print(f"    Warning: Could not read existing {posts_file}, starting fresh")
            existing_posts = []

    # Combine existing and new posts
    all_posts = existing_posts + new_posts

    # Remove duplicates based on post ID
    seen_ids = set()
    unique_posts = []
    for post in all_posts:
        post_id = post.get("name")
        if post_id and post_id not in seen_ids:
            seen_ids.add(post_id)
            unique_posts.append(post)

    # Sort by creation time (oldest first)
    unique_posts.sort(key=lambda x: x.get("created_utc", 0))

    # Save back to file
    with open(posts_file, "w", encoding="utf-8") as f:
        json.dump(unique_posts, f, indent=2, ensure_ascii=False)

    added_count = len(unique_posts) - len(existing_posts)
    return added_count, len(unique_posts)


def main():
    print("Reddit Post Fetcher")
    print("=" * 60)

    # Load current state
    state = load_fetch_state()
    print(f"Loaded fetch state for {len(state)} subreddits")

    total_new_posts = 0

    # Process each subreddit
    for subreddit in ["InstagramShops", "InstaShoppingFails"]:
        print(f"\nProcessing r/{subreddit}:")
        print("-" * 40)

        subreddit_state = state.get(subreddit, {})
        last_post_id = subreddit_state.get("last_post_id")

        if not last_post_id:
            print(f"  No last_post_id found for {subreddit}, skipping")
            continue

        # Fetch new posts
        new_posts, newest_post_id, newest_timestamp = fetch_subreddit_posts(
            subreddit, last_post_id
        )

        if not new_posts:
            print("  No new posts found")
            continue

        print(f"  Found {len(new_posts)} new posts")
        print(
            f"  Newest post: {newest_post_id} ({datetime.fromtimestamp(newest_timestamp, tz=timezone.utc).isoformat()})"
        )

        # Update subreddit's posts.json file
        added_count, total_posts = update_subreddit_posts_file(subreddit, new_posts)
        print(f"  Added {added_count} new posts to posts.json (total: {total_posts})")

        # Update state
        state[subreddit] = {
            "last_post_id": newest_post_id,
            "last_post_timestamp": newest_timestamp,
            "last_fetch_time": datetime.now(timezone.utc).isoformat(),
            "total_posts_fetched": subreddit_state.get("total_posts_fetched", 0)
            + len(new_posts),
        }

        total_new_posts += len(new_posts)

        # Save state after each subreddit for safety
        save_fetch_state(state)
        print("  Updated fetch state")

    print(f"\n{'=' * 60}")
    print(f"Summary: Fetched {total_new_posts} new posts total")

    if total_new_posts > 0:
        print("\nNext steps:")
        print("1. Run: python tools/extract_posts.py (to regenerate merged_posts.json)")
        print("2. Run: python main.py (to process new posts)")
    else:
        print("No new posts to process")


if __name__ == "__main__":
    main()
