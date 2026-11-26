"""Opt-in native orchestration. Credentials stay inside the separate local executor.

This module does not implement hotel packets, claim runtime success, or connect by
itself. A verified room manifest and an explicitly selected executor are required.
"""
import json
import math
import os
import selectors
import subprocess
import time
from pathlib import Path
from .core import ModelError, load_file, unique_keys

PROTOCOL = 'hgz-classic-editor/1'

class NativeExecutor:
    def __init__(self, command, timeout=30):
        if not isinstance(command,list) or not command or any(not isinstance(x,str) for x in command):
            raise ModelError('Executor must be an explicit argument list')
        self.command=command
        self.timeout=timeout
        self.proc=None
        self.sequence=0
        self.buffer=b''
        self.room_id=None
        self.close_status=None
    def __enter__(self):
        self.proc=subprocess.Popen(self.command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=None,bufsize=0)
        return self
    def __exit__(self,*args):
        if self.proc is None:return
        stop_ack=False
        try:
            if self.proc.poll() is None and self.room_id is not None:
                try:
                    self.call('stop',self.room_id)
                    stop_ack=True
                except (OSError,ValueError,ModelError):pass
            if not self.proc.stdin.closed:self.proc.stdin.close()
            try:self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                try:self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
            self.close_status={'stop_acknowledged':stop_ack,'exit_code':self.proc.returncode,'ticket_cleanup_verified':False}
        finally:
            if not self.proc.stdin.closed:self.proc.stdin.close()
            self.proc.stdout.close()
    def call(self,action,room_id,**payload):
        self.room_id=room_id
        self.sequence+=1
        request={'protocol':PROTOCOL,'request_id':self.sequence,'action':action,'room_id':room_id,**payload}
        encoded=(json.dumps(request,separators=(',',':'))+'\n').encode()
        if len(encoded)>65536:raise ModelError('Native request too large; no write issued')
        self.proc.stdin.write(encoded)
        self.proc.stdin.flush()
        deadline=time.monotonic()+self.timeout
        with selectors.DefaultSelector() as sel:
            sel.register(self.proc.stdout,selectors.EVENT_READ)
            while b'\n' not in self.buffer:
                left=deadline-time.monotonic()
                if left<=0 or not sel.select(left):raise ModelError('Native executor timed out; no retry issued')
                part=os.read(self.proc.stdout.fileno(),65536)
                if not part:raise ModelError('Native executor closed; outcome unknown, inspect before retry')
                self.buffer+=part
                if len(self.buffer)>1048576:raise ModelError('Executor response too large')
        line,self.buffer=self.buffer.split(b'\n',1)
        response=json.loads(line.decode('utf-8'),object_pairs_hook=unique_keys)
        if not isinstance(response,dict) or response.get('protocol')!=PROTOCOL or response.get('request_id')!=self.sequence or response.get('room_id')!=room_id:
            raise ModelError('Executor response identity mismatch')
        if response.get('ok') is not True:raise ModelError('Native executor rejected action; inspect executor locally')
        if 'box_id' in payload and response.get('box_id')!=payload['box_id']:
            raise ModelError('Executor box identity mismatch')
        return response

