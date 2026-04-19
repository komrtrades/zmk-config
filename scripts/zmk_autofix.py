#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pathlib
import re
from dataclasses import dataclass


@dataclass
class FixResult:
    changed: bool
    reason: str
    replacements: int = 0


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: pathlib.Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def collect_logs(logs_dir: pathlib.Path) -> str:
    chunks: list[str] = []
    if not logs_dir.exists():
        return ""

    for log_file in logs_dir.rglob("*"):
        if log_file.is_file():
            try:
                chunks.append(read_text(log_file))
            except Exception:
                continue
    return "\n".join(chunks)


def get_zmk_revision(repo_root: pathlib.Path) -> str:
    west = repo_root / "config" / "west.yml"
    if not west.exists():
        return ""

    text = read_text(west)
    m = re.search(r"^\s*revision:\s*([^\s#]+)", text, flags=re.MULTILINE)
    return m.group(1).strip() if m else ""


def apply_regex(content: str, pattern: str, repl: str) -> tuple[str, int]:
    return re.subn(pattern, repl, content, flags=re.MULTILINE)


def fix_build_yaml(repo_root: pathlib.Path, logs_text: str) -> FixResult:
    build_yaml = repo_root / "build.yaml"
    if not build_yaml.exists():
        return FixResult(False, "build.yaml not found")

    original = read_text(build_yaml)
    updated = original
    total = 0

    logs_lower = logs_text.lower()
    revision = get_zmk_revision(repo_root)
    is_main = revision == "main"

    missing_zmk_compat = (
        "missing zmk compat" in logs_lower
        or "selected board is not set up for zmk" in logs_lower
    )
    unknown_nice_nano_v2 = "unknown board" in logs_lower and "nice_nano_v2" in logs_lower

    if not missing_zmk_compat and not unknown_nice_nano_v2:
        return FixResult(False, "No known auto-fixable board error found in logs")

    if is_main:
        # On main (Zephyr 4.1+), use ZMK board variant format.
        updated, n1 = apply_regex(updated, r"(^\s*-\s*board:\s*)nice_nano_v2\s*$", r"\1nice_nano//zmk")
        total += n1
        updated, n2 = apply_regex(updated, r"(^\s*-\s*board:\s*)nice_nano@2(?:\.0\.0)?//zmk\s*$", r"\1nice_nano//zmk")
        total += n2
        updated, n3 = apply_regex(updated, r"(^\s*-\s*board:\s*)nice_nano/nrf52840/zmk\s*$", r"\1nice_nano//zmk")
        total += n3
    else:
        # On stable releases (e.g. v0.3), keep legacy board IDs.
        updated, n1 = apply_regex(updated, r"(^\s*-\s*board:\s*)nice_nano//zmk\s*$", r"\1nice_nano_v2")
        total += n1
        updated, n2 = apply_regex(updated, r"(^\s*-\s*board:\s*)nice_nano@2(?:\.0\.0)?//zmk\s*$", r"\1nice_nano_v2")
        total += n2
        updated, n3 = apply_regex(updated, r"(^\s*-\s*board:\s*)nice_nano/nrf52840/zmk\s*$", r"\1nice_nano_v2")
        total += n3

    if total == 0 or updated == original:
        return FixResult(False, "Known error found, but no safe board replacement applied")

    write_text(build_yaml, updated)
    return FixResult(True, f"Updated board IDs based on revision '{revision or 'unknown'}'", replacements=total)


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-fix common ZMK build board mismatch errors")
    parser.add_argument("--logs-dir", required=True, help="Directory containing extracted GitHub Actions logs")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    args = parser.parse_args()

    repo_root = pathlib.Path(args.repo_root).resolve()
    logs_dir = pathlib.Path(args.logs_dir).resolve()

    logs_text = collect_logs(logs_dir)
    result = fix_build_yaml(repo_root, logs_text)

    print(f"changed={'true' if result.changed else 'false'}")
    print(f"reason={result.reason}")
    print(f"replacements={result.replacements}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
