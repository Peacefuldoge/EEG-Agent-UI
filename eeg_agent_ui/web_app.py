"""Optional Chainlit client: real-time streaming + HITL + explicit session recovery.

The local Core SQLite store is not a replacement for Chainlit's optional
multi-user/authentication data layer. This UI targets trusted, single-user use.
"""
from __future__ import annotations
import asyncio
import os
import shutil
import uuid
import threading
import json
from pathlib import Path
import chainlit as cl
from chainlit.input_widget import Select
from eeg_agent_ui.compat import EEGSession,STRATEGIES,SUPPORTED_RAW,check_core
check_core()

DATA_ROOT=Path(os.getenv('EEG_DATA_ROOT','./examples/demo_npz')).resolve()
OUTPUT_ROOT=Path(os.getenv('EEG_OUTPUT_ROOT','./agent_runs')).resolve()
MODEL=os.getenv('EEG_LLM_MODEL','qwen3-8b')
BASE_URL=os.getenv('EEG_LLM_BASE_URL','http://127.0.0.1:8000/v1')


def new_session(session_id=None):
    return EEGSession(data_root=DATA_ROOT,output_root=OUTPUT_ROOT,model=MODEL,
                      base_url=BASE_URL,session_id=session_id)


async def async_events(factory):
    """Consume the synchronous Core generator in a worker; never block Chainlit."""
    loop=asyncio.get_running_loop()
    queue=asyncio.Queue()
    def worker():
        try:
            for event in factory():
                loop.call_soon_threadsafe(queue.put_nowait,('event',event))
        except BaseException as exc:
            loop.call_soon_threadsafe(queue.put_nowait,('error',exc))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait,('end',None))
    threading.Thread(target=worker,daemon=True).start()
    while True:
        kind,value=await queue.get()
        if kind=='end':break
        if kind=='error':raise value
        yield value


def artifacts(report):
    files=[];seen=set()
    sources=[report.get('manifest')]
    for entry in report.get('trace',[]):
        result=entry.get('result',{})
        if isinstance(result,dict):
            sources.extend(result.get(k) for k in ('report_html','summary_json',
                'quality_comparison_html','quality_comparison_csv','quality_comparison_json',
                'output_metadata_json','batch_metadata_json'))
    for item in sources:
        if not item:continue
        path=Path(item).resolve()
        if path.is_file() and path.is_relative_to(OUTPUT_ROOT) and str(path) not in seen:
            files.append(cl.File(name=path.name,path=str(path)))
            seen.add(str(path))
    return files


async def display_events(factory):
    reply=cl.Message(content='')
    await reply.send()
    nodes={};finished=None;had_tokens=False
    async for ev in async_events(factory):
        kind=ev['type']
        if kind=='token':
            await reply.stream_token(ev['text'])
            had_tokens=True
        elif kind=='node_started':
            name=ev['node']
            step=cl.Step(name=name,type='tool')
            step.output='执行中…'
            await step.send()
            nodes[name]=step
        elif kind=='node_completed':
            name=ev['node']
            if name in nodes:
                step=nodes[name]
                step.output='已完成 · '+ev.get('status','running')
                await step.update()
        elif kind=='tool_progress':
            progress=ev.get('data',{})
            if progress.get('kind')=='batch_progress':
                await cl.Message(content=f"Batch {progress.get('index')}/{progress.get('total')} · {progress.get('phase')} · {Path(progress.get('file','')).name}").send()
            else:
                await cl.Message(content=f"⚙ {progress.get('tool')}: {progress.get('phase')}").send()
        elif kind in ('run_finished','completed'):
            finished=ev.get('record',{'status':'completed','answer':ev.get('answer','')})
    if finished:
        if not had_tokens or finished.get('answer','')!=reply.content:
            reply.content=finished.get('answer','') or f"Task status: {finished['status']}"
        await reply.update()
        if finished.get('thread_id'):
            await cl.Message(content=(f"**Status:** {finished['status']} · **Thread:** `{finished['thread_id']}`"),
                             elements=artifacts(finished)).send()
        if finished.get('status')=='awaiting_approval':
            await request_approval(finished['thread_id'],finished.get('pending') or [])
    return finished


async def request_approval(thread_id,requests):
    details='\n'.join(f"- `{req.get('tool')}`: `{req.get('arguments')}`" for req in requests)
    response=await cl.AskActionMessage(
        content=f'### EEG operation requires approval\n{details}\n\nThread: `{thread_id}`',
        actions=[cl.Action(name='eeg_approve',payload={'approved':True},label='Approve'),
                 cl.Action(name='eeg_reject',payload={'approved':False},label='Reject'),
                 cl.Action(name='eeg_edit',payload={'edit':True},label='Modify parameters')],
        timeout=600
    ).send()
    if response is None:
        await cl.Message(content=f'未做出决定；任务已保存。可稍后输入 `/resume {thread_id}` 重新审批。').send()
        return
    payload=response.get('payload',{})
    s=cl.user_session.get('eeg_session')
    if payload.get('edit'):
        answer=await cl.AskUserMessage(content='请输入修改参数的 JSON 对象，例如 {"target_sfreq": 200}；修改后必须再次审批。',timeout=600).send()
        if not answer:return
        try:changes=json.loads(answer['output'])
        except (ValueError,KeyError):
            await cl.Message(content='无效 JSON；任务仍等待审批。').send();return
        if not isinstance(changes,dict) or not changes:
            await cl.Message(content='请输入非空的 JSON 参数对象。').send();return
        await display_events(lambda:s.resume_run(thread_id,parameters=changes))
    else:
        approved=bool(payload.get('approved',False))
        await display_events(lambda:s.resume_run(thread_id,approved=approved))


