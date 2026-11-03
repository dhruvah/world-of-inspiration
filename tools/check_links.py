"""Check every external link listed in links.txt (generated from the site data).

404/410 -> failure (job fails)
3xx redirect -> warning
403/406/429, timeouts, other errors -> manual review (a browser may still work)
"""
import re, sys, os, urllib.request, urllib.error, socket, concurrent.futures as cf

SKIP = ("fonts.googleapis.com", "fonts.gstatic.com", "cdn.jsdelivr.net", "openlibrary.org/search")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None

opener = urllib.request.build_opener(NoRedirect)

def check(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    try:
        with opener.open(req, timeout=25) as r:
            return url, r.status, ""
    except urllib.error.HTTPError as e:
        return url, e.code, e.headers.get("Location", "") or ""
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
        return url, None, str(getattr(e, "reason", e))[:120]

WIKI_HOSTS = {"en.wikipedia.org": "https://en.wikipedia.org/w/api.php",
              "commons.wikimedia.org": "https://commons.wikimedia.org/w/api.php"}

def check_wiki(urls):
    """Check Wikipedia/Commons pages through the MediaWiki API, 50 titles per request.
    One-by-one page fetches get rate-limited (429), which hides real 404s."""
    import json, time, urllib.parse
    results = []
    by_host = {}
    for u in urls:
        host = urllib.parse.urlsplit(u).netloc
        title = urllib.parse.unquote(u.split("/wiki/", 1)[1].split("#")[0]).replace("_", " ")
        by_host.setdefault(host, []).append((u, title))
    for host, items in by_host.items():
        api = WIKI_HOSTS[host]
        for i in range(0, len(items), 50):
            chunk = items[i:i + 50]
            q = urllib.parse.urlencode({"action": "query", "format": "json", "formatversion": "2",
                                        "titles": "|".join(t for _, t in chunk)})
            data = None
            for attempt in range(4):
                try:
                    req = urllib.request.Request(api + "?" + q, headers={"User-Agent": "world-of-inspiration-link-check/1.0 (GitHub Actions)"})
                    with urllib.request.urlopen(req, timeout=30) as r:
                        data = json.load(r)
                    break
                except Exception as e:
                    time.sleep(5 * (attempt + 1))
            if data is None:
                results += [(u, None, "wiki API unreachable") for u, _ in chunk]
                continue
            q2 = data.get("query", {})
            norm = {n["from"]: n["to"] for n in q2.get("normalized", [])}
            pages = {pg["title"]: pg for pg in q2.get("pages", [])}
            for u, t in chunk:
                pg = pages.get(norm.get(t, t))
                if pg is None or pg.get("missing") or pg.get("invalid"):
                    results.append((u, 404, "page does not exist"))
                else:
                    results.append((u, 200, ""))
            time.sleep(1)
    return results

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "links.txt"
    text = open(src, encoding="utf-8").read()
    if src.endswith(".txt"):
        urls = sorted({l.strip() for l in text.splitlines() if l.strip()})
    else:
        urls = sorted({u.rstrip(".,;") for u in re.findall(r"https?://[^\s\"'`<>\\]+", text)})
    urls = [u for u in urls if not any(s in u for s in SKIP) and "${" not in u]
    fail, warn, review = [], [], []
    wiki = [u for u in urls if any(f"//{h}/wiki/" in u for h in WIKI_HOSTS)]
    other = [u for u in urls if u not in set(wiki)]
    with cf.ThreadPoolExecutor(16) as ex:
        checked = list(ex.map(check, other))
    for url, code, note in checked + check_wiki(wiki):
        if True:
            if code in (404, 410):
                fail.append((url, code, note))
            elif code and 300 <= code < 400:
                warn.append((url, code, note))
            elif code is None or code >= 400:
                review.append((url, code or "error", note))
    out = [f"## Link check: {len(urls)} links", f"- Failures (404/410): **{len(fail)}**",
           f"- Redirects (warning): {len(warn)}", f"- Manual review (403/406/429/timeouts): {len(review)}"]
    for title, rows in (("Failures", fail), ("Redirects", warn), ("Manual review", review)):
        if rows:
            out += ["", f"### {title}", "| Code | URL | Note |", "|---|---|---|"]
            out += [f"| {c} | {u} | {n} |" for u, c, n in rows]
    report = "\n".join(out)
    print(report)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(report + "\n")
    sys.exit(1 if fail else 0)

if __name__ == "__main__":
    main()
