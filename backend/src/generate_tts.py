"""
Generate TTS audio for formatted Reddit posts.
Supports both Story Mode and Q&A Mode with multiple voices.
"""
import os
import sys
import json
from story_formatter import StoryFormatter
from tts_engine import TTSManager


if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def generate_audio_for_post(post_id: str, mode: str = 'qa', config_filename: str = "config.json"):
    """
    Generate TTS audio for a specific post.
    
    Args:
        post_id: Post ID to generate audio for
        mode: 'story' or 'qa'
        config_filename: Config file name (located in project root)
        
    Returns:
        True if successful, False otherwise
    """
    print("=" * 60)
    print(f"TTS Audio Generator - {mode.upper()} Mode")
    print("=" * 60)
    
    config_path = os.path.join(PROJECT_ROOT, config_filename)
    
    # Load configuration
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Initialize TTS manager
    tts_manager = TTSManager(config_filename)
    
    if not tts_manager.enabled:
        print("\nWARNING: TTS is disabled in config.json")
        print("Set 'tts.enabled' to true to enable TTS generation")
        return False
    
    # Load post data
    try:
        formatter = StoryFormatter(post_id)
    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
        return False
    
    if mode == 'story':
        # Generate Story Mode audio
        story_text = formatter.format_story_mode()
        
        print(f"\nPost: {formatter.summary.get('title', 'N/A')[:60]}...")
        print(f"Voice: {tts_manager.main_voice}")
        print(f"Text length: {len(story_text)} characters")
        
        audio_path = tts_manager.generate_story_mode_audio(post_id, story_text)
        
        if audio_path:
            print(f"\nSUCCESS: Story audio generated: {audio_path}")
            return True
        else:
            print(f"\nERROR: Failed to generate audio")
            return False
    
    elif mode == 'qa':
        # Generate Q&A Mode audio
        title = formatter.summary.get('title', '')
        selftext = formatter.summary.get('selftext', '')
        author = formatter.summary.get('author', 'Anonymous')
        
        # Create post text
        post_text = f"{title}"
        if selftext and selftext.strip():
            post_text += f". {selftext}"
        
        # Extract comments
        max_comments = config.get('formatting', {}).get('max_comments', 10)
        min_score = config.get('formatting', {}).get('min_comment_score', 10)
        comments = formatter._extract_top_comments(max_comments, min_score)
        
        print(f"\nPost: {title[:60]}...")
        print(f"Comments: {len(comments)}")
        print(f"Main voice: {tts_manager.main_voice}")
        print(f"Multiple voices: {tts_manager.use_multiple_voices}")
        
        results = tts_manager.generate_qa_mode_audio(post_id, post_text, comments)
        
        if results.get('post'):
            print(f"\nSUCCESS: Generated audio files:")
            print(f"   Post: {results['post']}")
            
            for comment_info in results.get('comments', []):
                print(f"   Comment {comment_info['index']} ({comment_info['voice']}): {comment_info['audio_path']}")
            return True
        else:
            print(f"\nERROR: Failed to generate audio")
            return False
    
    else:
        print(f"\nERROR: Invalid mode: {mode}. Use 'story' or 'qa'")
        return False


def interactive_mode():
    """Interactive CLI for generating TTS audio."""
    print("=" * 60)
    print("Reddit TTS Audio Generator")
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
    print("Select TTS mode:")
    print("=" * 60)
    print("1. Story Mode - Single voice (main post only)")
    print("2. Q&A Mode - Multiple voices (post + comments)")
    
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
    
    mode = 'story' if mode_choice == '1' else 'qa'
    
    # Generate audio
    print()
    generate_audio_for_post(selected_post, mode)
    
    print("\n" + "=" * 60)
    print("✅ TTS generation complete!")
    print("=" * 60)


def batch_generate_all():
    """Generate TTS for all posts in both modes."""
    posts_dir = os.path.join(PROJECT_ROOT, "posts")
    
    if not os.path.exists(posts_dir):
        print("No posts directory found!")
        return
    
    post_folders = [d for d in os.listdir(posts_dir) 
                   if os.path.isdir(os.path.join(posts_dir, d))]
    
    if not post_folders:
        print("No posts found!")
        return
    
    print(f"Found {len(post_folders)} posts. Generating TTS for all...\n")
    
    for post_id in post_folders:
        print(f"\n{'='*60}")
        print(f"Processing: {post_id}")
        print('='*60)
        
        try:
            # Generate both modes
            print("\n[Story Mode]")
            generate_audio_for_post(post_id, 'story')
            
            print("\n[Q&A Mode]")
            generate_audio_for_post(post_id, 'qa')
            
        except Exception as e:
            print(f"✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Batch TTS generation complete!")
    print("=" * 60)


def main():
    """Main entry point with CLI argument support."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate TTS audio for Reddit posts')
    parser.add_argument('post_id', nargs='?', help='Post ID to generate audio for (optional for interactive mode)')
    parser.add_argument('--mode', choices=['story', 'qa'], default='qa', help='TTS mode (default: qa)')
    
    args = parser.parse_args()
    
    if args.post_id:
        # Non-interactive mode with post_id argument
        try:
            success = generate_audio_for_post(args.post_id, args.mode)
            sys.exit(0 if success else 1)
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)
    elif len(sys.argv) > 1 and sys.argv[1] == 'batch':
        batch_generate_all()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
