"""
Quick demo script to format all downloaded posts in both modes.
Useful for batch processing.
"""
import os
import sys
import json
from story_formatter import StoryFormatter


if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def batch_format_all_posts():
    """Format all downloaded posts in both modes."""
    posts_dir = os.path.join(PROJECT_ROOT, "posts")
    
    if not os.path.exists(posts_dir):
        print("No posts directory found!")
        return
    
    post_folders = [d for d in os.listdir(posts_dir) 
                   if os.path.isdir(os.path.join(posts_dir, d))]
    
    if not post_folders:
        print("No posts found!")
        return
    
    print(f"Found {len(post_folders)} posts. Formatting all...\n")
    
    for post_id in post_folders:
        try:
            print(f"Processing: {post_id}")
            formatter = StoryFormatter(post_id)
            
            # Format both modes
            story_path = formatter.save_formatted_story('story')
            qa_path = formatter.save_formatted_story('qa')
            
            print(f"  ✓ Story mode: {story_path}")
            print(f"  ✓ Q&A mode: {qa_path}")
            print()
            
        except Exception as e:
            print(f"  ✗ Error: {e}\n")
    
    print("Batch formatting complete!")


if __name__ == "__main__":
    batch_format_all_posts()
