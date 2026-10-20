import os
import sys
import time
import webbrowser
import uvicorn

def main():
    port = 8000
    host = "127.0.0.1"
    url = f"http://{host}:{port}"

    print("=" * 65)
    print(" ExamLens AI — Examination Quality & Syllabus-Alignment Auditor ")
    print("=" * 65)
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

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    # Run Uvicorn
    uvicorn.run("backend.app:app", host=host, port=port, reload=False, log_level="info")

if __name__ == "__main__":
    main()
