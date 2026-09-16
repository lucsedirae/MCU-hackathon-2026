// Run against the isolated QA stack, never the primary application database.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||undefined});
 const page=await browser.newPage({viewport:{width:1440,height:1050}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try {
  await page.goto(process.env.QA_URL||'http://localhost:15173');
  await page.getByLabel('Your name').fill('QA Administrator');
  await page.getByLabel('Email',{exact:true}).fill('qa@example.test');
  await page.getByLabel('Password',{exact:true}).fill('QA-only-password-2026');
  await page.getByRole('button',{name:'Create account and sign in'}).click();
  await page.getByText('Create a workspace',{exact:true}).click();
  await page.getByLabel('Curriculum title').fill('Clinical Skills Curriculum');
  await page.getByRole('button',{name:'Create workspace',exact:true}).click();
  await page.getByLabel('Word, PDF, Markdown, text, Moodle backup, or SCORM/xAPI ZIP (maximum 20 MB)').setInputFiles({name:'curriculum.md',mimeType:'text/markdown',buffer:Buffer.from('# Clinical Skills\n\nParticipants practice safe patient assessment.\n\n## Learning objectives\n\n- Identify key observations\n- Explain the assessment sequence\n\n| Skill | Evidence |\n| --- | --- |\n| Assessment | Observed practice |')});
  await page.getByRole('button',{name:'Upload and save'}).click();
  await page.locator('.document-content').waitFor();
  await page.getByLabel('General comment',{exact:true}).fill('Check the assessment criteria before release.');
  await page.getByRole('button',{name:'Add comment',exact:true}).click();
  await page.getByText('Check the assessment criteria before release.',{exact:true}).waitFor();
  await page.locator('[data-block-text]').filter({hasText:'Participants practice safe patient assessment.'}).evaluate(el=>{
    const range=document.createRange();range.setStart(el.firstChild,0);range.setEnd(el.firstChild,12);const s=window.getSelection();s.removeAllRanges();s.addRange(range);el.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));
  });
  await page.getByLabel('Comment on selected text').fill('Include novice learners.');
  await page.getByRole('button',{name:'Add comment',exact:true}).click();
  await page.getByText('Include novice learners.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'2. Review changes',exact:true}).click();
  await page.getByRole('button',{name:'Preview changes',exact:true}).click();
  await page.getByRole('button',{name:'Accept entire proposal',exact:true}).click();
  await page.getByText('Revision 1 · accepted · current',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Download',exact:true}).click();
  await page.getByLabel('Include unresolved comments').check();
  const downloaded=page.waitForEvent('download');
  await page.getByRole('button',{name:'Download Word',exact:true}).click();
  const download=await downloaded;await download.saveAs('/private/tmp/cr-export-qa.docx');
  await page.screenshot({path:'/private/tmp/cr-desktop-qa.png',fullPage:true});
  await page.reload();
  await page.getByRole('button',{name:'Clinical Skills Curriculum',exact:true}).click();
  await page.getByText('Revision 1 · accepted · current',{exact:true}).waitFor();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'/private/tmp/cr-mobile-qa.png',fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
  if(overflow)throw new Error('Mobile layout overflows horizontally');
  if(errors.length)throw new Error(errors.join('\n'));
  console.log('PASS: setup, workspace, upload, general and selected-text comments, compare, accept, Word download, reload persistence, mobile layout; no browser errors.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
