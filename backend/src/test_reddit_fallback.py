"""
Tests for Reddit scraping methods and fallback functionality.
"""
import unittest
from unittest.mock import patch
import os
import sys

# Ensure backend/src is on sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from reddit_story_maker import RedditStoryMaker
from reddit_browser_scraper import _clean_post_url


class TestRedditScrapingFallback(unittest.TestCase):

    def test_clean_post_url(self):
        self.assertEqual(
            _clean_post_url("https://www.reddit.com/r/AskReddit/comments/12345/title/.json"),
            "https://www.reddit.com/r/AskReddit/comments/12345/title"
        )
        self.assertEqual(
            _clean_post_url("https://www.reddit.com/r/AskReddit/comments/12345/title.json"),
            "https://www.reddit.com/r/AskReddit/comments/12345/title"
        )
        self.assertEqual(
            _clean_post_url("12345"),
            "https://www.reddit.com/comments/12345"
        )
        self.assertEqual(
            _clean_post_url("r/AskReddit/comments/12345"),
            "https://www.reddit.com/r/AskReddit/comments/12345"
        )

    def test_scraping_method_config(self):
        maker = RedditStoryMaker()
        maker.config["scraping_method"] = "browser"
        self.assertEqual(maker.scraping_method, "browser")

        maker.config["scraping_method"] = "auto"
        self.assertEqual(maker.scraping_method, "auto")

        maker.config["scraping_method"] = "json"
        self.assertEqual(maker.scraping_method, "json")

    @patch("reddit_browser_scraper.scrape_subreddit_posts")
    def test_browser_mode_does_not_call_fetch_json(self, mock_browser_posts):
        mock_browser_posts.return_value = [{"id": "abc", "title": "Test Post"}]
        maker = RedditStoryMaker()
        maker.config["scraping_method"] = "browser"

        with patch.object(maker, "_fetch_json") as mock_fetch_json:
            posts = maker.fetch_subreddit_posts("AskReddit")
            mock_fetch_json.assert_not_called()
            mock_browser_posts.assert_called_once()
            self.assertEqual(len(posts), 1)
            self.assertEqual(posts[0]["id"], "abc")

    @patch("reddit_browser_scraper.scrape_post_details")
    def test_browser_mode_post_details_does_not_call_fetch_json(self, mock_browser_details):
        mock_browser_details.return_value = [{"kind": "Listing", "data": {"children": []}}, {"kind": "Listing", "data": {"children": []}}]
        maker = RedditStoryMaker()
        maker.config["scraping_method"] = "browser"

        with patch.object(maker, "_fetch_json") as mock_fetch_json:
            data = maker.fetch_post_details("https://www.reddit.com/r/AskReddit/comments/abc/test/.json")
            mock_fetch_json.assert_not_called()
            mock_browser_details.assert_called_once()
            self.assertIsNotNone(data)

    @patch("reddit_browser_scraper.scrape_subreddit_posts")
    def test_auto_mode_falls_back_when_json_fails(self, mock_browser_posts):
        mock_browser_posts.return_value = [{"id": "fallback_post", "title": "Fallback Success"}]
        maker = RedditStoryMaker()
        maker.config["scraping_method"] = "auto"

        with patch.object(maker, "_fetch_json", return_value=None):
            posts = maker.fetch_subreddit_posts("AskReddit")
            mock_browser_posts.assert_called_once()
            self.assertEqual(len(posts), 1)
            self.assertEqual(posts[0]["id"], "fallback_post")

    @patch("reddit_browser_scraper.scrape_post_details")
    def test_auto_mode_post_details_falls_back_when_json_fails(self, mock_browser_details):
        mock_browser_details.return_value = [
            {"kind": "Listing", "data": {"children": [{"kind": "t3", "data": {"id": "fb1", "title": "Fallback Detail"}}]}},
            {"kind": "Listing", "data": {"children": []}}
        ]
        maker = RedditStoryMaker()
        maker.config["scraping_method"] = "auto"

        with patch.object(maker, "_fetch_json", return_value=None):
            data = maker.fetch_post_details("https://www.reddit.com/comments/fb1")
            mock_browser_details.assert_called_once()
            self.assertIsNotNone(data)
            self.assertEqual(data[0]["data"]["children"][0]["data"]["title"], "Fallback Detail")

    @patch("reddit_browser_scraper.scrape_subreddit_posts")
    def test_json_mode_does_not_fall_back(self, mock_browser_posts):
        maker = RedditStoryMaker()
        maker.config["scraping_method"] = "json"

        with patch.object(maker, "_fetch_json", return_value=None):
            posts = maker.fetch_subreddit_posts("AskReddit")
            mock_browser_posts.assert_not_called()
            self.assertEqual(posts, [])


if __name__ == "__main__":
    unittest.main()
