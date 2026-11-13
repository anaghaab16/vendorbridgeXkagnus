"""Run before every push. Fails if a tracked file looks like it contains a secret, or if .env is tracked.

    python scripts/check_secrets.py
"""
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = {
    "database URL with a password": re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^\s:/@]+:(?!USER|PASSWORD|password|\*+|\$)[^\s@/]{4,}@"),
    "Neon password": re.compile(r"npg_[A-Za-z0-9]{8,}"),
    "64-character hex key": re.compile(r"\b[0-9a-f]{64}\b"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "SMTP or API password assignment": re.compile(r"(?i)(smtp_password|secret_key|api_key)\s*=\s*['\"]?(?!replace|change|your|example|test|docs|\s|\"|')[A-Za-z0-9/+_\-]{12,}"),
}
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".pdf", ".ico", ".lock"}
SKIP_NAMES = {"package-lock.json", "check_secrets.py"}

root = Path(__file__).resolve().parent.parent
try:
    tracked = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True).stdout.split("\n")
except Exception:  # not a git checkout: scan the folder instead
    tracked = [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and not {"node_modules", "venv", ".git"} & set(p.parts)]

problems = []
for name in filter(None, tracked):
    p = root / name
    if p.name == ".env" or (p.name.startswith(".env.") and p.name != ".env.example"):
        problems.append(f"{name}: environment file is tracked. Run: git rm --cached {name}")
        continue
    if p.suffix.lower() in SKIP_SUFFIX or p.name in SKIP_NAMES or not p.is_file():
        continue
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        continue
    for label, rx in PATTERNS.items():
        for m in rx.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            problems.append(f"{name}:{line}: looks like a {label}")

if problems:
    print("POSSIBLE SECRETS FOUND. Do not push until these are fixed (and rotate any real secret):\n")
    print("\n".join(" - " + x for x in problems))
    sys.exit(1)
print(f"OK: no secrets found in {len(tracked)} tracked files.")