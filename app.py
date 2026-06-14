"""
MacBook Cleanup Manager — Flask backend
Scans storage-heavy locations and allows selective cleanup.
"""

import os
import shutil
import subprocess
import json
from pathlib import Path
from flask import Flask, jsonify, request, render_template
CLOUD_MODE = os.getenv("CLOUD_MODE", "0") == "1"
app = Flask(__name__)

HOME = Path.home()

# ---------------------------------------------------------------------------
# Category definitions
# Each entry has:
#   id, name, desc, icon  — display metadata
#   scan_fn               — callable that returns size in bytes
#   clean_fn              — callable that performs cleanup, returns bytes freed
# ---------------------------------------------------------------------------

def _du(path: Path) -> int:
    """Return size of path in bytes using du, or 0 if not found."""
    try:
        if not path.exists():
            return 0
        result = subprocess.run(
            ["du", "-sk", str(path)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            kb = int(result.stdout.split()[0])
            return kb * 1024
    except Exception:
        pass
    return 0


def _du_glob(pattern_paths: list) -> int:
    """Sum du across a list of Path objects."""
    total = 0
    for p in pattern_paths:
        total += _du(p)
    return total


def _rm_contents(path: Path) -> int:
    """Delete contents of a directory (not the directory itself). Returns bytes freed."""
    before = _du(path)
    if not path.exists():
        return 0
    for child in path.iterdir():
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except Exception:
            pass
    return before


def _rm_path(path: Path) -> int:
    """Delete a path entirely. Returns bytes freed."""
    size = _du(path)
    try:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    except Exception:
        pass
    return size


# --- Docker ---
def scan_docker():
    try:
        result = subprocess.run(
            ["docker", "system", "df", "--format", "{{json .}}"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return 0
        total = 0
        for line in result.stdout.strip().splitlines():
            obj = json.loads(line)
            size_str = obj.get("Size", "0B")
            total += _parse_docker_size(size_str)
        return total
    except Exception:
        return 0


def _parse_docker_size(s: str) -> int:
    s = s.strip().upper().replace(" ", "")
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    for suffix, mult in sorted(units.items(), key=lambda x: -len(x[0])):
        if s.endswith(suffix):
            try:
                return int(float(s[:-len(suffix)]) * mult)
            except Exception:
                return 0
    return 0


def clean_docker():
    try:
        result = subprocess.run(
            ["docker", "system", "prune", "-af", "--volumes"],
            capture_output=True, text=True, timeout=120
        )
        # Parse reclaimed space from output
        for line in result.stdout.splitlines():
            if "reclaimed" in line.lower():
                parts = line.split()
                for i, p in enumerate(parts):
                    if p.lower() == "space" and i + 1 < len(parts):
                        return _parse_docker_size(parts[i + 1])
    except Exception:
        pass
    return 0


# --- Ollama ---
OLLAMA_PATH = HOME / ".ollama" / "models"

def scan_ollama():
    return _du(OLLAMA_PATH)

def clean_ollama():
    return _rm_contents(OLLAMA_PATH)


# --- Xcode DerivedData ---
XCODE_DERIVED = HOME / "Library" / "Developer" / "Xcode" / "DerivedData"

def scan_xcode():
    return _du(XCODE_DERIVED)

def clean_xcode():
    return _rm_contents(XCODE_DERIVED)


# --- UTM ---
UTM_PATH = HOME / "Library" / "Containers" / "com.utmapp.UTM" / "Data" / "Documents"

def scan_utm():
    return _du(UTM_PATH)

def clean_utm():
    return _rm_contents(UTM_PATH)


# --- Parallels ---
PARALLELS_PATH = HOME / "Parallels"

def scan_parallels():
    return _du(PARALLELS_PATH)

def clean_parallels():
    return _rm_contents(PARALLELS_PATH)


# --- Downloads ---
DOWNLOADS_PATH = HOME / "Downloads"

def scan_downloads():
    return _du(DOWNLOADS_PATH)

def clean_downloads():
    return _rm_contents(DOWNLOADS_PATH)


# --- Library Caches ---
LIB_CACHES = HOME / "Library" / "Caches"

def scan_libcache():
    return _du(LIB_CACHES)

def clean_libcache():
    return _rm_contents(LIB_CACHES)


# --- VS Code ---
VSCODE_PATHS = [
    HOME / "Library" / "Application Support" / "Code" / "logs",
    HOME / "Library" / "Application Support" / "Code" / "CachedExtensionVSIXs",
    HOME / "Library" / "Application Support" / "Code" / "CachedData",
    HOME / ".vscode" / "extensions" / ".obsolete",
]

def scan_vscode():
    return _du_glob(VSCODE_PATHS)

def clean_vscode():
    freed = 0
    for p in VSCODE_PATHS:
        freed += _rm_contents(p) if p.is_dir() else _rm_path(p)
    return freed


# --- Gemini cache ---
GEMINI_PATHS = [
    HOME / "Library" / "Application Support" / "Google" / "Gemini",
    HOME / "Library" / "Caches" / "com.google.Gemini",
]

def scan_gemini():
    return _du_glob(GEMINI_PATHS)

def clean_gemini():
    freed = 0
    for p in GEMINI_PATHS:
        freed += _rm_contents(p)
    return freed


# --- Antigravity cache ---
ANTIGRAVITY_PATHS = [
    HOME / "Library" / "Caches" / "Antigravity",
    HOME / "Library" / "Application Support" / "Antigravity",
]

def scan_antigravity():
    return _du_glob(ANTIGRAVITY_PATHS)

def clean_antigravity():
    freed = 0
    for p in ANTIGRAVITY_PATHS:
        freed += _rm_contents(p)
    return freed


# --- Trash ---
TRASH_PATH = HOME / ".Trash"


def _get_trash_size_applescript() -> int:
    """Return total size of Trash using AppleScript, or 0 in cloud mode."""
    if CLOUD_MODE:
        # Cloud environment cannot access macOS Finder; skip.
        return 0
    try:
        script = '''tell application "Finder"
          set total_size to 0
          repeat with i in (get items of trash)
            try
              set total_size to total_size + (size of i)
            end try
          end repeat
          return total_size
        end tell'''
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            out = result.stdout.strip()
            if out:
                return int(float(out))
    except Exception:
        pass
    return 0
    # stray except removed


def _list_trash_files_applescript() -> list:
    """Return list of Trash items via AppleScript, or empty list in cloud mode."""
    if CLOUD_MODE:
        return []
    files = []
    try:
        script = '''tell application "Finder"
          set out to ""
          repeat with i in (get items of trash)
            try
              set p to POSIX path of (i as alias)
              set n to name of i
              set s to size of i
              set k to kind of i
              set out to out & n & ";" & s & ";" & p & ";" & k & "\n"
            end try
          end repeat
          return out
        end tell'''
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                parts = line.split(";")
                if len(parts) >= 3:
                    name = parts[0]
                    size_str = parts[1]
                    path = parts[2]
                    kind = parts[3] if len(parts) > 3 else ""
                    
                    try:
                        size = int(float(size_str))
                    except Exception:
                        size = 0
                        
                    is_dir = "folder" in kind.lower() or "package" in kind.lower()
                    
                    files.append({
                        "name": name,
                        "path": path,
                        "size": size,
                        "is_dir": is_dir,
                        "type": "directory" if is_dir else "file"
                    })
    except Exception as e:
        print("AppleScript Trash list failed:", e)
    return files


def scan_trash():
    size = _get_trash_size_applescript()
    if size > 0:
        return size
    return _du(TRASH_PATH)


def clean_trash():
    try:
        subprocess.run(["osascript", "-e", 'tell application "Finder" to empty trash'],
                       capture_output=True, timeout=30)
    except Exception:
        pass
    return _rm_contents(TRASH_PATH)


# --- Temp files ---
TMP_PATHS = [Path("/private/tmp"), Path("/private/var/folders")]

def scan_tmp():
    return _du_glob(TMP_PATHS)

def clean_tmp():
    freed = 0
    for p in TMP_PATHS:
        freed += _rm_contents(p)
    return freed


# ---------------------------------------------------------------------------
CATEGORIES = [
    {
        "id": "docker",
        "name": "Docker",
        "desc": "Images, containers, volumes, build cache",
        "icon": "brand-docker",
        "scan": scan_docker,
        "clean": clean_docker,
        "warning": None,
    },
    {
        "id": "ollama",
        "name": "Ollama models",
        "desc": "Local LLM model weights (~/.ollama/models)",
        "icon": "brain",
        "scan": scan_ollama,
        "clean": clean_ollama,
        "warning": "This will delete all downloaded LLM models. Re-downloading takes time.",
    },
    {
        "id": "xcode",
        "name": "Xcode DerivedData",
        "desc": "Build artifacts and indexes",
        "icon": "hammer",
        "scan": scan_xcode,
        "clean": clean_xcode,
        "warning": None,
    },
    {
        "id": "utm",
        "name": "UTM virtual machines",
        "desc": "Virtual machine disk images",
        "icon": "server",
        "scan": scan_utm,
        "clean": clean_utm,
        "warning": "This will permanently delete UTM virtual machines.",
    },
    {
        "id": "parallels",
        "name": "Parallels VMs",
        "desc": "Parallels Desktop disk images (~/Parallels)",
        "icon": "server-2",
        "scan": scan_parallels,
        "clean": clean_parallels,
        "warning": "This will permanently delete Parallels virtual machines.",
    },
    {
        "id": "downloads",
        "name": "Downloads folder",
        "desc": "All files in ~/Downloads",
        "icon": "download",
        "scan": scan_downloads,
        "clean": clean_downloads,
        "warning": "This will delete everything in your Downloads folder.",
    },
    {
        "id": "libcache",
        "name": "Library Caches",
        "desc": "App caches in ~/Library/Caches",
        "icon": "archive",
        "scan": scan_libcache,
        "clean": clean_libcache,
        "warning": None,
    },
    {
        "id": "vscode",
        "name": "VS Code cache",
        "desc": "Logs, cached extensions, old data",
        "icon": "brand-vscode",
        "scan": scan_vscode,
        "clean": clean_vscode,
        "warning": None,
    },
    {
        "id": "gemini",
        "name": "Gemini cache",
        "desc": "Google Gemini app cache",
        "icon": "sparkles",
        "scan": scan_gemini,
        "clean": clean_gemini,
        "warning": None,
    },
    {
        "id": "antigravity",
        "name": "Antigravity cache",
        "desc": "Antigravity app cache files",
        "icon": "apps",
        "scan": scan_antigravity,
        "clean": clean_antigravity,
        "warning": None,
    },
    {
        "id": "trash",
        "name": "Trash",
        "desc": "Files in macOS Trash (~/.Trash)",
        "icon": "trash",
        "scan": scan_trash,
        "clean": clean_trash,
        "warning": None,
    },
    {
        "id": "tmp",
        "name": "Temp files",
        "desc": "System temporary files (/private/tmp)",
        "icon": "file-off",
        "scan": scan_tmp,
        "clean": clean_tmp,
        "warning": None,
    },
]

CAT_MAP = {c["id"]: c for c in CATEGORIES}


def get_category_paths(category_id: str) -> list:
    if category_id == "docker":
        return []
    elif category_id == "ollama":
        return [OLLAMA_PATH]
    elif category_id == "xcode":
        return [XCODE_DERIVED]
    elif category_id == "utm":
        return [UTM_PATH]
    elif category_id == "parallels":
        return [PARALLELS_PATH]
    elif category_id == "downloads":
        return [DOWNLOADS_PATH]
    elif category_id == "libcache":
        return [LIB_CACHES]
    elif category_id == "vscode":
        return VSCODE_PATHS
    elif category_id == "gemini":
        return GEMINI_PATHS
    elif category_id == "antigravity":
        return ANTIGRAVITY_PATHS
    elif category_id == "trash":
        return [TRASH_PATH]
    elif category_id == "tmp":
        return TMP_PATHS
    return []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/scan")
def api_scan():
    """Scan all categories and return sizes."""
    results = []
    total_disk, used_disk, free_disk = shutil.disk_usage("/")
    for cat in CATEGORIES:
        try:
            size = cat["scan"]()
        except Exception:
            size = 0
        results.append({
            "id": cat["id"],
            "name": cat["name"],
            "desc": cat["desc"],
            "icon": cat["icon"],
            "warning": cat["warning"],
            "size": size,
        })
    results.sort(key=lambda x: x["size"], reverse=True)
    return jsonify({
        "categories": results,
        "disk_total": total_disk,
        "disk_used": used_disk,
        "disk_free": free_disk,
    })


@app.route("/api/category-files/<category_id>")
def api_category_files(category_id):
    """List sub-files and folders under a category."""
    files = []
    
    # Special handling for Docker
    if category_id == "docker":
        try:
            # Get docker images
            img_result = subprocess.run(
                ["docker", "images", "--format", "{{json .}}"],
                capture_output=True, text=True, timeout=10
            )
            if img_result.returncode == 0:
                for line in img_result.stdout.strip().splitlines():
                    try:
                        obj = json.loads(line)
                        repo = obj.get("Repository", "<none>")
                        tag = obj.get("Tag", "<none>")
                        size_str = obj.get("Size", "0B")
                        size = _parse_docker_size(size_str)
                        files.append({
                            "name": f"Image: {repo}:{tag}",
                            "path": f"docker://image/{repo}:{tag}",
                            "size": size,
                            "is_dir": False,
                            "type": "docker_image"
                        })
                    except Exception:
                        pass
            # Get docker containers
            cont_result = subprocess.run(
                ["docker", "ps", "-a", "--format", "{{json .}}"],
                capture_output=True, text=True, timeout=10
            )
            if cont_result.returncode == 0:
                for line in cont_result.stdout.strip().splitlines():
                    try:
                        obj = json.loads(line)
                        name = obj.get("Names", "<none>")
                        image = obj.get("Image", "<none>")
                        size_str = obj.get("Size", "0B")
                        size = 0
                        if "virtual" in size_str:
                            import re
                            m = re.search(r'virtual\s+([0-9a-zA-Z\.]+)', size_str)
                            if m:
                                size = _parse_docker_size(m.group(1))
                        else:
                            parts = size_str.split()
                            if parts:
                                size = _parse_docker_size(parts[0])
                        
                        files.append({
                            "name": f"Container: {name} ({image})",
                            "path": f"docker://container/{name}",
                            "size": size,
                            "is_dir": False,
                            "type": "docker_container"
                        })
                    except Exception:
                        pass
        except Exception as e:
            print("Docker listing failed:", e)
    elif category_id == "trash":
        files = _list_trash_files_applescript()
        if not files:
            paths = get_category_paths(category_id)
            for p in paths:
                if not p.exists():
                    continue
                if p.is_file():
                    files.append({
                        "name": p.name,
                        "path": str(p),
                        "size": p.stat().st_size,
                        "is_dir": False,
                        "type": "file"
                    })
                elif p.is_dir():
                    try:
                        for child in p.iterdir():
                            try:
                                is_dir = child.is_dir()
                                size = _du(child) if is_dir else child.stat().st_size
                                files.append({
                                    "name": child.name,
                                    "path": str(child),
                                    "size": size,
                                    "is_dir": is_dir,
                                    "type": "directory" if is_dir else "file"
                                })
                            except Exception:
                                pass
                    except Exception:
                        pass
    else:
        paths = get_category_paths(category_id)
        for p in paths:
            if not p.exists():
                continue
            if p.is_file():
                files.append({
                    "name": p.name,
                    "path": str(p),
                    "size": p.stat().st_size,
                    "is_dir": False,
                    "type": "file"
                })
            elif p.is_dir():
                try:
                    for child in p.iterdir():
                        try:
                            is_dir = child.is_dir()
                            size = _du(child) if is_dir else child.stat().st_size
                            files.append({
                                "name": child.name,
                                "path": str(child),
                                "size": size,
                                "is_dir": is_dir,
                                "type": "directory" if is_dir else "file"
                            })
                        except Exception:
                            pass
                except Exception:
                    pass
    
    # Sort files by size descending
    files.sort(key=lambda x: x["size"], reverse=True)
    
    # Limit to top 100 items to avoid overloading the browser
    files = files[:100]
    
    # Return root paths for this category that exist
    root_paths = [str(p) for p in get_category_paths(category_id) if p.exists()]
    
    return jsonify({
        "files": files,
        "root_paths": root_paths
    })


@app.route("/api/open", methods=["POST"])
def api_open():
    """Open a path/file in Finder."""
    data = request.get_json() or {}
    path_str = data.get("path")
    if not path_str:
        return jsonify({"success": False, "error": "No path provided"}), 400
        
    if path_str.startswith("docker://"):
        return jsonify({"success": False, "error": "Docker items cannot be opened in Finder"}), 400
        
    p = Path(path_str)
    try:
        if not p.exists():
            original_p = p
            while p != p.parent and not p.exists():
                p = p.parent
            if not p.exists():
                return jsonify({"success": False, "error": f"Path '{original_p}' does not exist"}), 404
        
        # Use macOS Finder reveal if file, open folder if directory
        if p.is_file():
            subprocess.run(["open", "-R", str(p)], check=True)
        else:
            subprocess.run(["open", str(p)], check=True)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/delete-path", methods=["POST"])
def api_delete_path():
    """Delete a specific path inside safe zones."""
    data = request.get_json() or {}
    path_str = data.get("path")
    if not path_str:
        return jsonify({"success": False, "error": "No path provided"}), 400
        
    if path_str.startswith("docker://"):
        try:
            if path_str.startswith("docker://image/"):
                img_name = path_str[len("docker://image/"):]
                result = subprocess.run(["docker", "rmi", "-f", img_name], capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    return jsonify({"success": True, "size_freed": 0})
                else:
                    return jsonify({"success": False, "error": result.stderr}), 400
            elif path_str.startswith("docker://container/"):
                cont_name = path_str[len("docker://container/"):]
                subprocess.run(["docker", "stop", cont_name], capture_output=True, timeout=15)
                result = subprocess.run(["docker", "rm", cont_name], capture_output=True, text=True, timeout=15)
                if result.returncode == 0:
                    return jsonify({"success": True, "size_freed": 0})
                else:
                    return jsonify({"success": False, "error": result.stderr}), 400
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
            
    p = Path(path_str).resolve()
    
    is_safe = False
    try:
        if p.is_relative_to(HOME) or p.is_relative_to("/private/tmp") or p.is_relative_to("/private/var"):
            is_safe = True
    except ValueError:
        pass
        
    if not is_safe:
        return jsonify({"success": False, "error": "Forbidden: Path is outside allowable directories."}), 403
        
    critical_paths = [HOME, HOME / "Library", Path("/"), Path("/private"), Path("/private/tmp"), Path("/private/var")]
    if p in critical_paths or p.parent == Path("/"):
        return jsonify({"success": False, "error": "Forbidden: Cannot delete critical directories."}), 403
        
    try:
        if not p.exists():
            return jsonify({"success": False, "error": "Path does not exist"}), 404
            
        size_freed = _rm_path(p)
        return jsonify({"success": True, "size_freed": size_freed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/clean", methods=["POST"])
def api_clean():
    """Clean selected category IDs. Returns total bytes freed."""
    data = request.get_json()
    ids = data.get("ids", [])
    freed_total = 0
    details = []
    for cid in ids:
        cat = CAT_MAP.get(cid)
        if not cat:
            continue
        try:
            freed = cat["clean"]()
        except Exception:
            freed = 0
        freed_total += freed
        details.append({"id": cid, "freed": freed})
    return jsonify({"freed_total": freed_total, "details": details})


    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
