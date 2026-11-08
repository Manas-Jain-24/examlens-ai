import os
import sys
import time
import webbrowser
import threading
import uvicorn
from backend.core.config import settings

def main():
    port = settings.PORT
    host = settings.HOST
    url = f"http://{host}:{port}"

    print("=" * 68)
    print(f" {settings.PROJECT_NAME} v{settings.VERSION} — Assessment Quality & Alignment Auditor ")
    print("=" * 68)
    print(f"\n[+] Starting server at: {url}")
    print("[+] Opening dashboard in your default browser...")
    print("[+] Press Ctrl+C in this terminal to stop the server.\n")

    # Open browser after a brief delay so server has started
    def open_browser():
        time.sleep(1.2)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()

    # Run Uvicorn with settings
    uvicorn.run("backend.app:app", host=host, port=port, reload=settings.DEBUG, log_level="info")

if __name__ == "__main__":
    main()
