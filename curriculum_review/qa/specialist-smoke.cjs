// Run against the disposable QA stack after seeding a mocked specialist review.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const base='http://localhost:15174';
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||undefined});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(base);
  await page.getByLabel('Email',{exact:true}).fill('builder-admin@example.test');
  await page.getByLabel('Password',{exact:true}).fill('Synthetic-password-2026');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByRole('button',{name:/^Chat QA /}).first().click();
  await page.getByText('Delegated to Subject-matter expert',{exact:false}).waitFor();
  await page.getByText('Approval is unavailable',{exact:false}).waitFor();
  const report=page.locator('.builder-conversation').getByText('Specialist findings · completed',{exact:true});
  await report.click();
  await page.locator('.builder-conversation').getByText(/indexed text passages examined/).waitFor();
  await page.locator('.builder-conversation .specialist-findings').getByText('sme · Synthetic planning · independent · completed',{exact:true}).first().click();
  await page.locator('.builder-conversation').getByRole('button',{name:/^Read evidence/}).first().click();
  await page.locator('.builder-conversation .specialist-findings blockquote').waitFor();
  assert.equal(await page.locator('.builder-conversation').getByRole('button',{name:'Approve report',exact:true}).count(),0);
  await page.screenshot({path:'/private/tmp/specialist-desktop-qa.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Mobile overflow');
  await page.screenshot({path:'/private/tmp/specialist-mobile-qa.png',fullPage:true});
  await page.getByRole('button',{name:'User tour',exact:true}).click();
  const options=await page.getByLabel('Jump to a topic').locator('option').allTextContents();
  await page.getByLabel('Jump to a topic').selectOption({label:options.find(x=>x.includes('Configure OpenAI'))});
  await page.getByText('Open ISD instructions',{exact:false}).waitFor();
  await page.keyboard.press('Escape');
  assert.deepEqual(errors,[]);
  console.log('PASS: chat delegation, specialist findings, source evidence, coverage, material approval guard, settings tour, desktop/mobile. All model results mocked.');
 }catch(e){await page.screenshot({path:'/private/tmp/specialist-error-qa.png',fullPage:true});throw e;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
