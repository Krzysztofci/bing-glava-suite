import json
import re
import urllib.request

# ── KONFIGURACJA ──
GITHUB_USERNAME = "Krzysztofci"  # Twój login na GH
HTML_FILE_PATH = "index.html"
MAX_COMMITS = 3  # Ile maksymalnie wpisów chcesz pokazać w stopce


def fetch_github_activity():
    url = f"https://api.github.com/users/{GITHUB_USERNAME}/events/public"
    headers = {"User-Agent": "Python-Urllib-Activity-Bot"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Błąd pobierania danych z API: {e}")
        return []


def parse_commits(events):
    parsed_commits = []

    for event in events:
        if len(parsed_commits) >= MAX_COMMITS:
            break

        # Interesują nas tylko zdarzenia typu Push (wypchnięcie commitów)
        if event.get("type") == "PushEvent":
            repo_name = event.get("repo", {}).get("name", "").split("/")[-1]
            ref = event.get("payload", {}).get("ref", "")
            branch = ref.replace("refs/heads/", "") if ref else "unknown"

            # API zwraca czas w formacie ISO, wyciągamy samą godzinę i minuty
            created_at = event.get("created_at", "")
            time_str = (
                created_at[11:16] if len(created_at) > 16 else "--:--"
            )  # np. "22:14"

            commits = event.get("payload", {}).get("commits", [])
            # Iterujemy od najnowszych commitów w danym pushu
            for commit in reversed(commits):
                if len(parsed_commits) >= MAX_COMMITS:
                    break

                msg = commit.get("message", "").split("\n")[0]  # tylko pierwsza linia
                parsed_commits.append(
                    {
                        "time": time_str,
                        "repo": repo_name,
                        "branch": branch,
                        "msg": msg,
                    }
                )

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

    # Wyrażenie regularne, które znajdzie wszystko wewnątrz <div class="status-body">...</div>
    pattern = r'(<div class="status-body">)(.*?)(</div>)'
    modified_content = re.sub(
        pattern,
        rf"\1\n{new_html_content}\n    \3",
        content,
        flags=re.DOTALL,
    )

    with open(HTML_FILE_PATH, "w", encoding="utf-8") as file:
        file.write(modified_content)
    print("Plik index.html został pomyślnie zaktualizowany!")


if __name__ == "__main__":
    print("Uruchamianie bota aktualizacji...")
    raw_events = fetch_github_activity()
    latest_commits = parse_commits(raw_events)
    html_markup = generate_html_rows(latest_commits)
    update_index_html(html_markup)
