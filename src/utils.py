import json
import subprocess
from pathlib import Path

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

        _ = subprocess.run(
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
