// Drive /world end-to-end in headless Chromium: idle hero → prompt →
// live HUD with ticking metrics → sentinel thoughts. Fails on console errors.
import { chromium } from 'playwright'

const SCRATCH = '/tmp/claude-0/-home-user-overhaul-v2/ad3efaf1-c2cd-52a9-8984-bf1d472b9519/scratchpad'
const errors = []

const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })
const page = await browser.newPage({ viewport: { width: 1440, height: 860 } })
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(m.text())
})
page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))

await page.goto('http://localhost:5173/world', { waitUntil: 'networkidle' })
await page.waitForSelector('.wc-hero h1', { timeout: 20000 })
console.log('IDLE OK:', await page.textContent('.wc-hero h1'))
await page.screenshot({ path: `${SCRATCH}/world-idle.png` })

await page.fill('.wc-prompt input', 'what if it rains during rush hour in Noida?')
await page.click('.wc-prompt button')
await page.waitForSelector('.wc-topbar', { timeout: 90000 })
console.log('LIVE OK: region =', (await page.textContent('.wc-region')).trim())
console.log('WEATHER CHIP:', (await page.textContent('.wc-topbar .wc-chip:nth-child(2)')).trim())

// metrics should tick within a few seconds
await page.waitForFunction(() => {
  const el = document.querySelector('.wc-metrics b')
  return el && el.textContent !== '—' && Number(el.textContent) > 0
}, { timeout: 20000 })
const metrics = await page.$$eval('.wc-metrics > div', (els) =>
  els.map((e) => e.textContent.trim()))
console.log('METRICS:', metrics.join(' | '))

// clock ticking
const clock1 = await page.textContent('.wc-clock')
await page.waitForTimeout(3000)
const clock2 = await page.textContent('.wc-clock')
console.log('CLOCK:', clock1, '→', clock2, clock1 !== clock2 ? '(ticking)' : '(static?)')

// sentinel thoughts arrive after the first cognitive event (~30s real at 1×)
await page.waitForSelector('.wc-thought', { timeout: 60000 })
console.log('THOUGHTS OK:', (await page.textContent('.wc-thought')).trim())
await page.click('.wc-thought')
await page.waitForSelector('.wc-panel h3', { timeout: 5000 })
console.log('PANEL OK:', (await page.textContent('.wc-panel h3')).trim())

await page.screenshot({ path: `${SCRATCH}/world-live.png` })

// speed control roundtrip
await page.click('.wc-speeds button:last-child')
await page.waitForTimeout(1000)

const fatal = errors.filter((e) => !/VITE_MAPBOX|googletagmanager|fonts.googleapis|ERR_TUNNEL_CONNECTION_FAILED|ERR_CONNECTION_RESET|mapbox/i.test(e))
console.log('CONSOLE ERRORS:', fatal.length, fatal.slice(0, 5))
await browser.close()
if (fatal.length) {
  console.log('VERIFY FAILED')
  process.exit(1)
}
console.log('VERIFY PASSED')