def valid_manifest(plan,require_roles=False):
    if not isinstance(plan,dict) or plan.get('protocol')!=PROTOCOL or plan.get('target')!='habbogz':
        raise ModelError('Only the scoped Habbogz classic acceptance plan is supported')
    if type(plan.get('room_id')) is not int or plan['room_id']<=0 or plan.get('private_acceptance_room') is not True:
        raise ModelError('Verified private acceptance room required')
    if type(plan.get('owner_id')) is not int or plan['owner_id']<=0 or plan.get('room_state')!='hide':
        raise ModelError('Exact owner and real hidden room state required')
    items=plan.get('items');steps=plan.get('steps')
    if not isinstance(items,list) or not items or not isinstance(steps,list) or len(steps)!=4:
        raise ModelError('Room inventory and four classic steps required')
    if any(not isinstance(x,dict) for x in steps):raise ModelError('Invalid native step')
    if {x.get('role') for x in steps}!={'repeat','chase','collision','teleport'}:
        raise ModelError('Four distinct classic box roles required')
    ids=[]
    for item in items:
        if not isinstance(item,dict) or type(item.get('id')) is not int or item['id']<=0 or type(item.get('base_id')) is not int or not isinstance(item.get('position'),list) or len(item['position'])!=3:
            raise ModelError('Exact item id, base and position required')
        if any(type(n) not in (int,float) for n in item['position']):raise ModelError('Numeric position required')
        ids.append(item['id'])
    if len(set(ids))!=len(ids):raise ModelError('Duplicate item id')
    boxes=set()
    for step in steps:
        if type(step.get('box_id')) is not int or step['box_id'] not in ids or step['box_id'] in boxes:
            raise ModelError('Each step must identify a different verified box')
        boxes.add(step['box_id'])
        if not isinstance(step.get('native'),dict) or not isinstance(step.get('expected'),dict):
            raise ModelError('Grounded native settings and normalized readback required')
    mobile=plan.get('mobile_item_ids',[])
    chase=next(step for step in steps if step['role']=='chase')
    if (not isinstance(mobile,list) or len(mobile)>1 or
        any(type(n) is not int or n not in ids or n in boxes for n in mobile) or
        (mobile and (len(mobile)!=len(set(mobile)) or chase['native'].get('selected_items')!=mobile or chase['expected'].get('selected_items')!=mobile))):
        raise ModelError('Only the explicit chase target may have dynamic position')
    roles=plan.get('role_items')
    if require_roles and roles is None:
        raise ModelError('role_items with six exact item ids required')
    if roles is not None:
        if not isinstance(roles,dict) or set(roles)!={'duck','start','repeat','chase','collision','teleport'} or any(type(v) is not int or v not in ids for v in roles.values()) or len(set(roles.values()))!=6:
            raise ModelError('Six exact role item ids required')
        if any(roles[x['role']]!=x['box_id'] for x in steps):
            raise ModelError('Role item differs from step box')
        for role,target in [('chase','duck'),('teleport','start')]:
            step=next(x for x in steps if x['role']==role)
            if step['native'].get('selected_items')!=[roles[target]] or step['expected'].get('selected_items')!=[roles[target]]:
                raise ModelError('Role target differs from selected item')
        if mobile!=[roles['duck']]:raise ModelError('Duck must be only mobile item')
    return plan

ROLE_KEYS=('duck','start','repeat','chase','collision','teleport')

def check_role_items(plan):
    """Contract hgz-classic-editor/1 extension: role_items names the six exact items.
    Rejects before any write if it is missing or contradicts steps, targets or mobile item."""
    ri=plan.get('role_items')
    if not isinstance(ri,dict) or set(ri)!=set(ROLE_KEYS) or any(type(v) is not int or v<=0 for v in ri.values()):
        raise ModelError('role_items with six exact item ids required')
    if len(set(ri.values()))!=6:raise ModelError('One item cannot hold two roles')
    ids={i['id'] for i in plan['items']}
    if any(v not in ids for v in ri.values()):raise ModelError('role_items names an item outside the inventory')
    by={x['role']:x for x in plan['steps']}
    for r in ('repeat','chase','collision','teleport'):
        if by[r]['box_id']!=ri[r]:raise ModelError('Step box contradicts role_items for '+r)
    if by['chase']['native'].get('selected_items')!=[ri['duck']] or by['chase']['expected'].get('selected_items')!=[ri['duck']]:
        raise ModelError('Chase target contradicts role_items')
    if by['teleport']['native'].get('selected_items')!=[ri['start']] or by['teleport']['expected'].get('selected_items')!=[ri['start']]:
        raise ModelError('Teleport destination contradicts role_items')
    if plan.get('mobile_item_ids')!=[ri['duck']]:raise ModelError('Mobile item must be exactly the selected duck')

