#!/usr/bin/env python3
"""Add safely licensed Wikimedia page images for newly added story cards.

The bot deliberately uses exact Wikipedia titles (plus redirects) rather than
fuzzy search. A missing or ambiguous result is reported for human review.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
CATALOG = ROOT / "photo-catalog.js"
SERVICE_WORKER = ROOT / "sw.js"
LINKS = ROOT / "links.txt"
OVERRIDES = ROOT / "tools" / "photo_bot_overrides.json"
IGNORE = ROOT / "tools" / "photo_bot_ignore.txt"
USER_AGENT = (
    "WorldOfInspirationPhotoBot/1.0 "
    "(https://github.com/dhruvah/world-of-inspiration)"
)
CARD_RE = re.compile(r'(?m)^P\(\s*"([^"]+)"\s*,\s*"([^"]+)"')
CATALOG_ID_RE = re.compile(r'"([^"]+)"\s*:\s*\[\s*\{\s*"src"\s*:')
CATALOG_ASSIGN_RE = re.compile(r'window\.PHOTO_CATALOG\["([^"]+)"\]')
BUILTIN_PHOTO_RE = re.compile(
    r'(?m)^\s*(?:"([^"]+)"|([A-Za-z][\w-]*))\s*:\s*\['
)


def api(host: str, params: dict[str, str | int], retries: int = 4) -> dict:
    params = {**params, "format": "json", "maxlag": 5}
    url = f"https://{host}/w/api.php?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def cards(text: str) -> dict[str, str]:
    return dict(CARD_RE.findall(text))


def git_file(revision: str, path: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f"{revision}:{path}"], cwd=ROOT, text=True
        )
    except subprocess.CalledProcessError:
        return ""


def existing_photo_ids() -> set[str]:
    catalog = CATALOG.read_text(encoding="utf-8")
    result = set(CATALOG_ID_RE.findall(catalog))
    result.update(CATALOG_ASSIGN_RE.findall(catalog))
    index = INDEX.read_text(encoding="utf-8")
    marker = "const PHOTOS=Object.assign"
    if marker in index:
        photo_block = index.split(marker, 1)[1].split("});", 1)[0]
        result.update(a or b for a, b in BUILTIN_PHOTO_RE.findall(photo_block))
    return result


def load_ignore() -> set[str]:
    if not IGNORE.exists():
        return set()
    return {
        line.strip()
        for line in IGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def load_overrides() -> dict[str, str]:
    if not OVERRIDES.exists():
        return {}
    return json.loads(OVERRIDES.read_text(encoding="utf-8"))


def follow_aliases(title: str, query: dict) -> str:
    aliases = {
        item["from"]: item["to"]
        for key in ("normalized", "redirects")
        for item in query.get(key, [])
    }
    seen: set[str] = set()
    while title in aliases and title not in seen:
        seen.add(title)
        title = aliases[title]
    return title


def wikipedia_page_image(title: str) -> tuple[str | None, str]:
    data = api(
        "en.wikipedia.org",
        {
            "action": "query",
            "redirects": 1,
            "prop": "pageimages",
            "piprop": "name",
            "titles": title,
        },
    )
    query = data.get("query", {})
    resolved = follow_aliases(title, query)
    pages = {page.get("title"): page for page in query.get("pages", {}).values()}
    page = pages.get(resolved, {})
    if page.get("missing") is not None or not page:
        return None, f'no exact English Wikipedia page for "{title}"'
    if not page.get("pageimage"):
        return None, f'Wikipedia page "{resolved}" has no lead image'
    return page["pageimage"], resolved


def clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def accepted_license(name: str) -> bool:
    return bool(
        name == "CC0"
        or name == "GODL-India"
        or name.startswith("Public domain")
        or re.match(r"^CC BY(?:-SA)?(?:\s|$)", name)
    )


def commons_record(filename: str, display_name: str) -> tuple[dict | None, str]:
    requested = f"File:{filename}"
    data = api(
        "commons.wikimedia.org",
        {
            "action": "query",
            "redirects": 1,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "iiurlwidth": 1600,
            "titles": requested,
        },
    )
    query = data.get("query", {})
    resolved = follow_aliases(requested, query)
    pages = {page.get("title"): page for page in query.get("pages", {}).values()}
    page = pages.get(resolved, {})
    if not page.get("imageinfo"):
        return None, "the Wikipedia lead image is not hosted on Wikimedia Commons"

    info = page["imageinfo"][0]
    metadata = info.get("extmetadata", {})
    license_name = metadata.get("LicenseShortName", {}).get("value", "").strip()
    if not accepted_license(license_name):
        return None, f'license "{license_name or "unknown"}" is not allowlisted'

    creator = clean_html(metadata.get("Artist", {}).get("value", ""))
    record = {
        "src": (info.get("thumburl") or info["url"]).split("?", 1)[0],
        "alt": display_name,
        "caption": display_name,
        "creator": creator or "See the Wikimedia Commons source",
        "license": license_name,
        "source": info["descriptionurl"],
    }
    license_url = metadata.get("LicenseUrl", {}).get("value", "").strip()
    if license_url:
        record["licenseUrl"] = license_url.replace("http://", "https://", 1)
    return record, ""


def append_records(records: dict[str, list[dict]]) -> None:
    encoded = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    block = (
        "\n/* Added by the Wikimedia photo bot; review the generated PR before merging. */\n"
        f"Object.assign(window.PHOTO_CATALOG,{encoded});\n"
    )
    with CATALOG.open("a", encoding="utf-8") as output:
        output.write(block)


def bump_cache_version() -> None:
    text = SERVICE_WORKER.read_text(encoding="utf-8")
    match = re.search(r"insp-v(\d+)", text)
    if not match:
        raise RuntimeError("could not find the service-worker cache version")
    version = int(match.group(1)) + 1
    updated = text[: match.start()] + f"insp-v{version}" + text[match.end() :]
    SERVICE_WORKER.write_text(updated, encoding="utf-8")


def update_link_inventory(records: dict[str, list[dict]]) -> None:
    urls = set(LINKS.read_text(encoding="utf-8").splitlines()) if LINKS.exists() else set()
    for photos in records.values():
        for photo in photos:
            urls.update(
                value
                for key in ("src", "source", "licenseUrl")
                if (value := photo.get(key))
            )
    LINKS.write_text("\n".join(sorted(urls)) + "\n", encoding="utf-8")


def write_report(path: Path, added: list[tuple[str, str, dict]], skipped: list[tuple[str, str, str]]) -> None:
    lines = ["# Wikimedia photo bot", ""]
    if added:
        lines += [f"Added **{len(added)}** safely licensed image(s):", ""]
        for slug, name, record in added:
            lines.append(
                f'- `{slug}` — **{name}** — {record["license"]} — '
                f'[source]({record["source"]})'
            )
    else:
        lines.append("No images were added.")
    if skipped:
        lines += ["", f"Skipped **{len(skipped)}** card(s) for human review:", ""]
        for slug, name, reason in skipped:
            lines.append(f"- `{slug}` — **{name}**: {reason}")
    lines += [
        "",
        "The bot never performs fuzzy identity matching and never accepts non-allowlisted licenses.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", help="Only inspect cards added since this Git revision")
    parser.add_argument("--all", action="store_true", help="Inspect every currently unpictured card")
    parser.add_argument("--dry-run", action="store_true", help="Do not edit photo-catalog.js")
    parser.add_argument("--report", default="photo-bot-report.md")
    args = parser.parse_args()
    if not args.all and not args.base:
        parser.error("provide --base REVISION or --all")

    current = cards(INDEX.read_text(encoding="utf-8"))
    if args.all:
        candidates = current
    else:
        previous = cards(git_file(args.base, "index.html"))
        candidates = {slug: name for slug, name in current.items() if slug not in previous}

    existing = existing_photo_ids()
    ignored = load_ignore()
    overrides = load_overrides()
    candidates = {
        slug: name
        for slug, name in candidates.items()
        if slug not in existing and slug not in ignored
    }

    added: list[tuple[str, str, dict]] = []
    skipped: list[tuple[str, str, str]] = []
    for slug, name in sorted(candidates.items()):
        title = overrides.get(slug, name)
        try:
            filename, reason = wikipedia_page_image(title)
            if not filename:
                skipped.append((slug, name, reason))
                continue
            record, reason = commons_record(filename, name)
            if not record:
                skipped.append((slug, name, reason))
                continue
            added.append((slug, name, record))
        except Exception as error:  # Keep one API problem from losing the full report.
            skipped.append((slug, name, f"lookup failed: {error}"))

    if added and not args.dry_run:
        records = {slug: [record] for slug, _, record in added}
        append_records(records)
        update_link_inventory(records)
        bump_cache_version()
    write_report(Path(args.report), added, skipped)
    print(f"Added {len(added)}; skipped {len(skipped)}; candidates {len(candidates)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
