import subprocess
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CURLFIRE_PATH = BASE_DIR / "lib" / "curlfire"


def check_username_exists(username: str) -> bool:
    """
    Check if an Instagram username exists by fetching their profile page
    and looking for OpenGraph meta tags.

    Args:
        username: Instagram username to check

    Returns:
        True if username exists, False otherwise
    """
    url = f"https://www.instagram.com/{username}/"

    try:
        result = subprocess.run(
            [str(CURLFIRE_PATH), url],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        html_content = result.stdout

        return bool(_has_opengraph_tags(html_content))

    except subprocess.CalledProcessError as e:
        print(f"HTTP error checking {username}: {e.stderr[:200]}")
        return False
    except subprocess.TimeoutExpired:
        print(f"Timeout checking {username}")
        return False
    except Exception as e:
        print(f"Error checking {username}: {e}")
        return False


def _has_opengraph_tags(html_content: str) -> bool:
    """
    Check if HTML contains OpenGraph meta tags.

    Valid Instagram profiles have OpenGraph meta tags like:
    - <meta property="og:title" ... />
    - <meta property="og:type" ... />
    - <meta property="og:url" ... />

    Args:
        html_content: HTML content to check

    Returns:
        True if OpenGraph tags are present, False otherwise
    """
    og_pattern = r'<meta\s+(?:[^>]*\s+)?property=["\']og:[^"\']+["\']'

    return bool(re.search(og_pattern, html_content, re.IGNORECASE))


if __name__ == "__main__":
    test_usernames = ["nefsfinds", "thisusernamehopefullydoesnotexist12345"]

    for username in test_usernames:
        exists = check_username_exists(username)
        print(f"{username}: {'EXISTS' if exists else 'DOES NOT EXIST'}")
