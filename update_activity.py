#!/usr/bin/env python3

import html
import json
import urllib.request
from datetime import datetime

USERNAME = "Krzysztofci"
INDEX_FILE = "index.html"
MAX_COMMITS = 5

START_MARKER = "<!-- COMMITS_START -->"
END_MARKER   = "<!-- COMMITS_END -->"


def github_get(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "gh-pages-activity-bot",
            "Accept": "application/vnd.github+json"
        }
    )

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def fetch_events():
    url = f"https://api.github.com/users/{USERNAME}/events/public"

    try:
        return github_get(url)

    except Exception as e:
        print(f"GitHub API error: {e}")
        return []


def collect_commits(events):

    commits = []

    for event in events:

        if event["type"] != "PushEvent":
            continue

        repo = event["repo"]["name"]

        for commit in event["payload"]["commits"]:

            msg = commit["message"].splitlines()[0]

            if msg.startswith("Merge"):
                continue

            commits.append(
                {
                    "repo": repo,
                    "msg": msg,
                    "sha": commit["sha"][:7],
                    "url": f"https://github.com/{repo}/commit/{commit['sha']}",
                    "time": event["created_at"]
                }
            )

    commits.sort(
        key=lambda x: x["time"],
        reverse=True
    )

    return commits[:MAX_COMMITS]


def format_time(iso):

    dt = datetime.fromisoformat(
        iso.replace("Z", "+00:00")
    )

    return dt.strftime("%H:%M")


def generate_html(commits):

    if not commits:

        return """
<div class="status-row">
  <span class="status-msg">No recent activity.</span>
</div>
"""

    rows = []

    for c in commits:

        repo = html.escape(c["repo"])
        msg = html.escape(c["msg"])

        rows.append(f"""
<div class="status-row">
  <span class="status-time">[{format_time(c["time"])}]</span>

  <a class="status-repo"
     href="https://github.com/{repo}"
     target="_blank">
     {repo}
  </a>

  <span class="status-msg">
     <a href="{c["url"]}" target="_blank">
        {msg}
     </a>
  </span>
</div>
""")

    return "\n".join(rows)


def update_index(new_html):

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if START_MARKER not in content:
        raise RuntimeError("COMMITS_START missing")

    if END_MARKER not in content:
        raise RuntimeError("COMMITS_END missing")

    before, rest = content.split(START_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)

    updated = (
        before
        + START_MARKER
        + "\n"
        + new_html
        + "\n"
        + END_MARKER
        + after
    )

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(updated)

    print("HTML updated")


if __name__ == "__main__":

    events = fetch_events()

    commits = collect_commits(events)

    html_fragment = generate_html(commits)

    update_index(html_fragment)
