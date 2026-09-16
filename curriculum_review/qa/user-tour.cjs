// UI-only checks: mock every API response; no accounts or provider calls are made.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || undefined });
  try {
    for (const admin of [true, false]) {
      const page = await browser.newPage({ viewport: { width: admin ? 1440 : 390, height: 900 } });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/api/**', async route => {
        const path = new URL(route.request().url()).pathname;
        let data = [];
        if (path === '/api/auth/me') data = { id: 'tour-test', name: 'Tour tester', admin, must_change: false };
        if (path === '/api/settings/llm') data = { model: '', has_api_key: false, system_prompt: 'Saved instructions', guardrails_prompt: '', review_rubric: '', evidence_rules: '', examples: '' };
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
      });
      await page.goto(process.env.QA_URL || 'http://localhost:5173');
      await page.getByRole('button', { name: 'User tour', exact: true }).click();
      const dialog = page.getByRole('dialog');
      await dialog.getByRole('heading', { name: 'Welcome to Cadence' }).waitFor();
      const topics = dialog.getByLabel('Jump to a topic');
      if (await topics.locator('option').count() !== (admin ? 14 : 12)) throw Error('Incorrect role-specific tour steps');
      await topics.selectOption('2');
      await dialog.getByText('Review and creation intake use short conversational replies', { exact: false }).waitFor();
      if (await dialog.evaluate(el => el.scrollWidth > el.clientWidth)) throw Error('Changed builder step overflows');
      await topics.selectOption('0');
      await dialog.getByRole('button', { name: 'Next', exact: true }).focus();
      await page.keyboard.press('Enter');
      await dialog.getByRole('heading', { name: 'Choose a workspace' }).waitFor();
      while (await dialog.getByRole('button', { name: 'Next', exact: true }).count()) {
        await dialog.getByRole('button', { name: 'Next', exact: true }).click();
      }
      await dialog.getByRole('button', { name: 'Back', exact: true }).click();
      await topics.selectOption('0');
      await page.keyboard.press('Escape');
      if (await dialog.count()) throw Error('Escape did not dismiss the tour');
      await page.waitForFunction(() => document.activeElement?.textContent === 'User tour');
      await page.getByRole('button', { name: 'User tour', exact: true }).click();
      await topics.selectOption(String(admin ? 13 : 11));
      if (await dialog.evaluate(el => el.scrollWidth > el.clientWidth)) throw Error('Tour overflows horizontally');
      await dialog.getByRole('button', { name: 'Finish tour', exact: true }).click();
      if (errors.length) throw Error(errors.join('\n'));
      await page.close();
    }
    console.log('PASS: all tour steps, administrator/member variants, back/jump/finish, Escape/focus restoration, mobile width, conversational builder step.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
