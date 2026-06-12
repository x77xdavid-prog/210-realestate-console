import { chromium } from "playwright";
import { spawn } from "node:child_process";

const host = "127.0.0.1";
const port = 8765;
const url = `http://${host}:${port}/`;

const server = spawn(
  "python",
  ["-m", "realestate_alert", "serve-web", "--config", "config.example.json", "--host", host, "--port", String(port)],
  {
    stdio: "ignore",
    windowsHide: true,
  },
);

await waitForServer(`${url}api/listings`);

const browser = await chromium.launch({
  channel: "chrome",
  headless: false,
});

const context = await browser.newContext({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 2,
  isMobile: true,
  hasTouch: true,
});

const page = await context.newPage();
await page.goto(url);
await page.waitForSelector("text=후보 매물 검토 대시보드");
await page.waitForSelector("text=양천구 목동 병원 가능 근린상가");

console.log(`Opened dashboard in Playwright: ${url}`);
console.log("Viewport: 390x844 mobile");
console.log("Close the browser window when you are done.");

try {
  await page.waitForTimeout(60 * 60 * 1000);
} finally {
  await browser.close();
  server.kill();
}

async function waitForServer(endpoint) {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(endpoint);
      if (response.ok) {
        return;
      }
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  }
  server.kill();
  throw new Error(`Server did not start: ${endpoint}`);
}
