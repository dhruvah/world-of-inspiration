#!/usr/bin/env bash
# Syntax-check the site script and regenerate links.txt. Run from the repo root.
set -e
sed -n '/<script>$/,/<\/script>/p' index.html | sed '1d;$d' > /tmp/site-script.js
node --check /tmp/site-script.js
node tools/mklinks.js links.txt /tmp/site-script.js
