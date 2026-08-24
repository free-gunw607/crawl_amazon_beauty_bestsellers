from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .pipeline import Pipeline


def build_handler(pipeline: Pipeline):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, payload, status=200):
            body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            parts = [p for p in parsed.path.split("/") if p]
            if parsed.path == "/health":
                self._json({"ok": True})
            elif parts and parts[0] == "categories":
                self._json(pipeline.registry.all_entries())
            elif parts and parts[0] == "latest" and len(parts) >= 2:
                rows = pipeline.store.latest_snapshot(parts[1])
                self._json({"node_id": parts[1], "count": len(rows), "entries": rows})
            elif parts and parts[0] == "history":
                params = parse_qs(parsed.query)
                asin = (params.get("asin") or [""])[0]
                if not asin:
                    self._json({"error": "asin query param required"}, 400)
                    return
                self._json({"asin": asin, "history": pipeline.store.history_for_asin(asin)})
            elif parts and parts[0] == "stats":
                self._json(pipeline.store.stats())
            else:
                self._json(
                    {
                        "endpoints": [
                            "/health",
                            "/categories",
                            "/latest/{node_id}",
                            "/history?asin=",
                            "/stats",
                        ]
                    },
                    404,
                )

        def log_message(self, fmt, *args):
            print("[api]", fmt % args)

    return Handler


def serve(settings, host: str = "127.0.0.1", port: int = 8790):
    pipeline = Pipeline(settings)
    server = ThreadingHTTPServer((host, port), build_handler(pipeline))
    print(f"read API listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        pipeline.close()
