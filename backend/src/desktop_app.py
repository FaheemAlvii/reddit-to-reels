"""
Desktop app wrapper. Launches the FastAPI server and a PyWebView window.

Author: Faheem Alvi
GitHub: https://github.com/FaheemAlvii
LinkedIn: https://www.linkedin.com/in/faheem-alvi
Email: faheemalvi2000@gmail.com
License: CC BY-NC 4.0
"""
import os
import sys
import threading
import time

import uvicorn
import webview


def _get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = _get_base_dir()


def _run_server():
    sys.path.append(os.path.join(BASE_DIR, "backend", "src"))
    from api_server import app  # type: ignore

    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)
    server.run()


def main():
    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()

    for _ in range(50):
        try:
            import socket

            with socket.create_connection(("127.0.0.1", 8000), timeout=0.2):
                break
        except OSError:
            time.sleep(0.2)

    window = webview.create_window("Reddit Reel Maker", "http://127.0.0.1:8000", fullscreen=True)
    webview.start()


if __name__ == "__main__":
    main()
