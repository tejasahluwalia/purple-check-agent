import json
import tempfile
from pathlib import Path

from .feedback_db import conn, insert_feedback
from .fetch import fetch_post_comments
from .llm import analyze_sentiment, extract_instagram_username
from .utils import (
    load_progress,
    save_progress,
)


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
            # Check relevance and extract username
            print("  Checking relevance...")
            is_relevant, username = extract_instagram_username(post, image_paths)

            if not is_relevant:
                print("  ✗ Not relevant, skipping")
                processed_ids.add(post_id)
                continue

            print(f"  ✓ Relevant! Instagram: {username or 'unknown'}")

            # Fetch comments
            print("  Fetching comments...")
            try:
                comments = fetch_post_comments(post.get("permalink", ""))
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
