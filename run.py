import argparse
import os
import threading
import webbrowser

from backend.server import run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ระบบออกใบราคากลางบนเครื่องส่วนตัว")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not args.no_browser and os.environ.get("QUOTATION_NO_BROWSER") != "1":
        threading.Timer(1, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()
    try:
        run(port=args.port)
    except KeyboardInterrupt:
        print("ปิดระบบออกใบราคากลางแล้ว")
