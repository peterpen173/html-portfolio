// Does a real browser reach the shops that refused a plain HTTP request?
//
// The earlier probe used urllib and got 403/503 from KSP and Amazon. Bot walls
// usually gate on JavaScript, cookies and TLS fingerprint rather than on the
// URL, so the same page often loads fine in an actual browser. This checks
// that, once per site, and reports what came back.
//
// If a site answers with a CAPTCHA or a human-verification challenge, that is
// recorded as blocked. Solving one is not attempted.

import { chromium } from 'playwright';

const TARGETS = [
  ['KSP',       'https://ksp.co.il/web/cat/?search=lego%2076354'],
  ['Amazon DE', 'https://www.amazon.de/s?k=lego+76354'],
  ['Amazon UK', 'https://www.amazon.co.uk/s?k=lego+76354'],
  ['Amazon FR', 'https://www.amazon.fr/s?k=lego+76354'],
  ['Amazon US', 'https://www.amazon.com/s?k=lego+76354'],
];

const CHALLENGE = /captcha|are you a robot|enter the characters|verify you are human|אימות|לא אנושי/i;
const PRICE = /(₪\s?[\d,]+(?:\.\d{2})?)|([\d.,]+\s?€)|(\$[\d,]+\.\d{2})|(£[\d,]+\.\d{2})/g;

const browser = await chromium.launch();
const ctx = await browser.newContext({
  locale: 'he-IL',
  viewport: { width: 1280, height: 900 },
});

for (const [name, url] of TARGETS) {
  const page = await ctx.newPage();
  let status = '?';
  try {
    const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    status = resp ? resp.status() : 'no response';
    await page.waitForTimeout(4000);
    const text = await page.evaluate(() => document.body.innerText.slice(0, 20000));
    const challenged = CHALLENGE.test(text);
    const prices = [...new Set((text.match(PRICE) || []).slice(0, 8))];
    console.log(
      `${name.padEnd(10)} HTTP ${String(status).padEnd(4)} ` +
      (challenged ? 'CHALLENGE (captcha / human check) — stopping here'
                  : `loaded, ${text.length}b, prices seen: ${prices.join('  ') || 'none'}`)
    );
    if (!challenged && prices.length) {
      const lines = text.split('\n').filter(l => /76354|helicarrier|נושאת/i.test(l)).slice(0, 4);
      lines.forEach(l => console.log(`             | ${l.trim().slice(0, 90)}`));
    }
  } catch (err) {
    console.log(`${name.padEnd(10)} ${err.name}: ${String(err.message).split('\n')[0].slice(0, 90)}`);
  }
  await page.close();
}

await browser.close();
