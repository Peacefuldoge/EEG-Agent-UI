"""Optional interactive terminal client. All analysis logic belongs to Core."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
from .compat import EEGSession,STRATEGIES,check_core


def main(argv=None):
    check_core()
    parser=argparse.ArgumentParser(description='EEG Agent terminal chat (LangGraph/vLLM)')
    parser.add_argument('--data-root',type=Path,default=Path('examples/demo_npz'))
    parser.add_argument('--output-root',type=Path,default=Path('agent_runs'))
    parser.add_argument('--input',type=Path)
    parser.add_argument('--session-id',help='Restore a previous persistent Core session')
    parser.add_argument('--strategy',choices=STRATEGIES,default='react')
    parser.add_argument('--mode',choices=('chat','agent'),default='chat')
    parser.add_argument('--model',default=os.getenv('EEG_LLM_MODEL','qwen3-8b'))
    parser.add_argument('--base-url',default=os.getenv('EEG_LLM_BASE_URL','http://127.0.0.1:8000/v1'))
    parser.add_argument('--no-checkpoint',action='store_true')
    args=parser.parse_args(argv)

    def create(sid=None):
        return EEGSession(data_root=args.data_root,output_root=args.output_root,
                          strategy=args.strategy,model=args.model,base_url=args.base_url,
                          checkpoint=not args.no_checkpoint,session_id=sid)

    session=create(args.session_id)
    if args.input:session.set_file(args.input)
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
        from rich.console import Console
        console=Console()
        history_file=session.output_root/'.chat_prompt_history'
        prompt=PromptSession(history=FileHistory(str(history_file)))
        def show(s):console.print(s,markup=False)
        def ask(s):return prompt.prompt(s)
    except ImportError:
        def show(s):print(s)
        def ask(s):return input(s)

    mode=args.mode
    show(f'EEG-Agent UI | session={session.session_id} | strategy={session.strategy}')
    show('Commands: /chat /agent /file PATH /strategy NAME /sessions /use ID /runs /history /resume ID /approve ID /reject ID /edit ID JSON /status /clear /exit')

    def render(events):
        record=None;streamed=False
        for event in events:
            kind=event['type']
            if kind=='token':
                print(event['text'],end='',flush=True)
                streamed=True
            elif kind=='node_started':show('\n  ▶ '+event['node'])
            elif kind=='node_completed':show('  ✓ '+event['node']+' ['+event.get('status','running')+']')
            elif kind=='tool_progress':
                d=event.get('data',{})
                if d.get('kind')=='batch_progress':
                    show(f"    file {d.get('index')}/{d.get('total')}: {d.get('phase')} {d.get('file')}")
                else:show('    '+str(d.get('tool'))+': '+str(d.get('phase')))
            elif kind=='approval_required':
                for req in event['requests']:
                    show('\nAPPROVAL REQUIRED: '+str(req.get('tool'))+' '+str(req.get('arguments')))
                show('Use /approve '+event['thread_id']+' or /reject '+event['thread_id'])
            elif kind=='run_finished':
                record=event['record']
            elif kind=='completed':
                record={'status':'completed','answer':event['answer']}
        if record:
            if not streamed or record['status']!='completed':
                show('\n'+(record.get('answer') or ''))
            else:print()
            show('Status: '+record['status'])
            if record.get('thread_id'):show('Thread: '+record['thread_id'])
            if record.get('manifest'):show('Trace: '+record['manifest'])
        return record

    while True:
        try:msg=ask(f'[{mode}:{session.strategy}] > ').strip()
        except (EOFError,KeyboardInterrupt):show('\nGoodbye.');break
        if not msg:continue
        cmd,_,value=msg.partition(' ')
        try:
            if cmd in ('/exit','/quit'):break
            if cmd=='/help':show('Use /file PATH then /agent; /sessions and /use ID restore chat; /runs lists tasks; /approve ID and /reject ID resume HITL.');continue
            if cmd=='/chat':mode='chat';show('Chat mode');continue
            if cmd=='/agent':mode='agent';show('Agent mode');continue
            if cmd=='/strategy':session.set_strategy(value.strip());show('Strategy: '+session.strategy);continue
            if cmd=='/file':show('Input: '+session.set_file(value.strip().strip('"\'')));continue
            if cmd=='/status':show(f'session={session.session_id} mode={mode} strategy={session.strategy} file={session.current_file} endpoint={session.base_url}');continue
            if cmd=='/clear':session.clear();show('Conversation history cleared');continue
            if cmd=='/sessions':
                for x in session.list_sessions():show(f"{x['session_id']} | {x['strategy']} | {x['updated_at']}")
                continue
            if cmd=='/use':
                session=create(value.strip());show('Restored: '+session.session_id);continue
            if cmd=='/history':
                for m in session.get_history():show(m['role']+': '+m['content'])
                continue
            if cmd=='/runs':
                for r in session.list_runs():show(f"{r['thread_id']} | {r['status']} | {r['task'][:70]}")
                continue
            if cmd=='/edit':
                import json
                thread_id,sep,params=value.strip().partition(' ')
                if not sep:show('Usage: /edit THREAD_ID {"target_sfreq": 200}');continue
                edits=json.loads(params)
                render(session.resume_run(thread_id,parameters=edits));continue
            if cmd in ('/approve','/reject','/resume'):
                thread_id=value.strip()
                if not thread_id:show('Provide thread ID');continue
                approved=True if cmd=='/approve' else False if cmd=='/reject' else None
                render(session.resume_run(thread_id,approved=approved));continue
            if mode=='chat':render(session.stream_chat(msg))
            else:render(session.stream_agent(msg))
        except KeyboardInterrupt:show('Interrupted. Use /runs and /resume if a checkpoint was saved.')
        except Exception as exc:show(f'Execution error: {type(exc).__name__}: {exc}')

if __name__=='__main__':main()
