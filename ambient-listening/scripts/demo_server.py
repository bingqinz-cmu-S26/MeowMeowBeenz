"""Demo server for the cat-audio → mood pipeline (for screen recording).

Serves the demo webpage and runs the REAL AST+probe on POST /classify.
Run:   .venv/bin/python scripts/demo_server.py     then open http://localhost:8000
"""
import json, sys, time, contextlib, io
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

REPO = Path(__file__).resolve().parent.parent
DEMO = REPO / "demo"
sys.path.insert(0, str(REPO / "scripts"))

print("Loading AST + probe (once)...")
import warnings; warnings.filterwarnings("ignore")
with contextlib.redirect_stderr(io.StringIO()):
    from cat_mood import CatMood
    MODEL = CatMood()
print("Ready. Open http://localhost:7777")

CLIPS = {  # bucket -> demo audio file
    "content": DEMO / "assets" / "clip_content.wav",
    "agitated": DEMO / "assets" / "clip_agitated.wav",
    "distress": DEMO / "assets" / "clip_distress.wav",
}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(200, (DEMO / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path.startswith("/assets/") and path.endswith(".wav"):
            f = DEMO / "assets" / Path(path).name  # basename only (no traversal)
            if f.exists():
                self._send(200, f.read_bytes(), "audio/wav")
            else:
                self._send(404, b"not found", "text/plain")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/classify":
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            clip = dict(p.split("=", 1) for p in qs.split("&") if "=" in p).get("clip", "content")
            target = CLIPS.get(clip, CLIPS["content"])
            with contextlib.redirect_stderr(io.StringIO()):
                r = MODEL.classify(str(target))
            time.sleep(0.6)  # let the "classifying..." stage read on video
            self._send(200, json.dumps(r).encode())
        elif self.path == "/backend":
            # simulate the owner's backend receiving the event
            length = int(self.headers.get("Content-Length", 0))
            payload = self.rfile.read(length).decode() if length else "{}"
            print("→ backend received:", payload)
            self._send(200, json.dumps({"status": "ok", "received": True}).encode())
        else:
            self._send(404, b"not found", "text/plain")


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 7777), H).serve_forever()
