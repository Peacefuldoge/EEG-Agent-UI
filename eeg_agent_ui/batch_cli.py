"""One-shot and resume CLI using the SAME public Core session/event API.

Approval requests are reported as JSON and exit code 2, allowing a human to
resume from terminal/web later. No separate non-HITL execution engine.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from .compat import EEGSession, STRATEGIES,check_core


def main(argv=None):
    check_core()
    p=argparse.ArgumentParser(description='Run or resume a durable EEG-Agent task')
    p.add_argument('--strategy',choices=STRATEGIES,default='plan-execute')
    p.add_argument('--task',help='EEG analysis task in natural language')
    p.add_argument('--input',type=Path,help='Input EEG file')
    p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--output-root',type=Path,default=Path('./agent_runs'))
    p.add_argument('--model',default=os.getenv('EEG_LLM_MODEL','qwen3-8b'))
    p.add_argument('--base-url',default=os.getenv('EEG_LLM_BASE_URL','http://127.0.0.1:8000/v1'))
    p.add_argument('--session-id',help='Restore a previous Core session')
    p.add_argument('--thread-id',help='Resume an existing unfinished Core thread')
    approval=p.add_mutually_exclusive_group()
    approval.add_argument('--approve',action='store_true')
    approval.add_argument('--reject',action='store_true')
    p.add_argument('--max-steps',type=int,default=12)
    p.add_argument('--max-replans',type=int,default=1)
    p.add_argument('--no-checkpoint',action='store_true')
    args=p.parse_args(argv)
    if args.max_steps<1 or args.max_steps>30 or args.max_replans<0 or args.max_replans>3:
        p.error('--max-steps must be 1..30; --max-replans must be 0..3')
    if args.thread_id:
        if not args.session_id:
            p.error('Resuming --thread-id requires --session-id')
    elif not args.task or not args.input:
        p.error('New tasks require both --task and --input')

    s=EEGSession(data_root=args.data_root,output_root=args.output_root,
                 strategy=args.strategy,model=args.model,base_url=args.base_url,
                 max_steps=args.max_steps,max_replans=args.max_replans,
                 checkpoint=not args.no_checkpoint,session_id=args.session_id)
    if not args.thread_id:
        s.set_strategy(args.strategy)
        s.set_file(args.input)
        events=s.stream_agent(args.task)
    else:
        decision=True if args.approve else False if args.reject else None
        events=s.resume_run(args.thread_id,approved=decision)
    result=None
    for ev in events:
        if ev['type']=='node_started':
            print('NODE_START '+ev['node'],file=sys.stderr)
        elif ev['type']=='node_completed':
            print('NODE_END '+ev['node'],file=sys.stderr)
        elif ev['type']=='token':
            print(ev['text'],end='',flush=True,file=sys.stderr)
        elif ev['type']=='run_finished':
            result=ev['record']
    if result is None:
        raise RuntimeError('Core did not emit a final run record')
    print(json.dumps({'session_id':s.session_id,'thread_id':result['thread_id'],
                      'status':result['status'],'answer':result.get('answer',''),
                      'pending':result.get('pending',[]),
                      'manifest':result.get('manifest')},ensure_ascii=False,indent=2))
    if result['status']=='awaiting_approval':
        print('Approval required. Resume with --session-id ID --thread-id ID --approve or --reject.',file=sys.stderr)
        raise SystemExit(2)
    if result['status']!='completed':
        raise SystemExit(1)

if __name__=='__main__':main()
