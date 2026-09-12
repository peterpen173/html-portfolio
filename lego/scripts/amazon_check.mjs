// One-off snapshot: what Amazon US and UK show for four specific sets.
//
// The plain HTTP probe read 503 from every Amazon domain and concluded they
// could not be read. That was the wrong test: in a real browser, US and UK
// serve the page (DE and FR still refuse, and so does KSP).
//
// Search results mix the set itself with display cases and accessories, so a
// listing only counts when its title names the set number and LEGO, and does
// not look like an accessory. Shipping to Israel is not shown on a search
// page and is never inferred here.

import { chromium } from 'playwright';

const SETS = ['21357', '76344', '77984', '76354'];
const SITES = [
  ['Amazon US', 'https://www.amazon.com/s?k=lego+', '$', 'USD'],
  ['Amazon UK', 'https://www.amazon.co.uk/s?k=lego+', '£', 'GBP'],
];

const ACCESSORY = /display case|acrylic|compatible with|dust|stand for|lighting kit|light kit|sticker|storage|bag for/i;

const browser = await chromium.launch();
const ctx = await browser.newContext({ locale: 'en-US', viewport: { width: 1400, height: 1000 } });

for (const [siteName, base, sym, cur] of SITES) {
  console.log(`\n########## ${siteName}`);
  for (const set of SETS) {
    const page = await ctx.newPage();
    try {
      const resp = await page.goto(base + set, { waitUntil: 'domcontentloaded', timeout: 45000 });
      if (!resp || resp.status() !== 200) {
        console.log(`  ${set}: HTTP ${resp ? resp.status() : '?'} — refused`);
        await page.close();
        continue;
      }
      await page.waitForTimeout(3500);

      const items = await page.evaluate(() => {
        const out = [];
        for (const card of document.querySelectorAll('[data-component-type="s-search-result"]')) {
          const title = card.querySelector('h2')?.innerText?.trim() || '';
          const whole = card.querySelector('.a-price .a-price-whole')?.innerText?.replace(/[^\d]/g, '');
          const frac = card.querySelector('.a-price .a-price-fraction')?.innerText?.replace(/[^\d]/g, '');
          const offscreen = card.querySelector('.a-price .a-offscreen')?.textContent || '';
          out.push({ title, whole, frac, offscreen });
        }
        return out;
      });

      const hits = items
        .filter(i => i.title.includes(set) && /lego/i.test(i.title) && !ACCESSORY.test(i.title))
        .map(i => {
          const n = parseFloat((i.offscreen || '').replace(/[^\d.]/g, '')) ||
                    parseFloat(`${i.whole || ''}.${i.frac || '0'}`);
          return { title: i.title.slice(0, 72), price: n };
        })
        .filter(i => i.price > 0)
        .sort((a, b) => a.price - b.price);

      if (!hits.length) {
        console.log(`  ${set}: הדף נטען, לא נמצאה רשומה של הסט עצמו (${items.length} תוצאות בדף)`);
      } else {
        console.log(`  ${set}: ${hits.length} רשומות של הסט`);
        hits.slice(0, 3).forEach(h =>
          console.log(`      ${sym}${h.price.toFixed(2)}  ${h.title}`));
      }
    } catch (err) {
      console.log(`  ${set}: ${err.name}`);
    }
    await page.close();
  }
}

await browser.close();
