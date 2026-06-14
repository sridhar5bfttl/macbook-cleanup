# MacBook Cleanup Manager

A Python + web app to analyse and selectively clean storage-heavy areas on macOS.

## Setup

```bash
# 1. Install dependencies
pip3 install -r requirements.txt

# 2. Run the server
python3 app.py
```

Then open **http://127.0.0.1:5000** in your browser.

## What it cleans

| Category | Path |
|---|---|
| Docker | `docker system prune -af --volumes` |
| Ollama models | `~/.ollama/models` |
| Xcode DerivedData | `~/Library/Developer/Xcode/DerivedData` |
| UTM VMs | `~/Library/Containers/com.utmapp.UTM/…` |
| Parallels VMs | `~/Parallels` |
| Downloads | `~/Downloads` |
| Library Caches | `~/Library/Caches` |
| VS Code cache | Logs, CachedData, CachedExtensionVSIXs |
| Gemini cache | `~/Library/Caches/com.google.Gemini` |
| Antigravity cache | `~/Library/Caches/Antigravity` |
| Trash | `~/.Trash` (via Finder AppleScript) |
| Temp files | `/private/tmp` |

## Safety

- Nothing is deleted until you explicitly select items and click **Clean selected**
- A confirmation modal lists exactly what will be deleted before anything happens
- Items with irreversible consequences (VMs, Ollama models, Downloads) are flagged with a ⚠️ warning

## API

| Endpoint | Method | Description |
|---|---|---|
| `GET /api/scan` | GET | Scans all categories, returns sizes in bytes |
| `POST /api/clean` | POST | Cleans selected IDs. Body: `{"ids": ["docker", "trash", ...]}` |
