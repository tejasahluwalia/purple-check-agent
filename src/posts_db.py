import json
import sqlite3
from pathlib import Path

DB_PATH = "../data/db/posts.db"


def create_posts_db():
    """Initialize posts database with schema"""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            name TEXT,
            title TEXT,
            author TEXT,
            selftext TEXT,
            subreddit TEXT,
            created_utc REAL,
            url TEXT,
            permalink TEXT,
            num_comments INTEGER,
            score INTEGER,
            ups INTEGER,
            downs INTEGER,
            upvote_ratio REAL,
            over_18 INTEGER,
            thumbnail TEXT,
            is_gallery INTEGER,
            url_overridden_by_dest TEXT,
            link_flair_text TEXT,
            is_self INTEGER,
            domain TEXT,
            images TEXT,
            comments TEXT,
            raw_json TEXT
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_subreddit ON posts(subreddit)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_utc)")

    conn.commit()
    conn.close()
    print(f"✓ Created posts database at {DB_PATH}")


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


def insert_posts_batch(posts_data: list[tuple[dict, list[str]]]) -> int:
    """Insert multiple posts, returns count inserted"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    inserted = 0
    for post_data, image_urls in posts_data:
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
        inserted += 1

    conn.commit()
    conn.close()
    return inserted


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


def count_posts() -> int:
    """Get total post count"""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    if not Path(DB_PATH).exists():
        return 0
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM posts")
    count = cursor.fetchone()[0]
    conn.close()
    return count
