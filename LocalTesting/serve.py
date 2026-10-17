"""Test server for the Web GUI: serves the whole repository (the folder above this one) with caching turned off,
on the first free port from 8000."""
import functools, http.server, os, socket, sys, webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the repository root: "Single Generator/" and WebGUI/ sit here


class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # the browser must always load the files from this folder, never an older copy it kept
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def log_message(self, *args):
        pass


def free_port(start=8000):
    for port in range(start, start + 50):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    sys.exit("No free port between 8000 and 8049")


port = free_port()
url = f"http://localhost:{port}/WebGUI/"
server = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(NoCache, directory=ROOT))
print(f"Serving {ROOT}")
print(f"Open {url}   (close this window or press Ctrl+C to stop)")
webbrowser.open(url)
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
