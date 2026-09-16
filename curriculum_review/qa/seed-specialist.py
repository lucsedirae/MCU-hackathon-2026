import asyncio, json, os
from unittest.mock import patch, AsyncMock
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import builder
from app.models import User, Workspace, BuilderTask
assert os.environ.get('QA_FIXTURES_ONLY') == '1'
with Session(builder.engine) as s:
    users=list(s.scalars(select(User)))
    assert users and all(u.email.endswith('@example.test') for u in users), 'Only disposable synthetic QA accounts allowed'
    admin=next(u for u in users if u.email=='builder-admin@example.test')
    w=s.scalar(select(Workspace).where(Workspace.owner_id==admin.id).order_by(Workspace.created.desc()))
    context=builder.snapshot(s,w.id,'Review the synthetic planning course')
    context['owner_id']=admin.id
    task=BuilderTask(workspace_id=w.id,author_id=admin.id,action='review',snapshot=context)
    s.add(task);s.commit();tid=task.id
rids=[s['revision_id'] for s in context['sources']]
async def respond(prompt,**kwargs):
    q=json.loads(prompt);stage=q['stage']
    if stage=='plan':
        out={'reply':'I will review the evidence with specialists.','ready_for_review':True,'subjects_confirmed':True,
            'revision_ids':rids,'assignments':[{'role':role,'subject':'Synthetic planning','objective':'Check evidence and instructional alignment','revision_ids':rids} for role in ('sme','assessment','exercise','technical')]}
    elif stage in ('independent','challenge','verification'):
        out={'summary':'Synthetic specialist checked the assigned material.','examined':q['required_passage_ids'],'confidence':'Moderate','rationale':'Synthetic demonstration with limited evidence.',
            'findings':[{'kind':'gap','title':'Specify assessment criteria','explanation':'The synthetic course does not define scoring criteria.','recommendation':'Have the course owner verify the assessment standard.','citations':[q['required_passage_ids'][0]],'material':True}] if stage=='independent' else []}
    elif stage=='guidance':
        out={'tldr':'Practice is present; assessment standards need clarification.', 'model_lens':'The pinned guidance requires evidence and owner approval.',
            'gaps':['Assessment standard'], 'questions':[{'question':'What must learners demonstrate to pass?', 'why':'This establishes the performance standard.'}],
            'next_step':'Clarify the standard.', 'framework_citations':[p['id'] for p in q['evidence'] if p['collection']=='framework'][:1]}
    elif stage=='digest':out={'summary':'Assessment criteria need owner attention.','limitations':'Synthetic checks only.'}
    elif stage=='synthesis':
        out={'reply':'Your review report is ready. Please verify the assessment gaps.','ready_for_review':True,'report_markdown':'# Synthetic curriculum review\n\nStrength: planning practice. Gap: clarify scoring criteria.',
            'assessments':[{'revision_id':rid,'confidence':'Moderate','rationale':'Limited synthetic evidence.','gaps':['Scoring criteria'],'peer_review':'Consult an assessment peer.'} for rid in rids]}
    else:out={'passed':True,'findings':[],'confidence':'Moderate','rationale':'Scope and limitations are visible.','peer_review':'Consult a human peer.'}
    return {'text':json.dumps(out),'model':'synthetic-mock'}
with patch.object(builder,'request_completion',AsyncMock(side_effect=respond)):
    asyncio.run(builder.execute_task(tid))
with Session(builder.engine) as s:
    task=s.get(BuilderTask,tid)
    assert task.status=='completed', task.error
    print('Synthetic specialist review ready for browser QA:',tid)