@cl.on_chat_start
async def start():
    s=new_session()
    cl.user_session.set('eeg_session',s)
    cl.user_session.set('mode','chat')
    await cl.ChatSettings([
        Select(id='Strategy',label='Agent strategy',values=list(STRATEGIES),initial_index=1),
        Select(id='Mode',label='Mode',values=['chat','agent'],initial_index=0),
    ]).send()
    await cl.Message(content=f'**EEG-Agent** · session `{s.session_id}`\n\n'
                     'Commands: `/file PATH`, `/upload`, `/agent`, `/chat`, `/strategy rewoo`, '
                     '`/sessions`, `/use SESSION_ID`, `/runs`, `/resume THREAD_ID`. '
                     'Core persists sessions and tasks locally; the UI is optional.').send()


@cl.on_settings_update
async def settings_update(settings):
    s=cl.user_session.get('eeg_session')
    s.set_strategy(settings.get('Strategy','react'))
    cl.user_session.set('mode',settings.get('Mode','chat'))


@cl.on_message
async def on_message(msg:cl.Message):
    s:EEGSession=cl.user_session.get('eeg_session')
    text=msg.content.strip()
    cmd,_,tail=text.partition(' ')
    try:
        if cmd=='/file':
            path=s.set_file(tail.strip().strip('"\''))
            await cl.Message(content=f'已选择 EEG 文件：`{path}`').send();return
        if cmd=='/upload':
            files=await cl.AskFileMessage(content='选择 EEG 文件（最大 512 MB）',
                  accept={'application/octet-stream':sorted(SUPPORTED_RAW)},
                  max_size_mb=512,max_files=1).send()
            if not files:return
            f=files[0];src=Path(f.path);ext=Path(f.name).suffix.lower()
            if ext not in SUPPORTED_RAW or not src.is_file() or src.stat().st_size>512*1024*1024:
                raise ValueError('Invalid upload')
            target=OUTPUT_ROOT/'uploads';target.mkdir(parents=True,exist_ok=True)
            dest=target/(uuid.uuid4().hex+ext)
            await asyncio.to_thread(shutil.copyfile,src,dest)
            s.set_file(dest)
            await cl.Message(content=f'上传完成：`{dest}`').send();return
        if cmd in ('/chat','/agent'):
            cl.user_session.set('mode',cmd.lstrip('/'))
            await cl.Message(content='Mode: '+cmd.lstrip('/')).send();return
        if cmd=='/strategy':
            s.set_strategy(tail.strip());await cl.Message(content='Strategy: '+s.strategy).send();return
        if cmd=='/clear':
            s.clear();await cl.Message(content='Conversation history cleared').send();return
        if cmd=='/status':
            await cl.Message(content=f'Session `{s.session_id}` · strategy `{s.strategy}` · file `{s.current_file}`').send();return
        if cmd=='/sessions':
            rows=s.list_sessions()
            await cl.Message(content='\n'.join(f"- `{x['session_id']}` · {x['updated_at']}" for x in rows) or 'No sessions').send();return
        if cmd=='/use':
            previous=s
            s=new_session(tail.strip())
            cl.user_session.set('eeg_session',s)
            await cl.Message(content=f'Restored `{s.session_id}` · {len(s.get_history())} stored messages · file `{s.current_file}`. Use `/history` to display saved conversation.').send();return
        if cmd=='/history':
            hist=s.get_history(limit=30)
            for entry in hist:
                await cl.Message(author='User' if entry['role']=='user' else 'EEG-Agent',
                                 content=entry['content']).send()
            return
        if cmd=='/runs':
            runs=s.list_runs()
            await cl.Message(content='\n'.join(f"- `{r['thread_id']}` · {r['status']} · {r['task'][:80]}" for r in runs) or 'No runs').send();return
        if cmd=='/resume':
            thread_id=tail.strip()
            run=s.get_run(thread_id)
            if run['status']=='awaiting_approval':
                await request_approval(thread_id,run['pending'] or [])
            else:
                await display_events(lambda:s.resume_run(thread_id))
            return
        if cmd=='/edit':
            thread_id,sep,params=tail.strip().partition(' ')
            if not sep:raise ValueError('Usage: /edit THREAD_ID {"target_sfreq":200}')
            await display_events(lambda:s.resume_run(thread_id,parameters=json.loads(params)))
            return
        if cmd in ('/approve','/reject'):
            await display_events(lambda:s.resume_run(tail.strip(),approved=(cmd=='/approve')))
            return
        if not text:return
        if cl.user_session.get('mode','chat')=='chat':
            await display_events(lambda:s.stream_chat(text))
        else:
            if not s.current_file:
                await cl.Message(content='请先用 `/file /路径/record.edf` 选择 EEG 文件。').send();return
            await display_events(lambda:s.stream_agent(text))
    except Exception as exc:
        await cl.Message(content=f'Error: `{type(exc).__name__}: {exc}`').send()
