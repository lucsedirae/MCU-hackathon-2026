"""Synthetic SQLite fixtures and mocked provider calls; no application data or API calls."""
import io
import json
import unittest
import zipfile
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base
from app import auth, builder
from app.models import User, BuilderWorkspace, BuilderProposal, BuilderTask, Thread, FrameworkVersion


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as s:
            for uid, admin in [('owner',False),('peer',False),('admin',True)]:
                s.add(User(id=uid,email=uid+'@synthetic.invalid',name=uid,password='unused',admin=admin,must_change=False,active=True))
            s.commit()
        self.uid = 'owner'
        def session():
            with Session(self.engine) as s: yield s
        def current():
            with Session(self.engine) as s: return s.get(User,self.uid)
        def admin():
            from fastapi import HTTPException
            u=current()
            if not u.admin: raise HTTPException(403,'Administrator required')
            return u
        app.dependency_overrides[auth.db]=session
        app.dependency_overrides[auth.current]=current
        app.dependency_overrides[auth.administrator]=admin
        self.patch=patch.object(builder,'engine',self.engine); self.patch.start()
        self.settings=patch.object(builder,'read_settings',return_value={'instructional_model':'ADDIE'});self.settings.start()
        self.client=TestClient(app)
        self.wid=self.client.post('/api/builder/workspaces',json={'title':'Synthetic review'}).json()['id']

    def tearDown(self):
        self.client.close(); self.patch.stop();self.settings.stop();app.dependency_overrides.clear();self.engine.dispose()

    def detail(self): return self.client.get('/api/builder/workspaces/'+self.wid).json()

    def ready(self):
        self.uid='admin'
        r=self.client.post('/api/frameworks',data={'version':'test-v1','model':'ADDIE'},files={'file':('test.md',b'# Analysis\n\nRequire performance evidence.\n\n# Review\n\nCheck objectives and assessment alignment.')})
        self.assertEqual(r.status_code,200,r.text); fid=r.json()['id']
        self.assertEqual(self.client.post('/api/frameworks/'+fid+'/publish').status_code,200)
        self.uid='owner'
        self.assertEqual(self.client.post(f'/api/builder/workspaces/{self.wid}/framework',json={'framework_id':fid}).status_code,200)
        r=self.client.post(f'/api/builder/workspaces/{self.wid}/sources',files={'file':('lesson.md',b'# Lesson\n\nLearners practice planning.\n\nAssessment is unspecified.')})
        self.assertEqual(r.status_code,200,r.text)
        return fid

    def test_progress_is_persisted_activity_without_source_text(self):
        self.ready()
        from app.models import BuilderEntry
        with Session(self.engine) as session:
            session.add(BuilderEntry(workspace_id=self.wid, role='system', text='Assessment review delegated.'))
            session.add(BuilderEntry(workspace_id=self.wid, role='user', text='Private intake message'))
            session.add(BuilderTask(workspace_id=self.wid, author_id='owner', action='review', status='incomplete',
                snapshot={'secret': 'not progress'}, result={'coverage': {'scope': 'full', 'examined': 2, 'total': 5, 'complete': False}, 'raw_reply': 'not progress'}))
            session.commit()
        self.uid = 'peer'
        response = self.client.get(f'/api/builder/workspaces/{self.wid}/progress')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['framework_ready'])
        self.assertIn('Assessment review delegated.', [e['text'] for e in data['events']])
        self.assertEqual(data['tasks'][0]['status'], 'incomplete')
        self.assertFalse(data['tasks'][0]['coverage']['complete'])
        self.assertNotIn('Private intake message', response.text)
        self.assertNotIn('not progress', response.text)
        self.assertNotIn('units', response.text)

    def outputs(self, passed=True):
        source=self.detail()['sources'][0]; unit=source['units'][1]
        draft={'reply':'Review prepared. Verify the proposed assessment gap.', 'ready_for_review':True,
            'report_markdown':'# Review\n\nStrength: planning practice.\n\nGap: assessment criteria missing.\n\nEvidence confidence: Moderate. Needs review.',
            'assessments':[{'revision_id':source['revision_id'],'confidence':'Moderate','rationale':'Assessment criteria missing.','gaps':['Assessment standard'],'peer_review':'Consult an assessment peer.'}],
            'proposals':[{'title':'Clarify assessment standard','rationale':'The source does not specify assessment criteria.','impact':'Assessment design needs owner verification.','material':True}],
            'comments':[{'revision_id':source['revision_id'],'block_id':unit['id'],'quote':unit['text'][:160],'text':'Connect this practice to observable assessment criteria.'}]}
        quality={'passed':passed,'findings':[] if passed else ['Missing coverage'], 'confidence':'Moderate','rationale':'Assessment standard is not supplied.','peer_review':'Consult an assessment peer.'}
        return [{'text':json.dumps(draft),'model':'mock-model'},{'text':json.dumps(quality),'model':'mock-model'}]

    def responder(self, outputs=None):
        outputs = outputs or self.outputs()
        draft = json.loads(outputs[0]['text']); quality = json.loads(outputs[1]['text'])
        async def respond(prompt, **kwargs):
            request=json.loads(prompt); stage=request['stage']
            if stage=='plan':
                source=self.detail()['sources'][0]; rid=source['revision_id']
                body={'reply':draft['reply'], 'ready_for_review':draft['ready_for_review'], 'subjects_confirmed':True,
                    'revision_ids':[rid], 'assignments':[{'role':role,'subject':'Planning','objective':'Check course integrity','revision_ids':[rid]} for role in ('sme','technical')],
                    'omitted_roles':{'assessment':'No separate assessment supplied','exercise':'No exercise supplied'}}
            elif stage in ('independent','challenge','verification'):
                body={'summary':'Reviewed evidence in assigned scope.', 'examined':request['required_passage_ids'],
                    'confidence':'Moderate','rationale':'Synthetic evidence only.', 'findings':[]}
                if stage=='independent' and request['assignment']['role']=='sme':
                    body['findings']=[{'kind':'gap','title':p['title'],'explanation':p['rationale'],'recommendation':p['impact'],
                        'material':p['material'],'citations':[request['required_passage_ids'][0]]} for p in draft.get('proposals',[])]
            elif stage=='synthesis': body=draft
            elif stage=='guidance':
                body={'tldr':'Planning practice is present; scoring criteria need clarification.',
                    'model_lens':'The configured guidance requires objectives and assessment alignment.',
                    'gaps':['Assessment standard'], 'questions':[{'question':'What must learners demonstrate to pass?', 'why':'This determines the assessment standard.'},
                        {'question':'Who verifies the scoring criteria?', 'why':'This establishes the responsible reviewer.'}],
                    'next_step':'Clarify the assessment standard.',
                    'framework_citations':[p['id'] for p in request['evidence'] if p['collection']=='framework'][:1]}

            else: body=quality
            return {'text':json.dumps(body),'model':'mock-model'}
        return respond

    def run_review(self, outputs=None):
        with patch.object(builder,'request_completion',side_effect=self.responder(outputs)) as call:
            r=self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review uploaded evidence','action':'review'})
            self.assertEqual(r.status_code,200,r.text)
            self.assertGreaterEqual(call.await_count,5)
        return self.detail()['tasks'][0]

    def test_missing_guidance_allows_notes_but_blocks_ai(self):
        with patch.object(builder,'request_completion',AsyncMock()) as call:
            r=self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Audience is experienced officers','action':'record'})
            self.assertEqual(r.status_code,200)
            r=self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review now','action':'review'})
            self.assertEqual(r.status_code,409);call.assert_not_called()
        self.assertEqual(len(self.detail()['entries']),1)
        self.assertEqual(self.detail()['state'],{})

    def test_framework_publication_pinning_and_permissions(self):
        r=self.client.post('/api/frameworks',data={'version':'x','model':'ADDIE'},files={'file':('x.txt',b'Guidance')})
        self.assertEqual(r.status_code,403)
        fid=self.ready()
        self.assertEqual(self.client.post(f'/api/builder/workspaces/{self.wid}/framework',json={'framework_id':fid}).status_code,409)
        found=self.client.get('/api/frameworks/'+fid+'/search?q=assessment').json()
        self.assertTrue(found['passages']); self.assertEqual(found['framework']['id'],fid)
        self.uid='peer'
        self.assertEqual(self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'No','action':'record'}).status_code,403)
        self.assertEqual(self.client.post(f'/api/builder/workspaces/{self.wid}/sources',files={'file':('x.txt',b'X')}).status_code,403)

    def test_review_comments_verification_and_export(self):
        self.ready();task=self.run_review()
        self.assertEqual(task['status'],'completed',task)
        self.assertEqual(self.detail()['state'],{})
        p=self.detail()['proposals'][0]
        with Session(self.engine) as s:
            thread=s.scalar(select(Thread));self.assertTrue(thread.quote);self.assertFalse(thread.resolved)
        self.uid='peer'
        payload={'decision':'verify','reason':'I verified the missing standard.','expected_state_version':0}
        self.assertEqual(self.client.post(f"/api/builder/proposals/{p['id']}/verify",json=payload).status_code,403)
        self.uid='owner'
        self.assertEqual(self.client.post(f"/api/builder/proposals/{p['id']}/verify",json=payload).status_code,200)
        self.assertEqual(self.detail()['state_version'],1)
        self.assertEqual(self.client.post(f"/api/builder/proposals/{p['id']}/verify",json=payload).status_code,409)
        r=self.client.get(f'/api/builder/workspaces/{self.wid}/export');self.assertEqual(r.status_code,200,r.text)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            self.assertIn(p['title'],z.read('verified-history.md').decode())
            self.assertIn('Review uploaded evidence',z.read('conversation.md').decode())
            self.assertTrue(any(n.endswith('.docx') for n in z.namelist()))

    def test_decline_does_not_change_state_or_history(self):
        self.ready();self.run_review();p=self.detail()['proposals'][0]
        r=self.client.post(f"/api/builder/proposals/{p['id']}/verify",json={'decision':'decline','reason':'Existing assessment supplied separately.','expected_state_version':0})
        self.assertEqual(r.status_code,200);self.assertEqual(self.detail()['state'],{})
        with zipfile.ZipFile(io.BytesIO(self.client.get(f'/api/builder/workspaces/{self.wid}/export').content)) as z:
            self.assertNotIn(p['title'],z.read('verified-history.md').decode())

    def test_failed_quality_check_does_not_publish_report(self):
        self.ready();t=self.run_review(self.outputs(False));self.assertEqual(t['status'],'needs_revision')
        self.assertNotIn('report_id',t['result'])
        with Session(self.engine) as s:self.assertIsNone(s.scalar(select(Thread)))

    def test_malformed_result_applies_no_partial_changes(self):
        self.ready()
        with patch.object(builder,'request_completion',AsyncMock(return_value={'text':'not json','model':'mock'})):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review','action':'review'})
        self.assertEqual(self.detail()['tasks'][0]['status'],'failed')
        self.assertEqual(self.detail()['proposals'],[])

    def test_report_approval_is_owner_only_and_revision_bound(self):
        self.ready();out=self.outputs();draft=json.loads(out[0]['text']);draft['proposals']=[];out[0]['text']=json.dumps(draft);t=self.run_review(out)
        payload={'revision_id':t['result']['report_revision_id'],'peer_review':'declined','reason':'Owner reviewed the report limitations.'}
        self.uid='peer'
        self.assertEqual(self.client.post(f"/api/builder/tasks/{t['id']}/approve-report",json=payload).status_code,403)
        self.uid='owner'
        self.assertEqual(self.client.post(f"/api/builder/tasks/{t['id']}/approve-report",json={**payload,'revision_id':'wrong'}).status_code,409)
        self.assertEqual(self.client.post(f"/api/builder/tasks/{t['id']}/approve-report",json=payload).status_code,200)
        self.assertEqual(self.detail()['state'],{})

    def test_stale_result_discarded(self):
        self.ready();outputs=self.outputs();calls=0;respond_normal=self.responder(outputs)
        async def respond(*args,**kwargs):
            nonlocal calls
            if calls==0:
                with Session(self.engine) as s:
                    b=s.get(BuilderWorkspace,self.wid);b.state_version+=1;s.commit()
            calls+=1;return await respond_normal(*args,**kwargs)
        with patch.object(builder,'request_completion',respond):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review','action':'review'})
        self.assertEqual(self.detail()['tasks'][0]['status'],'stale');self.assertEqual(self.detail()['proposals'],[])

    def test_legacy_run_cannot_bypass_builder_guards(self):
        with patch('app.documents.request_completion',AsyncMock()) as call:
            r=self.client.post(f'/api/workspaces/{self.wid}/runs',json={'kind':'generate','instructions':'Bypass missing framework'})
            self.assertEqual(r.status_code,409);call.assert_not_called()

    def test_missing_document_assessment_rejects_entire_result(self):
        self.ready();out=self.outputs();draft=json.loads(out[0]['text']);draft['assessments']=[];out[0]['text']=json.dumps(draft)
        t=self.run_review(out);self.assertEqual(t['status'],'failed');self.assertEqual(self.detail()['proposals'],[])

    def test_stopped_task_does_not_apply_late_output(self):
        self.ready();out=self.outputs()
        async def respond(*args,**kwargs):
            with Session(self.engine) as s:
                t=s.scalar(select(BuilderTask));t.status='stopped';s.commit()
            return {'text':json.dumps({'reply':'Stopped','ready_for_review':False}),'model':'mock'}
        with patch.object(builder,'request_completion',respond):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review','action':'review'})
        self.assertEqual(self.detail()['tasks'][0]['status'],'stopped');self.assertEqual(self.detail()['proposals'],[])

    def test_insufficient_evidence_returns_intake_without_report(self):
        self.ready();out=self.outputs();draft=json.loads(out[0]['text']);draft.update(ready_for_review=False, report_markdown='',proposals=[],comments=[],assessments=[],reply='Submit learner prerequisites and performance standards.')
        with patch.object(builder,'request_completion',AsyncMock(return_value={'text':json.dumps({'reply':draft['reply'],'ready_for_review':False}),'model':'mock'})) as call:
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review','action':'review'})
            self.assertEqual(call.await_count,1)
        self.assertEqual(self.detail()['tasks'][0]['status'],'needs_information')
        self.assertNotIn('report_id',self.detail()['tasks'][0]['result'])

    def test_builder_comment_resolution_requires_owner_even_for_author(self):
        self.ready();source=self.detail()['sources'][0];self.uid='peer'
        r=self.client.post(f"/api/documents/{source['id']}/revisions/{source['revision_id']}/comments",json={'text':'Synthetic peer observation'})
        self.assertEqual(r.status_code,200,r.text);tid=r.json()['id']
        self.assertEqual(self.client.put(f'/api/comments/{tid}/state',json={'resolved':True}).status_code,403)
        self.uid='owner'
        self.assertEqual(self.client.put(f'/api/comments/{tid}/state',json={'resolved':True}).status_code,200)
        self.assertEqual(self.detail()['state'],{})

    def test_chat_without_guidance_saves_and_explains_next_step(self):
        with patch.object(builder,'request_completion',AsyncMock()) as call:
            r=self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Help me review my course','action':'chat'})
            self.assertEqual(r.status_code,200);call.assert_not_called()
        self.assertEqual(self.detail()['entries'][0]['text'],'Help me review my course')
        self.assertIn('framework',self.detail()['entries'][1]['text'])
        self.assertEqual(self.detail()['state'],{})

    def test_chat_routes_requested_review_through_quality_reviewer(self):
        self.ready()
        with patch.object(builder,'request_completion',AsyncMock(side_effect=self.responder())) as call:
            r=self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Please review the uploaded curriculum.'})
            self.assertEqual(r.status_code,200);self.assertGreaterEqual(call.await_count,5)
        self.assertEqual(self.detail()['tasks'][0]['status'],'completed')
        self.assertIn('report_id',self.detail()['tasks'][0]['result'])
        self.assertEqual(self.detail()['state'],{})

    def test_chat_can_interview_before_source_upload(self):
        fid=self.ready()
        self.wid=self.client.post('/api/builder/workspaces',json={'title':'No sources yet','framework_id':fid}).json()['id']
        reply={'reply':'Who are the learners and what must they be able to do?','ready_for_review':False}
        with patch.object(builder,'request_completion',AsyncMock(return_value={'text':json.dumps(reply),'model':'mock'})) as call:
            r=self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'I need help getting started.'})
            self.assertEqual(r.status_code,200);self.assertEqual(call.await_count,1)
        self.assertEqual(self.detail()['tasks'][0]['status'],'completed')

    def test_chat_followup_receives_report_and_pending_changes(self):
        self.ready();task=self.run_review()
        response={'reply':'The proposed assessment change needs your verification.','ready_for_review':False}
        with patch.object(builder,'request_completion',AsyncMock(return_value={'text':json.dumps(response),'model':'mock'})) as call:
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Explain the assessment gap you found.'})
            context=json.loads(call.call_args.args[0])['context']
            self.assertEqual(context['latest_report']['revision_id'],task['result']['report_revision_id'])
            self.assertEqual(context['proposed_changes'][0]['status'],'pending')
        self.assertEqual(self.detail()['state'],{})

    def test_framework_upload_requires_supported_model_and_derives_title(self):
        self.uid='admin'
        for model in ('unknown', ''):
            r=self.client.post('/api/frameworks',data={'version':'v1','model':model},files={'file':('test.txt',b'Synthetic framework guidance')})
            self.assertEqual(r.status_code,422)
        r=self.client.post('/api/frameworks',data={'version':'v1','model':'ADDIE'},files={'file':('test.txt',b'Synthetic framework guidance')})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['model'],'ADDIE')
        self.assertEqual(r.json()['title'],'ADDIE guidance')

    def test_new_workspace_automatically_pins_published_guidance(self):
        fid=self.ready()
        r=self.client.post('/api/builder/workspaces',json={'title':'Automatically configured'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.get('/api/builder/workspaces/'+r.json()['id']).json()['framework_id'],fid)

    def test_prepare_connects_waiting_workspace_once_without_changing_state(self):
        fid=self.ready()
        with Session(self.engine) as s:
            w=s.get(BuilderWorkspace,self.wid);w.framework_id=None;s.commit()
        self.uid='peer'
        self.assertEqual(self.client.post(f'/api/builder/workspaces/{self.wid}/prepare').status_code,403)
        self.uid='owner'
        self.assertEqual(self.client.post(f'/api/builder/workspaces/{self.wid}/prepare').json()['framework_id'],fid)
        self.uid='admin'
        new=self.client.post('/api/frameworks',data={'version':'new-version','model':'ADDIE'},files={'file':('test.txt',b'New synthetic guidance')}).json()['id']
        self.client.post('/api/frameworks/'+new+'/publish')
        self.uid='owner'
        self.assertEqual(self.client.post(f'/api/builder/workspaces/{self.wid}/prepare').json()['framework_id'],fid)
        self.assertEqual(self.detail()['state'],{})

    def test_chat_automatically_connects_newly_published_guidance(self):
        fid=self.ready()
        with Session(self.engine) as s:
            w=s.get(BuilderWorkspace,self.wid);w.framework_id=None;s.commit()
        reply={'reply':'First I will inspect the sources, then ask about missing performance standards.','ready_for_review':False}
        with patch.object(builder,'request_completion',AsyncMock(return_value={'text':json.dumps(reply),'model':'mock'})) as call:
            r=self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Here are my materials.'})
            self.assertEqual(r.status_code,200);self.assertEqual(call.await_count,1)
        self.assertEqual(self.detail()['framework_id'],fid)

    def test_large_collection_is_indexed_and_never_bundled_into_plan(self):
        self.ready()
        data=('Unique evidence line for larger collection. ' * 4000).encode()
        r=self.client.post(f'/api/builder/workspaces/{self.wid}/sources',files={'file':('large.txt',data)})
        self.assertEqual(r.status_code,200)
        with patch.object(builder,'request_completion',AsyncMock(return_value={'text':json.dumps({'reply':'Confirm the subject area.','ready_for_review':False}),'model':'mock'})) as call:
            r=self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Inspect these materials.'})
            self.assertEqual(r.status_code,200)
            prompt=call.call_args.args[0]
            self.assertLess(len(prompt),48000)
            context=json.loads(prompt)['context']
            self.assertNotIn('units',context['sources'][1])
            self.assertGreater(context['sources'][1]['passage_count'],50)
        self.assertEqual(self.detail()['tasks'][0]['status'],'completed')

    def test_retrieval_is_version_scoped_and_long_blocks_have_no_gaps(self):
        from app import knowledge
        from app.content import markdown
        content=markdown('Alpha ' * 1600)
        with Session(self.engine) as s:
            p=knowledge.index_content(s,'source','one',content)
            knowledge.index_content(s,'source','two',markdown('Secret other workspace evidence'))
            self.assertEqual(''.join(x.text for x in p),content['blocks'][0]['text'])
            hits=knowledge.search(s,{'source':['one']},'Alpha')
            self.assertTrue(hits);self.assertTrue(all(x['version_id']=='one' for x in hits))
            forbidden=knowledge.search(s,{'source':['two']},'Secret')[0]['id']
            with self.assertRaises(ValueError):knowledge.read_passages(s,{'source':['one']},[forbidden])
            s.commit()

    def test_shared_reference_publication_and_pinning(self):
        self.ready()
        fields={'title':'Synthetic doctrine','subject':'Planning','authority':'Synthetic authority','version':'v1'}
        self.assertEqual(self.client.post('/api/references',data=fields,files={'file':('ref.txt',b'Planning reference')}).status_code,403)
        self.uid='admin'
        r=self.client.post('/api/references',data=fields,files={'file':('ref.txt',b'Planning reference')})
        self.assertEqual(r.status_code,200,r.text);rid=r.json()['id']
        self.uid='owner';self.assertEqual(self.client.get('/api/references').json(),[])
        self.assertEqual(self.client.get('/api/references/'+rid).status_code,404)
        self.uid='admin';self.client.post('/api/references/'+rid+'/publish');self.uid='owner'
        with patch.object(builder,'request_completion',AsyncMock(return_value={'text':json.dumps({'reply':'Confirm discipline','ready_for_review':False}),'model':'mock'})):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Begin'})
        with Session(self.engine) as s:
            task=s.scalar(select(BuilderTask));self.assertEqual(task.snapshot['retrieval_scope']['reference'],[rid])
            self.assertEqual(task.snapshot['references'][0]['authority'],'Synthetic authority')

    def test_specialists_independent_before_challenge_and_chat_delegation(self):
        self.ready();stages=[];normal=self.responder()
        async def respond(prompt,**kwargs):
            req=json.loads(prompt);stages.append(req['stage'])
            if req['stage']=='independent':self.assertIsNone(req['prior_findings'])
            if req['stage']=='challenge':self.assertTrue(req['prior_findings'])
            return await normal(prompt,**kwargs)
        with patch.object(builder,'request_completion',side_effect=respond):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review'})
        self.assertLess(max(i for i,x in enumerate(stages) if x=='independent'),min(i for i,x in enumerate(stages) if x=='challenge'))
        t=self.detail()['tasks'][0];self.assertTrue(t['result']['coverage']['complete'])
        children=self.client.get(f"/api/builder/tasks/{t['id']}/specialists").json()
        self.assertEqual(len(children),4)
        self.assertTrue(any('Delegated to' in e['text'] for e in self.detail()['entries']))
        self.assertEqual(self.detail()['state'],{})

    def test_invalid_specialist_citation_blocks_final_report(self):
        self.ready();normal=self.responder()
        async def respond(prompt,**kwargs):
            out=await normal(prompt,**kwargs)
            if json.loads(prompt)['stage']=='independent':
                body=json.loads(out['text'])
                if body['findings']:body['findings'][0]['citations']=['unauthorized-passage']
                out['text']=json.dumps(body)
            return out
        with patch.object(builder,'request_completion',side_effect=respond):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review'})
        t=self.detail()['tasks'][0];self.assertEqual(t['status'],'failed');self.assertNotIn('report_id',t['result'])

    def test_missing_passage_coverage_blocks_review(self):
        self.ready();normal=self.responder()
        async def respond(prompt,**kwargs):
            out=await normal(prompt,**kwargs)
            if json.loads(prompt)['stage']=='independent':
                body=json.loads(out['text']);body['examined']=[];out['text']=json.dumps(body)
            return out
        with patch.object(builder,'request_completion',side_effect=respond):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review'})
        self.assertEqual(self.detail()['tasks'][0]['status'],'failed')

    def test_quick_review_cannot_be_approved(self):
        self.ready();normal=self.responder()
        async def respond(prompt,**kwargs):
            out=await normal(prompt,**kwargs)
            if json.loads(prompt)['stage']=='plan':
                body=json.loads(out['text']);body['scope']='quick';out['text']=json.dumps(body)
            return out
        with patch.object(builder,'request_completion',side_effect=respond):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Quick screening please'})
        t=self.detail()['tasks'][0];self.assertEqual(t['status'],'completed',t)
        self.assertFalse(t['result']['coverage']['complete'])
        self.assertEqual(self.client.post(f"/api/builder/tasks/{t['id']}/approve-report",json={'revision_id':t['result']['report_revision_id'],'peer_review':'declined','reason':'Read report'}).status_code,409)

    def test_material_findings_block_approval_even_after_decline(self):
        self.ready();t=self.run_review();p=self.detail()['proposals'][0]
        self.client.post(f"/api/builder/proposals/{p['id']}/verify",json={'decision':'decline','reason':'Decline suggestion','expected_state_version':0})
        self.assertEqual(self.client.post(f"/api/builder/tasks/{t['id']}/approve-report",json={'revision_id':t['result']['report_revision_id'],'peer_review':'declined','reason':'Decline peer review'}).status_code,409)

    def test_resource_limit_reports_incomplete_without_false_report(self):
        from app import orchestration
        self.ready()
        with patch.object(orchestration,'MAX_CALLS',2),patch.object(builder,'request_completion',side_effect=self.responder()):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review'})
        t=self.detail()['tasks'][0];self.assertEqual(t['status'],'incomplete');self.assertNotIn('report_id',t['result'])

    def test_active_instructions_admin_only(self):
        self.assertEqual(self.client.get('/api/builder/instructions').status_code,403)
        self.uid='admin';r=self.client.get('/api/builder/instructions')
        self.assertEqual(r.status_code,200)
        self.assertEqual({x['role'] for x in r.json()},{'planner','coordinator','specialist','reviewer','guidance'})
        self.assertTrue(all(x['text'] and len(x['version'])==64 for x in r.json()))

    def test_retrieval_tool_round_is_scoped_and_recorded(self):
        self.ready();normal=self.responder();requested=False
        async def respond(prompt,**kwargs):
            nonlocal requested
            req=json.loads(prompt)
            if req['stage']=='independent' and not requested:
                requested=True
                return {'text':json.dumps({'summary':'Need evidence','examined':[], 'confidence':'Low','rationale':'Need reference',
                    'retrieval':{'queries':['planning'],'passage_ids':[]}}),'model':'mock'}
            return await normal(prompt,**kwargs)
        with patch.object(builder,'request_completion',side_effect=respond):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review'})
        t=self.detail()['tasks'][0];self.assertEqual(t['status'],'completed',t)
        children=self.client.get(f"/api/builder/tasks/{t['id']}/specialists").json()
        self.assertTrue(any(c['result'].get('retrieval_log') for c in children))

    def test_full_review_of_large_source_uses_bounded_batches(self):
        self.ready()
        # Replace test source with >140k text: larger than the former entire-workspace limit.
        from app.models import Document, Revision
        from app.content import markdown
        with Session(self.engine) as s:
            d=s.scalar(select(Document).where(Document.kind=='source'))
            r=s.get(Revision,d.current_id);r.content=markdown('# Lesson\n\n' + 'Planning evidence and practice assessment. ' * 3700);s.commit()
        # Index was built at upload; immutable revisions must not mutate in real application.
        from app.models import EvidencePassage
        with Session(self.engine) as s:
            s.query(EvidencePassage).filter(EvidencePassage.collection=='source').delete();s.commit()
        normal=self.responder();sizes=[]
        async def respond(prompt,**kwargs):
            sizes.append(len(prompt.encode())+len(kwargs['system_prompt'].encode()))
            if json.loads(prompt)['stage']=='digest':
                return {'text':json.dumps({'summary':'Synthetic aggregate: incomplete assessment criteria.','limitations':'Synthetic test only.'}),'model':'mock'}
            return await normal(prompt,**kwargs)
        with patch.object(builder,'request_completion',side_effect=respond):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review'})
        t=self.detail()['tasks'][0];self.assertEqual(t['status'],'completed',t.get('error'))
        self.assertTrue(t['result']['coverage']['complete']);self.assertGreater(t['result']['coverage']['total'],60)
        self.assertTrue(all(n<48000 for n in sizes));self.assertGreater(len(sizes),20)

    def test_stop_during_specialist_keeps_child_stopped(self):
        self.ready();normal=self.responder()
        async def respond(prompt,**kwargs):
            if json.loads(prompt)['stage']=='independent':
                t=self.detail()['tasks'][0]
                self.assertEqual(self.client.post(f"/api/builder/tasks/{t['id']}/stop").status_code,200)
            return await normal(prompt,**kwargs)
        with patch.object(builder,'request_completion',side_effect=respond):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review'})
        t=self.detail()['tasks'][0];self.assertEqual(t['status'],'stopped')
        children=self.client.get(f"/api/builder/tasks/{t['id']}/specialists").json()
        self.assertEqual(children[0]['status'],'stopped');self.assertEqual(children[0]['result'],{})

    def test_surrounding_read_stays_in_authorized_version(self):
        from app import knowledge
        from app.content import markdown
        with Session(self.engine) as s:
            a=knowledge.index_content(s,'source','allowed',markdown('One\n\nTwo\n\nThree\n\nFour'))
            b=knowledge.index_content(s,'source','other',markdown('Confidential test fixture'))
            adjacent=knowledge.read_surrounding(s,{'source':['allowed']},a[1].id)
            self.assertEqual([p['text'] for p in adjacent],['One','Two','Three'])
            with self.assertRaises(ValueError):knowledge.read_surrounding(s,{'source':['allowed']},b[0].id)

    def test_moodle_source_upload_and_original_download(self):
        import tempfile
        from pathlib import Path
        from app import uploads
        from app.models import Original
        from tests.test_moodle import backup_bytes
        data=backup_bytes()
        with tempfile.TemporaryDirectory() as directory, patch.object(uploads,'UPLOAD_DIR',Path(directory)):
            r=self.client.post(f'/api/builder/workspaces/{self.wid}/sources',files={'file':('course.MBZ',data)})
            self.assertEqual(r.status_code,200,r.text)
            with Session(self.engine) as s:
                original=s.scalar(select(Original));self.assertIsNone(original.data);key=original.storage_key;oid=original.id
            self.assertTrue((Path(directory)/key).is_file())
            response=self.client.get('/api/originals/'+oid)
            self.assertEqual(response.status_code,200);self.assertEqual(response.content,data)
            (Path(directory)/key).unlink()
            self.assertEqual(self.client.get('/api/originals/'+oid).status_code,404)

    def test_moodle_revision_upload_uses_disk_original(self):
        import tempfile
        from pathlib import Path
        from app import uploads
        from app.models import Original, Document
        from tests.test_moodle import backup_bytes
        self.ready();source=self.detail()['sources'][0]
        data=backup_bytes('gzip')
        with tempfile.TemporaryDirectory() as directory, patch.object(uploads,'UPLOAD_DIR',Path(directory)):
            r=self.client.post(f"/api/documents/{source['id']}/upload",data={'expected_current':source['revision_id']},files={'file':('course.mbz',data)})
            self.assertEqual(r.status_code,200,r.text)
            with Session(self.engine) as s:
                original=s.scalar(select(Original).where(Original.storage_key.is_not(None)))
                self.assertTrue(original.storage_key);oid=original.id
            self.assertEqual(self.client.get('/api/originals/'+oid).content,data)

    def test_moodle_over_two_million_characters_uploads_and_indexes_without_loss(self):
        import tempfile
        from pathlib import Path
        from app import uploads, knowledge
        from app.models import Revision, Original
        from app.content import text_of
        from tests.test_moodle import backup_bytes, course_files
        body='Mission learning evidence. ' * 80000 + 'END_OF_LARGE_COURSE'
        self.assertGreater(len(body),2000000)
        files=course_files()
        files['activities/page_11/page.xml']=('<activity><page><name>Large lesson</name><content>'+body+'</content></page></activity>').encode()
        data=backup_bytes(files=files)
        with tempfile.TemporaryDirectory() as directory, patch.object(uploads,'UPLOAD_DIR',Path(directory)):
            r=self.client.post(f'/api/builder/workspaces/{self.wid}/sources',files={'file':('large-course.mbz',data)})
            self.assertEqual(r.status_code,200,r.text)
            with Session(self.engine) as session:
                from app.models import Document
                document=session.get(Document,r.json()['id'])
                revision=session.get(Revision,document.current_id)
                self.assertTrue(body in text_of(revision.content), "Extracted course text must retain every sentence and the final marker")
                passages=knowledge.allowed_passages(session,{'source':[revision.id]})
                self.assertTrue(body in ''.join(p.text for p in passages), 'Indexed passages must retain the complete course text')
                self.assertTrue(any('END_OF_LARGE_COURSE' in p.text for p in passages))
                original=session.scalar(select(Original).where(Original.revision_id==revision.id))
                self.assertEqual(uploads.stored_path(original.storage_key).read_bytes(),data)

    def test_review_displays_sequential_model_guidance_and_keeps_raw_report(self):
        self.ready();normal=self.responder();stages=[]
        async def respond(prompt,**kwargs):
            request=json.loads(prompt);stages.append(request['stage'])
            if request['stage']=='guidance':
                self.assertIn('# Review',request['raw_response']['report_markdown'])
                self.assertIn('Review prepared.',request['raw_response']['reply'])
                self.assertTrue(any(p['collection']=='framework' for p in request['evidence']))
                self.assertEqual(request['framework']['id'],self.detail()['framework_id'])
            return await normal(prompt,**kwargs)
        with patch.object(builder,'request_completion',side_effect=respond):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review'})
        task=self.detail()['tasks'][0];self.assertEqual(task['status'],'completed',task['error'])
        self.assertLess(stages.index('quality'),stages.index('guidance'))
        displayed=self.detail()['entries'][-1]['text']
        self.assertTrue(displayed.startswith('## TLDR'))
        self.assertIn('What must learners demonstrate to pass?',displayed)
        self.assertNotIn('Who verifies the scoring criteria?',displayed)
        self.assertEqual(len(task['result']['guidance']['questions']),2)
        self.assertIn('Review prepared.',task['result']['raw_reply'])
        self.assertIn('# Review',task['result']['coordinator']['report_markdown'])
        self.assertEqual(self.detail()['state'],{})

    def test_followup_answer_receives_question_queue_without_automatic_review(self):
        self.ready();self.run_review()
        answer={'reply':'That clarifies the performance standard. Who verifies the scoring criteria?','ready_for_review':False}
        with patch.object(builder,'request_completion',AsyncMock(return_value={'text':json.dumps(answer),'model':'mock'})) as call:
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Learners must produce an accurate operational plan.'})
            self.assertEqual(call.await_count,1)
            context=json.loads(call.call_args.args[0])['context']
            self.assertEqual(len(context['review_guidance']['guidance']['questions']),2)
            self.assertTrue(context['review_guidance']['evidence_current'])
            self.assertIn('operational plan',context['conversation'][-1]['text'])
        self.assertEqual(self.detail()['state'],{})

    def test_guidance_uses_configured_model_not_hardcoded_addie(self):
        fid=self.ready()
        with Session(self.engine) as s:
            s.get(FrameworkVersion,fid).model='Synthetic model'
            s.get(BuilderWorkspace,self.wid).model='Synthetic model';s.commit()
        normal=self.responder();seen=[]
        async def respond(prompt,**kwargs):
            req=json.loads(prompt)
            if req['stage']=='guidance':seen.append(req['configured_model'])
            return await normal(prompt,**kwargs)
        with patch.object(builder,'request_completion',side_effect=respond):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review'})
        self.assertEqual(seen,['Synthetic model'])
        self.assertEqual(self.detail()['tasks'][0]['status'],'completed')

    def test_guidance_cannot_cite_an_unretrieved_framework(self):
        self.ready();normal=self.responder()
        async def respond(prompt,**kwargs):
            result=await normal(prompt,**kwargs)
            if json.loads(prompt)['stage']=='guidance':
                body=json.loads(result['text']);body['framework_citations']=['unretrieved'];result['text']=json.dumps(body)
            return result
        with patch.object(builder,'request_completion',side_effect=respond):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Review'})
        task=self.detail()['tasks'][0];self.assertEqual(task['status'],'failed');self.assertNotIn('report_id',task['result'])

    def test_initial_file_analysis_also_gets_sequential_tldr(self):
        self.ready();normal=self.responder();stages=[]
        async def respond(prompt,**kwargs):
            req=json.loads(prompt);stages.append(req['stage'])
            if req['stage']=='plan':
                return {'text':json.dumps({'reply':'Raw initial analysis: assessment criteria are unspecified.','ready_for_review':False,'analyzed_sources':True}),'model':'mock'}
            if req['stage']=='guidance':
                self.assertIsNone(req['quality']);self.assertFalse(req['coverage']['complete'])
                self.assertIn('Raw initial analysis',req['raw_response']['reply'])
            return await normal(prompt,**kwargs)
        with patch.object(builder,'request_completion',side_effect=respond):
            self.client.post(f'/api/builder/workspaces/{self.wid}/chat',json={'text':'Please look over this file.'})
        self.assertEqual(stages,['plan','guidance'])
        task=self.detail()['tasks'][0];self.assertEqual(task['status'],'completed')
        self.assertNotIn('report_id',task['result'])
        self.assertTrue(self.detail()['entries'][-1]['text'].startswith('## TLDR'))
