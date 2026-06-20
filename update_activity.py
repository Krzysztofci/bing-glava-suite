import json
import re
import urllib.request

# ── KONFIGURACJA ──
GITHUB_USERNAME = "Krzysztofci"
HTML_FILE_PATH = "index.html"
MAX_COMMITS = 3


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

    print(f"Znaleziono {len(events)} ogólnych zdarzeń w API.")

    for event in events:
        if len(parsed_commits) >= MAX_COMMITS:
            break

        if event.get("type") == "PushEvent":
            repo_full_name = event.get("repo", {}).get("name", "unknown/repo")
            repo_name = repo_full_name.split("/")[-1]

            ref = event.get("payload", {}).get("ref", "")
            branch = ref.replace("refs/heads/", "") if ref else "main"

            created_at = event.get("created_at", "")
            time_str = created_at[11:16] if len(created_at) > 16 else "--:--"

            payload = event.get("payload", {})
            commits = payload.get("commits", [])

            print(
                f"Przetwarzanie PushEvent dla {repo_name} [{branch}], zawiera commitów: {len(commits)}"
            )

            # Jeśli z jakiegoś powodu tablica commitów jest pusta, ale push się odbył
            if not commits:
                parsed_commits.append(
                    {
                        "time": time_str,
                        "repo": repo_name,
                        "branch": branch,
                        "msg": "Pushed changes / Updated branch",
                    }
                )
                continue

            for commit in reversed(commits):
                if len(parsed_commits) >= MAX_COMMITS:
                    break

                msg = commit.get("message", "").split("\n")[0]
                if not msg:
                    msg = "No commit message"

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

    pattern = r'(<div class="status-body">)(.*?)(</div>)'

    # Dodatkowe sprawdzenie, czy znacznik w ogóle istnieje w index.html
    if not re.search(pattern, content, flags=re.DOTALL):
        print(
            "BŁĄD: Nie znaleziono sekcji <div class='status-body'> w index.html!"
        )
        return

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
    print(f"Przygotowano {len(latest_commits)} wpisów do wstrzyknięcia.")
    html_markup = generate_html_rows(latest_commits)
    update_index_html(html_markup)
