"""Serve the launch site locally; keep publication and DNS separate."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(SimpleHTTPRequestHandler):
    def send_error(self, code, message=None, explain=None):
        page = Path(self.directory) / "404.html"
        if code != 404 or not page.is_file():
            return super().send_error(code, message, explain)
        body = page.read_bytes()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parents[1] / "dist/website")
    parser.add_argument("--port", type=int, default=8820)
    args = parser.parse_args()
    if not (args.directory / "index.html").is_file():
        parser.error("Build the website first.")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(args.directory.resolve())))
    print(f"Local: http://127.0.0.1:{server.server_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
