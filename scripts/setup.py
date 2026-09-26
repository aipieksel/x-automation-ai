#!/usr/bin/env python3
"""Create private local configuration from examples without overwriting edits."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    for source, target in [
        ("config/settings.example.json", "config/settings.json"),
        ("config/accounts.example.json", "config/accounts.json"),
        (".env.example", ".env"),
    ]:
        destination = ROOT / target
        try:
            with destination.open("x") as handle:
                handle.write((ROOT / source).read_text())
            destination.chmod(0o600)
            print(f"Created {target}")
        except FileExistsError:
            print(f"Kept existing {target}")
    print("Add your credentials and cookie path, then enable only your own configured account.")

if __name__ == "__main__":
    main()
