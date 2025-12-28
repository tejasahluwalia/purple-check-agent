import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "db" / "posts.db"


def insert_post(post_data: dict, image_urls: list[str]) -> None:
    """Insert or replace a post by ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO posts (
            id, name, title, author, selftext, subreddit,
            created_utc, url, permalink, num_comments, score,
            ups, downs, upvote_ratio, over_18, thumbnail,
            is_gallery, url_overridden_by_dest, link_flair_text,
            is_self, domain, images, comments, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            post_data.get("id"),
            post_data.get("name"),
            post_data.get("title"),
            post_data.get("author"),
            post_data.get("selftext"),
            post_data.get("subreddit"),
            post_data.get("created_utc"),
            post_data.get("url"),
            post_data.get("permalink"),
            post_data.get("num_comments"),
            post_data.get("score"),
            post_data.get("ups"),
            post_data.get("downs"),
            post_data.get("upvote_ratio"),
            1 if post_data.get("over_18") else 0,
            post_data.get("thumbnail"),
            1 if post_data.get("is_gallery") else 0,
            post_data.get("url_overridden_by_dest"),
            post_data.get("link_flair_text"),
            1 if post_data.get("is_self") else 0,
            post_data.get("domain"),
            json.dumps(image_urls),
            "[]",
            json.dumps(post_data),
        ),
    )

    conn.commit()
    conn.close()


def get_all_posts(subreddit: str | None = None) -> list[dict]:
    """Query all posts, optionally filtered by subreddit"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if subreddit:
        cursor.execute(
            "SELECT * FROM posts WHERE subreddit = ? ORDER BY created_utc ASC",
            (subreddit,),
        )
    else:
        cursor.execute("SELECT * FROM posts ORDER BY created_utc ASC")

    posts = []
    for row in cursor.fetchall():
        post = dict(row)
        if post["images"]:
            post["images"] = json.loads(post["images"])
        if post["comments"]:
            post["comments"] = json.loads(post["comments"])
        if post["raw_json"]:
            post["raw_json"] = json.loads(post["raw_json"])
        posts.append(post)

    conn.close()
    return posts


def get_post(post_id: str) -> dict | None:
    """Get single post by ID"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        post = dict(row)
        if post["images"]:
            post["images"] = json.loads(post["images"])
        if post["comments"]:
            post["comments"] = json.loads(post["comments"])
        if post["raw_json"]:
            post["raw_json"] = json.loads(post["raw_json"])
        return post
    return None


def update_post_comments(post_id: str, comments: list[dict]) -> None:
    """Update comments for a post"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE posts SET comments = ? WHERE id = ?", (json.dumps(comments), post_id)
    )

    conn.commit()
    conn.close()


def get_unprocessed_posts(limit: int | None = None) -> list[dict]:
    """Get posts that haven't been processed yet"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM posts WHERE processed_at IS NULL ORDER BY created_utc ASC"
    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)

    posts = []
    for row in cursor.fetchall():
        post = dict(row)
        if post["images"]:
            post["images"] = json.loads(post["images"])
        if post["comments"]:
            post["comments"] = json.loads(post["comments"])
        if post["raw_json"]:
            post["raw_json"] = json.loads(post["raw_json"])
        posts.append(post)

    conn.close()
    return posts


def delete_post(post_id: str) -> None:
    """Delete a post from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM posts WHERE id = ?", (post_id,))

    conn.commit()
    conn.close()


def mark_post_processed(post_id: str) -> None:
    """Mark a post as processed with current timestamp"""
    from datetime import datetime, timezone

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE posts SET processed_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), post_id),
    )

    conn.commit()
    conn.close()
