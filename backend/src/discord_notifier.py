import os
import requests
import time
import json
from datetime import datetime

class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.max_size_bytes = 24 * 1024 * 1024  # 24MB limit (safe margin for 25MB)

    def send_embed(self, title: str, description: str, fields: list = None, color: int = 0xFF4500):
        """Send a rich embed message to Discord."""
        try:
            embed = {
                "title": title,
                "description": description,
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "Reddit Story Maker"
                }
            }
            
            if fields:
                embed["fields"] = fields

            payload = {
                "embeds": [embed]
            }
            
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
            print(f"   ✓ Discord embed sent: {title}")
            return True
        except Exception as e:
            print(f"   ⚠️ Failed to send Discord embed: {e}")
            return False

    def send_message(self, content: str):
        """Send a simple text message to Discord."""
        try:
            payload = {"content": content}
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
            print(f"   ✓ Discord message sent: {content[:50]}...")
            return True
        except Exception as e:
            print(f"   ⚠️ Failed to send Discord message: {e}")
            return False

    def send_file(self, file_path: str, message: str = ""):
        """Upload a file to Discord."""
        if not os.path.exists(file_path):
            print(f"   ⚠️ File not found for Discord upload: {file_path}")
            return False

        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)

        if file_size > self.max_size_bytes:
            print(f"   ⚠️ File {filename} is too large for Discord upload ({file_size/1024/1024:.2f}MB > 24MB). Sending notification only.")
            self.send_message(f"{message}\n\n⚠️ **File too large to upload**: `{filename}` ({file_size/1024/1024:.2f}MB)")
            return False

        print(f"   Uploading {filename} to Discord...")
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f)}
                payload = {'content': message} if message else {}
                response = requests.post(self.webhook_url, data=payload, files=files)
                response.raise_for_status()
            print(f"   ✓ Discord upload successful: {filename}")
            return True
        except Exception as e:
            print(f"   ⚠️ Failed to upload file to Discord: {e}")
            # Try sending just the message if file upload failed
            if message:
                self.send_message(f"{message}\n\n⚠️ **Upload Failed**: `{filename}`")
            return False
