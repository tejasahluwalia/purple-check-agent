import json
from pathlib import Path

# Define the data directory
data_dir = Path(__file__).parent.parent / "data"

# List to hold all extracted post data
all_posts = []

print("Creating merged posts file from subreddit posts.json files...")
print("=" * 60)

# Iterate through both subdirectories
for subreddit_dir in data_dir.iterdir():
    if subreddit_dir.is_dir():
        print(f"\nProcessing {subreddit_dir.name}...")

        posts_file = subreddit_dir / "posts.json"

        if posts_file.exists():
            try:
                with open(posts_file, "r", encoding="utf-8") as f:
                    subreddit_posts = json.load(f)

                print(f"  Found {len(subreddit_posts)} posts in {posts_file.name}")
                all_posts.extend(subreddit_posts)

            except Exception as e:
                print(f"  Error reading {posts_file.name}: {e}")
        else:
            print(f"  No posts.json file found in {subreddit_dir.name}")

# Sort all posts by creation time (oldest first)
all_posts.sort(key=lambda post: post.get("created_utc", 0.0))

print(f"\n{'=' * 60}")
print(f"Total posts to merge: {len(all_posts)}")

# Remove duplicates based on post ID
seen_ids = set()
unique_posts = []
duplicates = 0

for post in all_posts:
    post_id = post.get("name")  # Reddit uses 'name' field (e.g., t3_xxx)
    if post_id:
        if post_id in seen_ids:
            duplicates += 1
        else:
            seen_ids.add(post_id)
            unique_posts.append(post)
    else:
        # If no post_id, include it anyway
        unique_posts.append(post)

print(f"Duplicates removed: {duplicates}")
print(f"Unique posts: {len(unique_posts)}")

# Save merged file
output_file = data_dir / "merged_posts.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(unique_posts, f, indent=2, ensure_ascii=False)

print(f"\nMerged data saved to {output_file}")
