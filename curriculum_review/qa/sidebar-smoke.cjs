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
  if(path==='/api/auth/me')data={id:'qa',name:'Synthetic reviewer',admin:process.env.QA_MEMBER!=='1',must_change:false};
  else if(path==='/api/workspaces')data=[w,{...w,id:'other',title:'Other course'}];
  else if(path==='/api/workspaces/other')data={...w,id:'other',title:'Other course'};
  else if(path.endsWith('/progress'))data={model:'ADDIE',framework_ready:true,events:path.includes('/other/')?[]:[{id:'step',text:'Assessment specialist examined the scoring rubric.',created:'2026-09-16T12:00:00Z'}],tasks:[{id:'task',action:'review',status:'incomplete',created:'2026-09-16T12:00:00Z',coverage:{scope:'full',examined:2,total:5,complete:false}}]};
  else if(path==='/api/auth/users')data=[];
  else if(path==='/api/workspaces/w')data=w;
  else if(path.endsWith('/prepare'))data={framework_id:'f'};
  else if((path==='/api/builder/workspaces/w'||path==='/api/builder/workspaces/other'))data={workspace_id:'w',mode:'review',model:'ADDIE',framework:{id:'f',version:'QA'},sources:[],tasks:[],proposals:[],entries:[{id:'entry',role:'assistant',text}],state:{}};
  await route.fulfill({json:data});
 });
 try{
  await page.goto(process.env.QA_URL||'http://localhost:5173');
  await page.getByRole('button',{name:'Formatting QA',exact:true}).click();
  const sidebar=page.getByRole('complementary',{name:'Workspace sidebar'});
  await sidebar.getByText('Assessment specialist examined the scoring rubric.').waitFor();
  await sidebar.getByText('Latest task: incomplete').waitFor();
  await sidebar.getByText('Workspace details',{exact:true}).click();
  await sidebar.getByText('Guidance QA (pinned)',{exact:false}).waitFor();
  await sidebar.getByRole('button',{name:'User tour',exact:true}).click();
  await page.getByRole('button',{name:'Next',exact:true}).focus();await page.keyboard.press('Enter');
  await page.getByRole('heading',{name:'Choose a workspace',exact:true}).waitFor();
  await page.getByLabel('Jump to a topic').selectOption({label:'4. Find your way around'});
  await page.getByText('The sidebar records analysis steps above', {exact:false}).waitFor();
  await page.keyboard.press('Escape');
  await page.waitForFunction(()=>document.activeElement?.textContent==='User tour');
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:900});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Page should not overflow');
  }
  await sidebar.getByRole('button',{name:'Other course',exact:true}).click();
  await sidebar.getByRole('heading',{name:'Other course',exact:true}).waitFor();
  assert.equal(await sidebar.getByText('Assessment specialist examined the scoring rubric.').count(),0);
  if(process.env.QA_MEMBER==='1'){assert.equal(await sidebar.getByText('Administration',{exact:true}).count(),0);}else{
  await sidebar.getByText('Administration',{exact:true}).click();
  assert.equal(await sidebar.getByRole('button',{name:'OpenAI settings',exact:true}).count(),1);
  }
  await sidebar.getByRole('button',{name:'Formatting QA',exact:true}).click();
  await sidebar.getByText('Assessment specialist examined the scoring rubric.').waitFor();
  assert.deepEqual(errors,[]);
  console.log('PASS: persisted progress, incomplete status, workspace switching, sidebar settings/details, tour keyboard focus and mobile layout. All API calls mocked.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
