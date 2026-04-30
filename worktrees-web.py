#!/usr/bin/env python3
"""Tiny server for the git worktrees dashboard. Run and open http://localhost:8787"""

import json
import os
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8787
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCAN_DIR = os.path.dirname(SCRIPT_DIR)


def scan_worktrees():
    repos = []
    repos_scanned = 0

    for entry in sorted(os.listdir(SCAN_DIR)):
        dir_path = os.path.join(SCAN_DIR, entry)
        if not os.path.isdir(dir_path) or not os.path.exists(os.path.join(dir_path, ".git")):
            continue

        repos_scanned += 1
        result = subprocess.run(
            ["git", "-C", dir_path, "worktree", "list", "--porcelain"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            continue

        worktrees = []
        current = {}
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                if current:
                    worktrees.append(current)
                current = {"path": line[9:], "branch": "", "prunable": False, "main": not worktrees and not current}
            elif line.startswith("branch "):
                current["branch"] = line.removeprefix("branch refs/heads/")
            elif line == "detached":
                current["branch"] = "(detached)"
            elif line.startswith("prunable"):
                current["prunable"] = True
        if current:
            worktrees.append(current)

        if len(worktrees) > 1:
            repos.append({"name": entry, "worktrees": worktrees})

    return {"repos": repos, "repos_scanned": repos_scanned}


def remove_worktree(repo_name, worktree_path):
    repo_dir = os.path.join(SCAN_DIR, repo_name)
    if not os.path.isdir(repo_dir):
        return False, f"Repository '{repo_name}' not found"

    # Verify the worktree actually belongs to this repo and is not the main worktree
    result = subprocess.run(
        ["git", "-C", repo_dir, "worktree", "list", "--porcelain"],
        capture_output=True, text=True,
    )
    paths = []
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            paths.append(line[9:])

    if worktree_path not in paths:
        return False, "Worktree not found in this repository"
    if paths and paths[0] == worktree_path:
        return False, "Cannot remove the main worktree"

    result = subprocess.run(
        ["git", "-C", repo_dir, "worktree", "remove", "--force", worktree_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        # Fall back to prune if remove fails (e.g. directory already gone)
        result = subprocess.run(
            ["git", "-C", repo_dir, "worktree", "prune"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return False, result.stderr.strip()

    return True, "Removed"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SCRIPT_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/api/worktrees":
            data = json.dumps(scan_worktrees()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(data))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/":
            self.path = "/worktrees.html"
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/worktrees/remove":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            ok, message = remove_worktree(body["repo"], body["path"])
            status = 200 if ok else 400
            data = json.dumps({"ok": ok, "message": message}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(data))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # silence request logs


if __name__ == "__main__":
    HTTPServer.allow_reuse_address = True
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Worktrees dashboard: http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
