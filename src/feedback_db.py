import os

import libsql
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("TURSO_DATABASE_URL")
auth_token = os.getenv("TURSO_AUTH_TOKEN")

conn = libsql.connect("../data/db/purple-check.db", sync_url=url, auth_token=auth_token)  # type: ignore[unresolved-attribute]
conn.sync()


def insert_feedback(
    giver: str,
    receiver: str,
    sentiment: str,
):
    """Insert feedback into database"""
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
            (giver, receiver, rating, ""),
        )

        conn.commit()
        print(f"✓ Inserted feedback: {giver} -> {receiver} ({rating})")

    except Exception as e:
        print(f"Error inserting feedback: {e}")
        raise
