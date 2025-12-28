from .feedback_db import conn, insert_feedback
from .fetch import fetch_post_comments
from .llm import analyze_sentiment, extract_instagram_username
from .posts_db import (
    delete_post,
    get_unprocessed_posts,
    mark_post_processed,
    update_post_comments,
)


def process_posts(limit: int | None = None):
    """Main processing loop"""
    posts_to_process = get_unprocessed_posts(limit=limit)
    processed_count = 0

    print(f"Processing {len(posts_to_process)} posts...")

    for idx, post in enumerate(posts_to_process, 1):
        post_id = post["id"]
        title = post["title"][:60]

        print(f"\n[{idx}/{len(posts_to_process)}] Processing: {post_id} - {title}...")

        try:
            # Check relevance and extract username
            print("  Checking relevance...")
            is_relevant, username = extract_instagram_username(post)

            if not is_relevant:
                print("  ✗ Not relevant, deleting from database...")
                delete_post(post_id)
                continue

            print(f"  ✓ Relevant! Instagram: {username or 'unknown'}")

            # Fetch comments
            print("  Fetching comments...")
            try:
                comments = fetch_post_comments(post["permalink"])
                update_post_comments(post["id"], comments)
                print(f"  Found {len(comments)} comments")
            except Exception as e:
                print(f"  ✗ Failed to fetch comments: {e}")
                # Stop on Reddit API failure as requested
                raise

            # Analyze sentiment
            print("  Analyzing sentiment...")
            sentiment, confidence = analyze_sentiment(post, comments)
            print(f"  Sentiment: {sentiment} ({confidence} confidence)")

            # Insert to database
            print("  Saving to database...")
            insert_feedback(post, username, sentiment, confidence, comments)

            # Mark as processed
            mark_post_processed(post_id)
            processed_count += 1

        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Saving progress...")
            raise

        except Exception as e:
            print(f"  ✗ Error processing post: {e}")
            raise

    # Final save
    print(f"\n✓ Complete! Processed {processed_count} total posts")
    conn.sync()


def main():
    print("Purple Check Agent - Reddit Post Processor")
    print("=" * 50)

    # Process 5 posts as initial test
    process_posts(limit=5)


if __name__ == "__main__":
    main()
