# Purple Check Agent
This agent uses information from the web to populate the Purple Check database with reviews/feedback of pages on Instagram (currently focused on e-commerce).
# Specs
- Production Purple Check (Turso Cloud libsql/sqlite3) database is connected. The schema is available in schema.sql.
- Posts from Reddit subreddits are saved in `data/<subreddit-name>` in the format provided by the public JSON API. 
    - These posts are validated and concatenated into a single `data/merged_posts.json` by the `tools/extract_posts.py` script.
- Any requests to public websites like reddit should be made through `tools/curlfire` which uses my firefox cookies and headers to avoid getting blocked.
# Agent Workflow
## 1. Fetch posts (Incremental)
The system now supports incremental fetching of new posts:
- **Checkpoint tracking**: `data/fetch_state.json` tracks the last fetched post per subreddit
- **Incremental fetch**: Run `python fetch_posts.py` to fetch only new posts since last run
- **Simplified storage**: Only `posts.json` files are maintained (no individual `t3_*.json` files)
- **API integration**: Uses Reddit's `/new.json` endpoint with `before` parameter
- **Authentication**: Uses `curlfire` with Firefox cookies to avoid rate limiting

### Usage:
```bash
# Fetch new posts incrementally (updates posts.json directly)
python fetch_posts.py

# Create merged_posts.json from subreddit posts.json files
python tools/extract_posts.py

# Process new posts
python main.py
```

### Scheduling (cron example):
```bash
# Run daily at 2 AM
0 2 * * * cd /path/to/agent && python fetch_posts.py && python tools/extract_posts.py && python main.py
```

### File Structure:
```
data/
├── fetch_state.json          # Tracks last fetched post per subreddit
├── InstagramShops/
│   ├── posts.json           # All posts for this subreddit (updated incrementally)
│   └── end.json             # Original end marker from initial fetch
├── InstaShoppingFails/
│   ├── posts.json           # All posts for this subreddit (updated incrementally)
│   └── end.json             # Original end marker from initial fetch
└── merged_posts.json        # Combined posts from all subreddits
```

### Key Changes:
1. **No individual `t3_*.json` files** - Posts are stored directly in `posts.json`
2. **Deduplication** - Duplicate posts are automatically filtered out
3. **Chronological ordering** - Posts are always sorted by creation time
4. **Incremental updates** - Only fetches posts newer than last known post
## 2. Process posts
- Loop through the posts; in each iteration:
    - Determine if the post is relevant by making an LLM API call with the `title`, `self_text` and `media` (if `post["gallery_data"]` is present, then `post["media_metadata"][<for all image_ids from gallery_data>]["s"]["u"]` has the images, else `post["preview"][<for all previews>]["source"]` has the image url)
    - If the post is refers to an Instagram page, and there is enough information to accurately extract the username, then continue. Add it to a list of relevant posts.
    - Fetch comments for the post using `post["permalink"]` and `fetch_comments` function and add them to the post object.
    - Determine if there is enough information to confidently say if the post is positive or negative feedback by providing the entire post and images to an LLM API call and save the result to the post object.
    - Finally, add the data to the database.