def compare_inventory(plan,observed):
    if not isinstance(observed,list) or len(observed)!=len(plan['items']):return False
    expected={item['id']:item for item in plan['items']}
    if any(not isinstance(item,dict) or type(item.get('id')) is not int for item in observed):return False
    if len({item['id'] for item in observed})!=len(observed):return False
    mobile=plan.get('mobile_item_ids',[])
    for item in observed:
        wanted=expected.get(item['id'])
        if wanted is None or set(item)!=set(wanted):return False
        if item['id'] not in mobile:
            if item!=wanted:return False
        else:
            position=item.get('position')
            if not isinstance(position,list) or len(position)!=3 or any(type(n) not in (int,float) or not math.isfinite(n) for n in position):return False
            if any(item[k]!=wanted[k] for k in wanted if k!='position'):return False
    return True

def _fresh_context(plan,executor,room):
    obs=executor.call('inspect_room',room)
    if obs.get('room_id')!=room or obs.get('owner_id')!=plan['owner_id'] or obs.get('room_state')!=plan['room_state'] or obs.get('private_acceptance_room') is not True or not compare_inventory(plan,obs.get('items')):
        raise ModelError('Room context drifted (room, owner, state, privacy or inventory); stopping')
    return obs

def current_room_matches(plan,observed):
    return (isinstance(observed,dict) and observed.get('room_id')==plan['room_id']
            and observed.get('owner_id')==plan['owner_id'] and observed.get('room_state')=='hide'
            and observed.get('private_acceptance_room') is True and compare_inventory(plan,observed.get('items')))

def apply_classic(plan,executor,require_roles=False):
    plan=valid_manifest(plan,require_roles)
    room=plan['room_id']
    report={'target':'habbogz','room_id':room,'configured':[],'configuration_verified':False,'gameplay_verified':False,'video_recorded':False}
    observed=executor.call('inspect_room',room)
    if not current_room_matches(plan,observed):
        raise ModelError('Room state differs from approved manifest; no writes issued')
    report['inspected_items']=observed['items']
    report['mobile_item_ids']=plan.get('mobile_item_ids',[])
    print(json.dumps({'event':'room_inspected','room_id':room,'items':observed['items'],'mobile_item_ids':report['mobile_item_ids']},ensure_ascii=False),flush=True)
    # Snapshot every box before any write, for owner-controlled recovery.
    baseline=[]
    for step in plan['steps']:
        old=executor.call('read_box',room,box_id=step['box_id'],role=step['role'])
        if old.get('observed_via')!='reopened_native_editor' or not isinstance(old.get('settings'),dict):
            raise ModelError('Cannot capture native baseline; no writes issued')
        baseline.append({'box_id':step['box_id'],'settings':old['settings']})
    report['baseline']=baseline
    print(json.dumps({'event':'baseline','report':report},ensure_ascii=False),flush=True)
    for step in plan['steps']:
        fresh=executor.call('inspect_room',room)
        if not current_room_matches(plan,fresh):
            raise ModelError('Room authority or inventory drift before write; partial changes possible, inspect baseline')
        executor.call('configure_box',room,box_id=step['box_id'],role=step['role'],native=step['native'])
        # Click/ACK is never accepted as persistence evidence.
        readback=executor.call('read_box',room,box_id=step['box_id'],role=step['role'])
        if readback.get('observed_via')!='reopened_native_editor' or readback.get('settings')!=step['expected']:
            raise ModelError('Readback mismatch; partial changes possible, stop and inspect baseline')
        report['configured'].append(step['box_id'])
        print(json.dumps({'event':'box_readback_verified','box_id':step['box_id'],'room_id':room},ensure_ascii=False),flush=True)
    report['configuration_verified']=True
    return report
