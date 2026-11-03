"""Deeper link QC: open every link like a browser would and record where it really lands.

Writes a TSV: url, status, final_url, page_title, flags.
Flags catch links that 'work' but are wrong: soft 404s, redirects to a home page,
redirects to another site, Wikipedia disambiguation pages and redirects.
"""
import sys, re, json, time, html, urllib.request, urllib.parse, urllib.error, concurrent.futures as cf

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
SOFT404 = re.compile(r"\b(404|not found|page not found|no longer available|does not exist|error|oops|cannot be found|unavailable)\b", re.I)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*", "Accept-Language": "en"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read(300000).decode("utf-8", "ignore")
            m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
            title = html.unescape(re.sub(r"\s+", " ", m.group(1)).strip()) if m else ""
            return url, r.status, r.geturl(), title
    except urllib.error.HTTPError as e:
        return url, e.code, url, ""
    except Exception as e:
        return url, "error", url, str(e)[:100]

def flags(url, status, final, title):
    f = []
    if status != 200: f.append(f"status {status}")
    a, b = urllib.parse.urlsplit(url), urllib.parse.urlsplit(final)
    if a.netloc.replace("www.", "") != b.netloc.replace("www.", ""): f.append("other site")
    if a.path.strip("/") and not b.path.strip("/"): f.append("sent to home page")
    if title and SOFT404.search(title): f.append("title looks like an error")
    return f

def wiki(urls):
    out = []
    by = {}
    for u in urls:
        host = urllib.parse.urlsplit(u).netloc
        t = urllib.parse.unquote(u.split("/wiki/", 1)[1].split("#")[0]).replace("_", " ")
        by.setdefault(host, []).append((u, t))
    for host, items in by.items():
        for i in range(0, len(items), 50):
            chunk = items[i:i + 50]
            q = urllib.parse.urlencode({"action": "query", "format": "json", "formatversion": "2", "redirects": "1",
                                        "prop": "pageprops|description", "ppprop": "disambiguation", "titles": "|".join(t for _, t in chunk)})
            req = urllib.request.Request(f"https://{host}/w/api.php?{q}", headers={"User-Agent": "world-of-inspiration-link-qc/1.0"})
            data = json.load(urllib.request.urlopen(req, timeout=30))["query"]
            norm = {n["from"]: n["to"] for n in data.get("normalized", [])}
            red = {n["from"]: n["to"] for n in data.get("redirects", [])}
            pages = {p["title"]: p for p in data.get("pages", [])}
            for u, t in chunk:
                t1 = norm.get(t, t); t2 = red.get(t1, t1); p = pages.get(t2, {})
                f = []
                if p.get("missing") or not p: f.append("status 404")
                if t2 != t1: f.append(f"redirects to '{t2}'")
                if "pageprops" in p and "disambiguation" in p["pageprops"]: f.append("disambiguation page")
                out.append((u, 404 if "status 404" in f else 200, u, t2 + " — " + p.get("description", ""), f))
            time.sleep(1)
    return out

def main():
    urls = sorted({l.strip() for l in open(sys.argv[1], encoding="utf-8") if l.strip().startswith("http")})
    urls = [u for u in urls if "fonts.g" not in u and "cdn.jsdelivr" not in u and "openlibrary.org/search" not in u]
    w = [u for u in urls if "wikipedia.org/wiki/" in u or "commons.wikimedia.org/wiki/" in u]
    o = [u for u in urls if u not in set(w)]
    rows = [(u, s, fin, t, flags(u, s, fin, t)) for u, s, fin, t in cf.ThreadPoolExecutor(12).map(fetch, o)] + wiki(w)
    with open(sys.argv[2], "w", encoding="utf-8") as fh:
        fh.write("url\tstatus\tfinal_url\ttitle\tflags\n")
        for u, s, fin, t, f in rows:
            fh.write("\t".join(map(str, (u, s, fin, t.replace("\t", " "), "; ".join(f)))) + "\n")
    bad = [r for r in rows if r[4]]
    print(f"{len(rows)} links, {len(bad)} flagged")

if __name__ == "__main__":
    main()
