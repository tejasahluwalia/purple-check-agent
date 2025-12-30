import sqlite3
import json
from pathlib import Path
import subprocess


def fetch_post_comments(permalink):
    """Fetch all comments from a Reddit post"""
    url = "https://www.reddit.com" + permalink + ".json"
    curlfire_path = Path(__file__).parent.parent / "lib" / "curlfire"

    try:
        result = subprocess.run(
            [str(curlfire_path), url],
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
        return []


def generate_test_cases(num_posts: int = 20):
    """Generate test cases from the database"""
    db_path = Path(__file__).parent.parent / "data" / "db" / "posts.db"
    test_dir = Path(__file__).parent

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, title, selftext, permalink, author, images
        FROM posts
        WHERE selftext IS NOT NULL AND selftext != '' AND permalink IS NOT NULL
        ORDER BY RANDOM()
        LIMIT ?
    """,
        (num_posts,),
    )

    posts_data = cursor.fetchall()
    print(f"Fetched {len(posts_data)} random posts")

    username_tests = []
    sentiment_tests = []

    for post_id, title, selftext, permalink, author, images_json in posts_data:
        images = []
        if images_json:
            try:
                images = json.loads(images_json)
            except json.JSONDecodeError:
                pass

        username_tests.append(
            {
                "input": {
                    "post": {
                        "title": title or "",
                        "selftext": selftext or "",
                        "author": author or "",
                    },
                    "images": images,
                },
                "expected": {"is_relevant": None, "username": None},
                "note": "Fill in expected values manually",
                "post_id": post_id,
                "permalink": f"https://www.reddit.com{permalink}",
            }
        )

        print(
            f"Fetching comments for post {post_id} by {author} ({len(images)} images)..."
        )
        try:
            comments = fetch_post_comments(permalink)
            comments = [
                {
                    "author": c.get("author", "unknown"),
                    "score": c.get("score", 0),
                    "body": c.get("body", ""),
                }
                for c in comments
                if c.get("body")
            ]
            print(f"  - Found {len(comments)} comments")
        except Exception as e:
            print(f"  - Error fetching comments: {e}")
            comments = []

        expected_sentiments = [
            {"author": c["author"], "sentiment": None} for c in comments
        ]

        sentiment_tests.append(
            {
                "input": {
                    "post": {
                        "title": title or "",
                        "selftext": selftext or "",
                        "author": author or "",
                        "permalink": f"https://www.reddit.com{permalink}",
                    },
                    "comments": comments,
                    "images": images,
                },
                "expected": {"sentiments": expected_sentiments},
                "note": "Fill in expected sentiment values (positive/negative/neutral) manually",
                "post_id": post_id,
                "permalink": f"https://www.reddit.com{permalink}",
            }
        )

    conn.close()

    with open(test_dir / "extract_instagram_username_test_data.json", "w") as f:
        json.dump(username_tests, f, indent=2)

    with open(test_dir / "analyze_sentiment_test_data.json", "w") as f:
        json.dump(sentiment_tests, f, indent=2)

    print(f"\nSaved test files to {test_dir}")
    print(
        f"  - extract_instagram_username_test_data.json ({len(username_tests)} cases)"
    )
    print(f"  - analyze_sentiment_test_data.json ({len(sentiment_tests)} cases)")

    posts_with_images = sum(1 for test in username_tests if test["input"]["images"])
    total_comments = sum(len(test["input"]["comments"]) for test in sentiment_tests)
    posts_with_comments = sum(
        1 for test in sentiment_tests if test["input"]["comments"]
    )

    print(f"\nStatistics:")
    print(f"  Posts with images: {posts_with_images}/{len(username_tests)}")
    print(f"  Posts with comments: {posts_with_comments}/{len(sentiment_tests)}")
    print(f"  Total comments: {total_comments}")
    print(f"  Avg comments per post: {total_comments / len(sentiment_tests):.1f}")


if __name__ == "__main__":
    import sys

    num_posts = 20
    if len(sys.argv) > 1:
        try:
            num_posts = int(sys.argv[1])
        except ValueError:
            print("Usage: python generate_test_data.py [num_posts]")
            sys.exit(1)

    generate_test_cases(num_posts)
