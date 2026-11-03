"""Resolve a Google Form link and print its form id and question entry ids."""
import sys, re, json, urllib.request
u = sys.argv[1]
r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30)
final, html = r.geturl(), r.read().decode("utf-8", "ignore")
print("FORMINFO final", final)
m = re.search(r"FB_PUBLIC_LOAD_DATA_ = (.*?);</script>", html, re.S)
if m:
    data = json.loads(m.group(1))
    print("FORMINFO title", data[1][8] if len(data[1]) > 8 else data[3])
    for q in data[1][1]:
        if q[4]:
            print("FORMINFO question", repr(q[1]), "entry", q[4][0][0], "type", q[3])
if len(sys.argv) > 2 and sys.argv[2]:
    import urllib.parse
    post = final.split("/viewform")[0] + "/formResponse"
    body = urllib.parse.urlencode({sys.argv[3]: sys.argv[2]}).encode()
    r = urllib.request.urlopen(urllib.request.Request(post, data=body, headers={"User-Agent": "Mozilla/5.0"}), timeout=30)
    print("FORMINFO test submit status", r.status)
