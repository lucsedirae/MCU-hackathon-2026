// UI-only fixtures: every API request is intercepted; no accounts or model calls.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||undefined});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const text=['## Review summary','','**Strong alignment** with *one gap*.','','1. Confirm outcomes','2. Review assessments','   - Check scoring','','| Area | Finding |','| --- | --- |','| Evidence | Review needed |','','```text','literal <tag> '+ 'x'.repeat(160),'```','','[Reference](https://example.org/guide)','','[unsafe](javascript:alert%281%29)','','![External illustration](https://example.invalid/image.png)','','<script>window.markdownExecuted=true</script>'].join('\n');
 const w={id:'w',title:'Formatting QA',owner_id:'qa',builder_mode:'review',documents:[],runs:[]};
 let remoteImages=0;
 await page.route('https://example.invalid/**',r=>{remoteImages++;r.abort();});
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;let data={};
  if(path==='/api/auth/me')data={id:'qa',name:'Synthetic reviewer',admin:false,must_change:false};
  else if(path==='/api/workspaces')data=[w];
  else if(path==='/api/workspaces/w')data=w;
  else if(path.endsWith('/prepare'))data={framework_id:'f'};
  else if(path==='/api/builder/workspaces/w')data={workspace_id:'w',mode:'review',model:'ADDIE',framework:{id:'f',version:'QA'},sources:[],tasks:[],proposals:[],entries:[{id:'entry',role:'assistant',text}],state:{}};
  await route.fulfill({json:data});
 });
 try{
  await page.goto(process.env.QA_URL||'http://localhost:5173');
  await page.getByRole('button',{name:'Formatting QA',exact:true}).click();
  const message=page.locator('.agent-markdown');
  await message.getByRole('heading',{name:'Review summary',level:2}).waitFor();
  assert.equal(await message.locator('strong').textContent(),'Strong alignment');
  assert.equal(await message.locator('ol > li').count(),2);
  assert.equal(await message.getByRole('table').count(),1);
  assert((await message.locator('pre code').textContent()).includes('literal <tag>'));
  assert.equal(await message.getByRole('link',{name:'Reference'}).getAttribute('href'),'https://example.org/guide');
  assert.equal(await message.getByRole('link',{name:'unsafe'}).count(),0);
  assert.equal(await message.locator('script,img').count(),0);
  assert.equal(await page.evaluate(()=>window.markdownExecuted),undefined);
  assert.equal(remoteImages,0);
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:900});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Page should not overflow');
  }
  assert.deepEqual(errors,[]);
  console.log('PASS: headings, emphasis, nested lists, tables, code, safe links, inert HTML/images, desktop/mobile. All API calls mocked.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
