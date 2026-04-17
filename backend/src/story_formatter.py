import json
import os
import sys
from typing import Dict, List, Optional
from datetime import datetime
from content_cleaner import clean_profanity


if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class StoryFormatter:
    """
    Formats Reddit post data into narration-ready scripts.
    """
    
    def __init__(self, post_id: str):
        """Initialize with post ID."""
        self.post_id = post_id
        # Use PROJECT_ROOT to find posts directory
        self.output_dir = os.path.join(PROJECT_ROOT, "posts", post_id)
        # Fix: load summary and full_data separately as per existing methods
        self.post_folder = self.output_dir  # Needed for _load_summary and _load_full_data
        self.summary = self._load_summary()
        self.full_data = self._load_full_data()
    
    def _load_summary(self) -> Dict:
        """Load the summary.json file."""
        summary_path = os.path.join(self.post_folder, "summary.json")
        if not os.path.exists(summary_path):
            raise FileNotFoundError(f"Summary not found: {summary_path}")
        
        with open(summary_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_full_data(self) -> List:
        """Load the full_data.json file."""
        full_path = os.path.join(self.post_folder, "full_data.json")
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Full data not found: {full_path}")
        
        with open(full_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_all_comments(self, min_score: int = 0) -> List[Dict]:
        """
        Public method to get all top-level comments for display/selection.
        Returns list sorted by score descending.
        """
        return self._extract_top_comments(max_comments=999, min_score=min_score)

    def _extract_top_comments(self, max_comments: int = 10, min_score: int = 10) -> List[Dict]:
        """
        Extract top-level comments from the post.
        Returns list of comment dictionaries with author, body, and score.
        """
        if len(self.full_data) < 2:
            return []
        
        comments_listing = self.full_data[1]  # Second element is comments
        if not isinstance(comments_listing, dict):
            return []
        
        children = comments_listing.get('data', {}).get('children', [])
        
        top_comments = []
        for child in children:
            if child.get('kind') != 't1':  # t1 = comment
                continue
            
            comment_data = child.get('data', {})
            score = comment_data.get('score', 0)
            body = comment_data.get('body', '').strip()
            author = comment_data.get('author', '[deleted]')
            
            # Skip deleted, removed, or low-score comments
            if body and score >= min_score and body not in ['[deleted]', '[removed]']:
                top_comments.append({
                    'author': author,
                    'body': body,
                    'score': score,
                    'created_utc': comment_data.get('created_utc', 0)
                })
        
        # Sort by score (highest first) and limit
        top_comments.sort(key=lambda x: x['score'], reverse=True)
        return top_comments[:max_comments]
    
    def format_story_mode(self) -> str:
        """
        Format as Story Mode: Just the post text.
        Returns clean, TTS-ready story text.
        """
        title = self.summary.get('title', '')
        selftext = self.summary.get('selftext', '')
        
        # If there's no selftext, use the title as the story
        if not selftext or selftext.strip() == '':
            story = f"{title}"
        else:
            story = f"{title}\n\n{selftext}"
        
        # Clean up for TTS
        story = self._clean_for_tts(story)
        
        return story
    
    def format_qa_mode(self, max_comments: int = 10, min_comment_score: int = 10,
                       selected_indices: Optional[List[int]] = None,
                       max_comment_chars: int = 0) -> str:
        """
        Format as Q&A Mode: Post + top comments with usernames.
        selected_indices: if provided, only include comments at these 0-based indices (in the given order).
        max_comment_chars: if > 0, skip comments longer than this many characters.
        Returns TTS-ready narration script.
        """
        title = self.summary.get('title', '')
        selftext = self.summary.get('selftext', '')
        author = self.summary.get('author', 'Anonymous')
        
        # Start with the post
        script = f"{title}"
        
        if selftext and selftext.strip():
            script += f"\n\n{selftext}"
        
        script += "\n\n" + "="*60 + "\n"
        script += "Top Comments:\n"
        script += "="*60 + "\n\n"
        
        # Get all top comments first
        all_comments = self._extract_top_comments(max_comments, min_comment_score)
        
        # Apply char limit filter
        if max_comment_chars > 0:
            all_comments = [c for c in all_comments if len(c['body']) <= max_comment_chars]
        
        # Apply selection filter
        if selected_indices is not None:
            comments = [all_comments[i] for i in selected_indices if 0 <= i < len(all_comments)]
        else:
            comments = all_comments
        
        if not comments:
            script += "\nNo comments available.\n"
        else:
            for i, comment in enumerate(comments, 1):
                script += f"Comment {i} by {comment['author']} ({comment['score']} upvotes):\n"
                script += f"{comment['body']}\n\n"
                script += "-" * 60 + "\n\n"
        
        # Clean up for TTS
        script = self._clean_for_tts(script)
        
        return script
    
    def _clean_for_tts(self, text: str) -> str:
        """
        Clean text for TTS narration.
        Removes markdown, URLs, and other TTS-unfriendly elements.
        Also replaces profanity with family-friendly alternatives.
        Preserves [PAUSE:N] markers for interactive content.
        """
        import re

        # Temporarily protect [PAUSE:N] markers
        pause_markers = {}
        def _protect_pause(m):
            key = f"__PAUSE_PLACEHOLDER_{len(pause_markers)}__"
            pause_markers[key] = m.group(0)
            return key
        text = re.sub(r'\[PAUSE:\d+\]', _protect_pause, text)

        # Remove markdown links [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        
        # Remove standalone URLs
        text = re.sub(r'https?://\S+', '[link]', text)
        
        # Remove markdown formatting
        text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*([^\*]+)\*', r'\1', text)      # Italic
        text = re.sub(r'~~([^~]+)~~', r'\1', text)       # Strikethrough
        
        # Remove excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove Reddit-specific formatting
        text = text.replace('&gt;', '>')
        text = text.replace('&lt;', '<')
        text = text.replace('&amp;', '&')
        
        # Replace profanity with clean alternatives
        text = clean_profanity(text)

        # Restore [PAUSE:N] markers
        for key, original in pause_markers.items():
            text = text.replace(key, original)
        
        return text.strip()
    
    def save_formatted_story(self, mode: str, output_filename: Optional[str] = None) -> str:
        """
        Save formatted story to a file.
        mode: 'story' or 'qa'
        Returns the path to the saved file.
        """
        if mode.lower() == 'story':
            content = self.format_story_mode()
            default_filename = "story_mode.txt"
        elif mode.lower() == 'qa':
            content = self.format_qa_mode()
            default_filename = "qa_mode.txt"
        else:
            raise ValueError("Mode must be 'story' or 'qa'")
        
        filename = output_filename or default_filename
        output_path = os.path.join(self.post_folder, filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return output_path


def interactive_mode():
    """Interactive CLI for formatting posts."""
    print("=" * 60)
    print("Reddit Story Formatter")
    print("=" * 60)
    
    # List available posts
    posts_dir = os.path.join(PROJECT_ROOT, "posts")
    if not os.path.exists(posts_dir):
        print(f"\n✗ No posts directory found. Run reddit_story_maker.py first!")
        return
    
    post_folders = [d for d in os.listdir(posts_dir) if os.path.isdir(os.path.join(posts_dir, d))]
    
    if not post_folders:
        print(f"\n✗ No posts found. Run reddit_story_maker.py first!")
        return
    
    print(f"\n📁 Available posts ({len(post_folders)}):\n")
    for i, post_id in enumerate(post_folders, 1):
        # Try to load summary for preview
        try:
            summary_path = os.path.join(posts_dir, post_id, "summary.json")
            with open(summary_path, 'r', encoding='utf-8') as f:
                summary = json.load(f)
                title = summary.get('title', 'No title')[:60]
                print(f"{i}. {post_id} - {title}...")
        except:
            print(f"{i}. {post_id}")
    
    # Select post
    while True:
        try:
            choice = input(f"\nSelect post number (1-{len(post_folders)}): ").strip()
            post_index = int(choice) - 1
            if 0 <= post_index < len(post_folders):
                selected_post = post_folders[post_index]
                break
            else:
                print("Invalid number. Try again.")
        except ValueError:
            print("Please enter a number.")
        except KeyboardInterrupt:
            print("\n\nCancelled.")
            return
    
    # Select mode
    print("\n" + "=" * 60)
    print("Select formatting mode:")
    print("=" * 60)
    print("1. Story Mode - Just the post text (clean story)")
    print("2. Q&A Mode - Post + top comments with usernames")
    
    while True:
        try:
            mode_choice = input("\nSelect mode (1 or 2): ").strip()
            if mode_choice in ['1', '2']:
                break
            else:
                print("Please enter 1 or 2.")
        except KeyboardInterrupt:
            print("\n\nCancelled.")
            return
    
    # Format the post
    try:
        formatter = StoryFormatter(selected_post)
        
        print("\n" + "=" * 60)
        print("Formatting...")
        print("=" * 60)
        
        if mode_choice == '1':
            mode = 'story'
            content = formatter.format_story_mode()
            print("\n📝 Story Mode Output:\n")
        else:
            mode = 'qa'
            # Ask for comment settings
            try:
                max_comments = input("\nMax comments to include (default 10): ").strip()
                max_comments = int(max_comments) if max_comments else 10
                
                min_score = input("Minimum comment score (default 10): ").strip()
                min_score = int(min_score) if min_score else 10
                
                content = formatter.format_qa_mode(max_comments, min_score)
            except ValueError:
                print("Using defaults...")
                content = formatter.format_qa_mode()
            
            print("\n💬 Q&A Mode Output:\n")
        
        print("-" * 60)
        print(content)
        print("-" * 60)
        
        # Save option
        save = input("\n💾 Save to file? (y/n): ").strip().lower()
        if save == 'y':
            output_path = formatter.save_formatted_story(mode)
            print(f"\n✅ Saved to: {output_path}")
        
        print("\n" + "=" * 60)
        print("✅ Formatting complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point with CLI argument support."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Format Reddit posts for TTS')
    parser.add_argument('post_id', nargs='?', help='Post ID to format (optional for interactive mode)')
    parser.add_argument('--mode', choices=['story', 'qa'], default='qa', help='Formatting mode (default: qa)')
    
    args = parser.parse_args()
    
    if args.post_id:
        # Non-interactive mode with post_id argument
        try:
            formatter = StoryFormatter(args.post_id)
            
            # Save formatted story
            formatter.save_formatted_story(args.mode)
            print(f"Formatted {args.post_id} in {args.mode.upper()} Mode")
            
            sys.exit(0)
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)
    else:
        # Interactive mode
        interactive_mode()


if __name__ == "__main__":
    main()
