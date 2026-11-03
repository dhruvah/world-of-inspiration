"""For sites that block automated checks (Britannica, Cloudflare-protected pages):
ask the Internet Archive whether it has ever seen the page return 200. Prints url, verdict, latest capture."""
import sys, json, time, urllib.request, urllib.parse
urls = [l.strip() for l in open(sys.argv[1]) if l.strip()]
for u in urls:
    q = "https://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode({"url": u, "output": "json", "filter": "statuscode:200", "limit": "-1", "fl": "timestamp"})
    verdict, ts = "no 200 capture", ""
    for attempt in range(3):
        try:
            rows = json.load(urllib.request.urlopen(urllib.request.Request(q, headers={"User-Agent": "world-of-inspiration-link-qc/1.0"}), timeout=40))
            if len(rows) > 1: verdict, ts = "seen OK", rows[-1][0]
            break
        except Exception as e:
            verdict = "lookup failed"; time.sleep(4)
    print(f"WBROW\t{u}\t{verdict}\t{ts}", flush=True)
    time.sleep(1.2)
