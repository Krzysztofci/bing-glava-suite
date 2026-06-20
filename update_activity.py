import urllib.request
import json
import re

GITHUB_USERNAME = "Krzysztofci"
HTML_FILE_PATH = "index.html"
MAX_COMMITS = 5

def fetch_latest_commits():
    url = f"https://api.github.com/search/commits?q=author:{GITHUB_USERNAME}&sort=author-date&order=desc&per_page={MAX_COMMITS}"
    headers = {
        "User-Agent": "Python-Commit-Search-Bot",
        "Accept": "application/vnd.github.cloak-preview+json"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            return data.get("items", [])
    except Exception as e:
        print(f"Błąd: {e}")
        return []

def parse_commits(items):
    parsed_commits = []
    for item in items:
        repo_name = item.get("repository", {}).get("name", "unknown")
        commit_data = item.get("commit", {}).get("author", {})
        date_str = commit_data.get("date", "")
        time_str = date_str[11:16] if len(date_str) > 16 else "--:--"
        msg = item.get("commit", {}).get("message", "").split("\n")[0]
        
        parsed_commits.append({
            "time": time_str,
            "repo": repo_name,
            "branch": "main",  # Trzymamy pusty placeholder dla kolumny branch
            "msg": msg
        })
    return parsed_commits

def generate_html_rows(commits):
    if not commits:
        return '      <div class="status-row"><span class="status-msg">No recent activity found.</span></div>'
        
    html_rows = []
    for c in commits:
        row = f"""      <div class="status-row">
        <span class="status-time">[{c['time']}]</span>
        <span class="status-repo">{c['repo']}</span>
        <span class="status-branch">{c['branch']}</span>
        <span class="status-msg">{c['msg']}</span>
      </div>"""
        html_rows.append(row)
    return "\n".join(html_rows)

def update_index_html(new_html_content):
    with open(HTML_FILE_PATH, "r", encoding="utf-8") as file:
        content = file.read()
        
    pattern = r'(<div class="status-body">)(.*?)(</div>)'
    if not re.search(pattern, content, flags=re.DOTALL):
        print("Brak sekcji status-body")
        return
        
    modified_content = re.sub(pattern, rf"\1\n{new_html_content}\n    \3", content, flags=re.DOTALL)
    with open(HTML_FILE_PATH, "w", encoding="utf-8") as file:
        file.write(modified_content)

if __name__ == "__main__":
    commit_items = fetch_latest_commits()
    latest_commits = parse_commits(commit_items)
    html_markup = generate_html_rows(latest_commits)
    update_index_html(html_markup)
