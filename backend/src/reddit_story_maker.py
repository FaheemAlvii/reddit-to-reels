"""
Reddit Story Maker. Fetches and processes Reddit posts for video generation.

Author: Faheem Alvi
GitHub: https://github.com/FaheemAlvii
LinkedIn: https://www.linkedin.com/in/faheem-alvi
Email: faheemalvi2000@gmail.com
License: CC BY-NC 4.0
"""
import requests
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple


if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class RedditStoryMaker:
    """
    Fetches Reddit posts from a specified subreddit with customizable filters,
    tracks used posts, and saves post data organized by post ID.
    """
    
    def __init__(self, config_filename: str = "config.json"):
        """Initialize with configuration file."""
        self.config_path = os.path.join(PROJECT_ROOT, config_filename)
        self.config = self._load_config(self.config_path)
        self.used_posts = self._load_used_posts()
        self.headers = {
            'User-Agent': 'RedditStoryMaker/1.0'
        }
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found: {config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")
    
    def _load_used_posts(self) -> List[str]:
        """Load list of already used post IDs."""
        used_posts_file = self.config['output']['used_posts_file']
        # Resolve absolute path for used_posts_file
        self.used_posts_path = os.path.join(PROJECT_ROOT, used_posts_file)
        
        if os.path.exists(self.used_posts_path):
            try:
                with open(self.used_posts_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse {self.used_posts_path}, starting fresh")
                return []
        return []
    
    def _save_used_posts(self):
        """Save the list of used post IDs."""
        with open(self.used_posts_path, 'w', encoding='utf-8') as f:
            json.dump(self.used_posts, f, indent=2)
        print(f"✓ Updated used posts list: {len(self.used_posts)} posts tracked")
    
    def _fetch_json(self, url: str) -> Optional[Dict]:
        """Fetch JSON data from a URL with error handling."""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"✗ Error fetching {url}: {e}")
            return None
    
    def _meets_filters(self, post_data: Dict) -> Tuple[bool, str]:
        """
        Check if a post meets all configured filters.
        Returns (meets_filters, reason_if_not)
        """
        filters = self.config['filters']
        
        # Check upvotes
        if post_data.get('score', 0) < filters['min_upvotes']:
            return False, f"Upvotes ({post_data.get('score', 0)}) below minimum ({filters['min_upvotes']})"
        
        # Check comments
        num_comments = post_data.get('num_comments', 0)
        if num_comments < filters['min_comments']:
            return False, f"Comments ({num_comments}) below minimum ({filters['min_comments']})"
        if num_comments > filters['max_comments']:
            return False, f"Comments ({num_comments}) above maximum ({filters['max_comments']})"
        
        # Check age
        created_utc = post_data.get('created_utc', 0)
        post_age = datetime.now(timezone.utc) - datetime.fromtimestamp(created_utc, timezone.utc)
        min_age = timedelta(hours=filters['min_age_hours'])
        max_age = timedelta(hours=filters['max_age_hours'])
        
        if post_age < min_age:
            return False, f"Post too new ({post_age.total_seconds()/3600:.1f}h < {filters['min_age_hours']}h)"
        if post_age > max_age:
            return False, f"Post too old ({post_age.total_seconds()/3600:.1f}h > {filters['max_age_hours']}h)"
        
        # Check NSFW
        if post_data.get('over_18', False) and not filters['allow_nsfw']:
            return False, "Post is NSFW"
        
        # Check selftext requirement
        if filters['require_selftext'] and not post_data.get('selftext', '').strip():
            return False, "Post has no selftext"
        
        return True, "All filters passed"
    
    def fetch_subreddit_posts(self, subreddit: str = None, limit: int = 25, sort: str = "hot") -> List[Dict]:
        """
        Fetch posts from the configured subreddit.
        Returns list of post data dictionaries.
        sort: one of 'best', 'hot', 'new', 'rising', 'top'
        """
        if not subreddit:
            # Fallback for backward compatibility or default
            subreddit = self.config.get('subreddit', 'AskReddit')
        
        valid_sorts = ["best", "hot", "new", "rising", "top"]
        if sort not in valid_sorts:
            sort = "hot"
            
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
        if sort == "top":
            url += "&t=week"
        
        print(f"\nFetching posts from r/{subreddit}...")
        data = self._fetch_json(url)
        
        if not data:
            return []
        
        posts = []
        children = data.get('data', {}).get('children', [])
        
        for child in children:
            if child.get('kind') == 't3':  # t3 = post
                posts.append(child.get('data', {}))
        
        print(f"✓ Retrieved {len(posts)} posts from subreddit")
        return posts
    
    def find_suitable_post(self) -> Optional[Dict]:
        """
        Find a post that meets all filters and hasn't been used yet.
        Returns the post data or None if no suitable post found.
        """
        # Get subreddits list (support both new list and old single string for backward compat)
        subreddits = self.config.get('subreddits', [])
        if not subreddits and 'subreddit' in self.config:
            subreddits = [self.config['subreddit']]
            
        if not subreddits:
            print("Error: No subreddits configured")
            return None

        request_delay = self.config.get('request_delay', 2.0)
        
        for i, subreddit in enumerate(subreddits):
            # Add delay between subreddit requests (but not before the first one)
            if i > 0:
                print(f"\nWaiting {request_delay}s before checking next subreddit...")
                time.sleep(request_delay)
                
            posts = self.fetch_subreddit_posts(subreddit=subreddit, limit=100)
            
            print(f"\n📋 Filtering posts from r/{subreddit}...")
            print(f"   Already used: {len(self.used_posts)} posts")
            
            for post in posts:
                post_id = post.get('id')
                
                # Skip if already used
                if post_id in self.used_posts:
                    continue
                
                # Check filters
                meets_filters, reason = self._meets_filters(post)
                
                if meets_filters:
                    print(f"\n✓ Found suitable post in r/{subreddit}!")
                    print(f"   ID: {post_id}")
                    print(f"   Title: {post.get('title', 'N/A')[:80]}...")
                    print(f"   Upvotes: {post.get('score', 0)}")
                    print(f"   Comments: {post.get('num_comments', 0)}")
                    return post
                else:
                    print(f"   Skipped {post_id}: {reason}")
        
        print("\nWARNING: No suitable posts found matching the criteria in any configured subreddit.")
        return None
    
    def fetch_post_details(self, post_url: str) -> Optional[List]:
        """
        Fetch detailed post data including comments.
        Returns [post_data, comments_data] or None.
        """
        # Ensure URL ends with .json
        if not post_url.endswith('.json'):
            post_url = post_url.rstrip('/') + '/.json'
        
        print(f"\nFetching post details...")
        data = self._fetch_json(post_url)
        
        if data and isinstance(data, list) and len(data) >= 2:
            print(f"Retrieved post details with comments")
            return data
        
        print(f"Failed to retrieve post details")
        return None
    
    def save_post_data(self, post_id: str, post_data: Dict, full_data: List):
        """
        Save post data to a folder named by post_id.
        Saves both the summary and full JSON data.
        """
        posts_dir = os.path.join(PROJECT_ROOT, self.config['output']['posts_directory'])
        post_folder = os.path.join(posts_dir, post_id)
        
        # Create directory
        os.makedirs(post_folder, exist_ok=True)
        
        # Save summary info
        summary = {
            'id': post_id,
            'title': post_data.get('title'),
            'author': post_data.get('author'),
            'subreddit': post_data.get('subreddit'),
            'score': post_data.get('score'),
            'upvote_ratio': post_data.get('upvote_ratio'),
            'num_comments': post_data.get('num_comments'),
            'created_utc': post_data.get('created_utc', 0),
            'created_datetime': datetime.fromtimestamp(post_data.get('created_utc', 0), timezone.utc).isoformat(),
            'url': post_data.get('url'),
            'permalink': post_data.get('permalink'),
            'selftext': post_data.get('selftext'),
            'over_18': post_data.get('over_18'),
            'is_video': post_data.get('is_video'),
            'downloaded_at': datetime.now(timezone.utc).isoformat()
        }
        
        summary_path = os.path.join(post_folder, 'summary.json')
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        # Save full data (post + comments)
        full_path = os.path.join(post_folder, 'full_data.json')
        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nSaved post data to: {post_folder}")
        print(f"   - summary.json (key information)")
        print(f"   - full_data.json (complete post + comments)")
    
    def process_new_post(self) -> Optional[str]:
        """
        Main workflow: Find a suitable post, fetch details, and save.
        Returns post_id if successful, None otherwise.
        """
        # Find a suitable post
        post = self.find_suitable_post()
        
        if not post:
            return None
        
        post_id = post.get('id')
        post_url = post.get('url')
        
        # Fetch full post details
        full_data = self.fetch_post_details(post_url)
        
        if not full_data:
            return None
        
        # Save the data
        self.save_post_data(post_id, post, full_data)
        
        # Mark as used
        self.used_posts.append(post_id)
        self._save_used_posts()
        
        print(f"\nSaved post: {post_id}")
        return post_id


def main():
    """Main entry point."""
    print("=" * 60)
    print("Reddit Story Maker")
    print("=" * 60)
    
    try:
        maker = RedditStoryMaker()
        success = maker.process_new_post()
        
        if success:
            print("\n" + "=" * 60)
            print("Process completed successfully!")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("WARNING: No suitable post found matching the criteria.")
            print("=" * 60)
            
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
