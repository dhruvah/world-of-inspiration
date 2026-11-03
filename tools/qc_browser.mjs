// Open links in a real browser (Chromium) and print status, final URL, title and the start of the page text.
import { chromium } from 'playwright';
import fs from 'fs';
const urls = fs.readFileSync(process.argv[2], 'utf8').split('\n').map(s => s.trim()).filter(Boolean);
const browser = await chromium.launch();
const ctx = await browser.newContext({ userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36', locale: 'en-US' });
const out = [];
const work = async (url) => {
  const page = await ctx.newPage();
  let status = 'error', title = '', text = '', final = url;
  try {
    const r = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(2500);
    status = r ? r.status() : 'none'; final = page.url(); title = await page.title();
    text = (await page.evaluate(() => (document.querySelector('h1')?.innerText || '') + ' || ' + document.body.innerText.slice(0, 220))).replace(/\s+/g, ' ');
  } catch (e) { text = String(e).slice(0, 120); }
  await page.close();
  out.push([url, status, final, title, text].join('\t'));
};
for (let i = 0; i < urls.length; i += 6) await Promise.all(urls.slice(i, i + 6).map(work));
await browser.close();
console.log(out.map(l => 'QCROW\t' + l).join('\n'));
