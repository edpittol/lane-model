"""The sample runtime of the lane-model project: a tiny server with real state.

Every request appends a row to a SQLite file in the lane's data directory, so pausing
must keep the file and teardown must remove it. The lane id on the command line is how
the lane tool traces this process to its lane.
"""
import argparse
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

ap = argparse.ArgumentParser()
ap.add_argument("--lane-id", required=True)
ap.add_argument("--port", type=int, required=True)
ap.add_argument("--data", required=True)
args = ap.parse_args()

db = sqlite3.connect(f"{args.data}/hits.db", check_same_thread=False)
db.execute("create table if not exists hits (at real, path text)")
db.commit()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        db.execute("insert into hits values (?, ?)", (time.time(), self.path))
        db.commit()
        n = db.execute("select count(*) from hits").fetchone()[0]
        body = f"lane {args.lane_id}: {n} hit(s) kept in {args.data}\n".encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
