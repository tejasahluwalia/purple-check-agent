# Purple Check Agent
This agent uses information from reddit to populate the Purple Check database with reviews/feedback of pages on Instagram (currently focused on e-commerce).

# Specs
- Production Purple Check (Turso Cloud libsql/sqlite3) database is connected. The schema is available in schema.sql.
- Posts from Reddit subreddits are saved in `data/<subreddit-name>` in the format provided by the public JSON API. 
    - These posts are validated and added to the `data/db/posts.db` sqlite3 database.
- Any requests to public websites like reddit should be made through `lib/curlfire` which uses my firefox cookies and headers to avoid getting blocked.

# Workflow

## 1. Fetch posts (Incremental)
The system supports incremental fetching of new posts:
- **Incremental fetch**: Run `uv run fetch_posts.py` to fetch only new posts since last run
- **API integration**: Uses Reddit's `/new.json` endpoint with `before` parameter
- **Authentication**: Uses `curlfire` with Firefox cookies to avoid rate limiting

## 2. Agentic loop
- Loop through the posts; in each iteration:
    - Determine if the post is relevant by making an LLM API call with the `title`, `self_text` and `media` (if `post["gallery_data"]` is present, then `post["media_metadata"][<for all image_ids from gallery_data>]["s"]["u"]` has the images, else `post["preview"][<for all previews>]["source"]` has the image url)
    - If the post is refers to an Instagram page, and there is enough information to accurately extract the username, then continue. Add it to a list of relevant posts.
    - Fetch comments for the post using `post["permalink"]` and `fetch_post_comments` function and add them to the post object.
    - Determine if there is enough information to confidently say if the post is positive or negative feedback by providing the entire post and images to an LLM API call and save the result to the post object.
    - Finally, add the data to the database.

## Usage:
```bash
# Fetch new posts incrementally (updates posts.db)
uv run fetch_posts.py

# Process new posts
uv run main.py
```

## File Structure:
```
agent/
├── src/                   # Python source code modules
│   ├── agent.py           # Agentic loop
│   ├── db.py              # Database connection and queries
│   ├── fetch.py           # Reddit data fetching logic
│   ├── llm.py             # LLM API integration
│   └── utils.py           # Shared utilities
├── data/                  # Data storage
│   ├── raw/               # Raw subreddit JSON data
│   │   ├── InstagramShops/
│   │   └── InstaShoppingFails/
│   ├── processed/        # Processed data files
│   │   ├── fetch_state.json
│   │   └── merged_posts.json
│   └── db/               # Database files
├── config/               # Configuration files
│   └── llm_config.json   # LLM provider configuration
├── lib/                # External binaries
│   ├── curlfire          # HTTP client with Firefox cookies
│   └── cookiefire        # Cookie extractor
├── pyproject.toml        # Python dependencies
├── README.md
├── fetch_posts.py        # Entry point: calls src.fetch.main()
├── main.py               # Entry point: calls src.agent.main()
├── extract_posts.py      # Entry point: calls src.extract.main()
└── .env                  # Environment variables
```
