import urllib.request
import json
import re

GITHUB_USERNAME = "Krzysztofci"
HTML_FILE_PATH = "index.html"
MAX_COMMITS = 5

def fetch_latest_activity():
    # Przechodzimy na Events API - szybsze, dokładniejsze i zawiera informacje o branchach
    url = f"https://api.github.com/users/{GITHUB_USERNAME}/events/public"
    headers = {
        "User-Agent": "Python-Activity-Monitor-Bot",
        "Accept": "application/vnd.github+json"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Błąd pobierania danych z API: {e}")
        return []

def parse_events(events):
    parsed_commits = []
    
    for event in events:
        if len(parsed_commits) >= MAX_COMMITS:
            break
            
        # Interesują nas tylko zdarzenia typu Push (wypchnięcie nowych commitów)
        if event.get("type") != "PushEvent":
            continue
            
        repo_name = event.get("repo", {}).get("name", "unknown").split("/")[-1]
        
        # Wyciąganie nazwy brancha (np. "refs/heads/main" -> "main")
        ref = event.get("payload", {}).get("ref", "")
        branch_name = ref.split("/")[-1] if ref else "unknown"
        
        # Parsowanie czasu (format: 2026-06-24T15:30:00Z -> 15:30)
        created_at = event.get("created_at", "")
        time_str = created_at[11:16] if len(created_at) > 16 else "--:--"
        
        # Przetwarzanie commitów wewnątrz danego Pusha (od najnowszego)
        commits = event.get("payload", {}).get("commits", [])
        for commit in reversed(commits):
            if len(parsed_commits) >= MAX_COMMITS:
                break
                
            full_msg = commit.get("message", "")
            msg = full_msg.split("\n")[0] if full_msg else "No commit message"
            
            parsed_commits.append({
                "time": time_str,
                "repo": repo_name,
                "branch": branch_name,
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
        
    # Bezpieczny regex, który nigdy nie wyjdzie poza wyznaczone komentarze HTML
    pattern = r"(<!-- ACTIVITY_START -->)[\s\S]*?(<!-- ACTIVITY_END -->)"
    
    if not re.search(pattern, content):
        print("Błąd: Nie znaleziono znaczników komentarza <!-- ACTIVITY_START --> w index.html")
        return
        
    # Zastępuje całą starą zawartość nową, gwarantując idempotentność
    modified_content = re.sub(pattern, f"\\1\n{new_html_content}\n\\2", content)
    
    with open(HTML_FILE_PATH, "w", encoding="utf-8") as file:
        file.write(modified_content)

if __name__ == "__main__":
    events_data = fetch_latest_activity()
    latest_commits = parse_events(events_data)
    html_markup = generate_html_rows(latest_commits)
    update_index_html(html_markup)
