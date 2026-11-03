"""Print title, channel and availability for YouTube links (via YouTube's oEmbed)."""
import sys, json, urllib.request, urllib.parse
for u in [l.strip() for l in open(sys.argv[1]) if l.strip()]:
    q = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(u, safe="")
    try:
        d = json.load(urllib.request.urlopen(q, timeout=20))
        print(f"VIDROW\t{u}\tOK\t{d.get('title')}\t{d.get('author_name')}")
    except urllib.error.HTTPError as e:
        print(f"VIDROW\t{u}\tUNAVAILABLE ({e.code})\t\t")
