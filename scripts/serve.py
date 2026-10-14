#!/usr/bin/env python3
"""Serve the site at the GitHub Pages base path."""

from __future__ import annotations

import argparse
import functools
import http.server
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview Bump to Baby locally")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    parent = Path(tempfile.mkdtemp(prefix="btb-preview-"))
    (parent / "bump-to-baby").symlink_to(ROOT)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(parent))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Serving {ROOT}")
    print(f"Open http://127.0.0.1:{args.port}/bump-to-baby/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")


if __name__ == "__main__":
    main()
