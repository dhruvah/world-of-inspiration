# Notes for automated maintenance (World of Inspiration)

Single-file site: `index.html` (data + code). GitHub Pages serves `main`. Photos: `photo-catalog.js` (maintained by Harsh; do not add photos of real people yourself).

## Adding a person or organization
Insert a `P(...)` call before the comment `/* merge Spiritual into the first category */`:

`P(slug,name,years,era,field,where,icon,color,beyond,story,facts,circle,qKey,links,books)`
- era: "past" | "modern" | "org"; field: one of FIELDS (SAINTS, "History & kingdoms", "Science", "Engineering & tech", BIZ, "Leaders who gave back", "Arts & music", "Sports", "Seva", ORG).
- icon: an existing key of `icons`; color: sun|mint|sky|blush|coral|lilac|tomato; qKey: an existing key of `Q`.
- story: 4–6 plain sentences, own words, facts only, no hype. Religious figures "as their tradition describes". Living politicians: strictly factual, note supporters and critics.
- links: `[source, title, url, why, type]`; helpers `W("Wikipedia_Title")`, `NOB(path,t,w)`, `GUT(n,t,w)`, `MT(name,t)`. Only high-quality sources (official sites, Nobel, Britannica, universities, museums, Yad Vashem, reputable long-form). Every URL must come from a search result or be verified; never guess.
- Also add a globe location: append to `Object.assign(LOC,{...})` style blocks: `slug:[lat,lon,year,"label?"]`.
- Optional "who lit whom": `LINEAGE.push({t:"",steps:["~Mentor without page","slug"],notes:["one line"]})`.

## Videos
Add to `VIDEOS` with `(VIDEOS["slug"]=VIDEOS["slug"]||[]).push([channel+" · YouTube", title, url, why, "Video"])`. Only official/original channels (TED, Nobel Prize, universities, broadcasters, the person's own foundation). Verify channel and title with the "Video info" workflow (`tools/video_urls.txt`).

## Checks before committing
- `bash tools/check.sh` (syntax check + regenerate links.txt)
- Bump the cache version in `sw.js` (`insp-vN` → N+1).
- Wikipedia titles must resolve to the right person (not a disambiguation page). Run the "Link QC (deep)" workflow after pushing a branch if many links changed.
