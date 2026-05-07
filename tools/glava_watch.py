import os
import time

WATCH_PATH = os.path.expanduser("~/.config/glava/")

def get_file_hash():
    """Pobiera pełną zawartość wszystkich plików .glsl do porównania."""
    data = {}
    for root, dirs, files in os.walk(WATCH_PATH):
        if "backup_install" in root: continue
        for file in files:
            if file.endswith(".glsl"):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r') as f:
                        data[path] = f.readlines()
                except: pass
    return data

if __name__ == "__main__":
    print(f"--- Monitoring TOTALNY plików GLSL ---")
    last_state = get_file_hash()
    
    try:
        while True:
            time.sleep(0.5)
            current_state = get_file_hash()
            
            for path, lines in current_state.items():
                if path in last_state and lines != last_state[path]:
                    rel_path = os.path.relpath(path, WATCH_PATH)
                    print(f"\n[{time.strftime('%H:%M:%S')}] ZMIANA W: {rel_path}")
                    
                    # Pokazujemy dokładnie co się zmieniło (stara vs nowa linia)
                    old_lines = last_state[path]
                    for i, line in enumerate(lines):
                        if i < len(old_lines):
                            if line != old_lines[i]:
                                print(f"  STARA: {old_lines[i].strip()}")
                                print(f"  NOWA : {line.strip()}")
                        else:
                            print(f"  DODANO: {line.strip()}")
                
                elif path not in last_state:
                    print(f"[{time.strftime('%H:%M:%S')}] NOWY PLIK: {path}")

            last_state = current_state
    except KeyboardInterrupt:
        print("\nZatrzymano.")