import copy,contextlib,io,unittest
from wired_workbench.native import apply_classic,valid_manifest
from wired_workbench.core import ModelError

def plan():
 return {'protocol':'hgz-classic-editor/1','target':'habbogz','room_id':901,'owner_id':5,'room_state':'hide','private_acceptance_room':True,'items':[{'id':n,'base_id':100+n,'position':[n,1,0]} for n in range(1,7)],'steps':[{'role':r,'box_id':n,'native':{'fixture':'value'},'expected':{'fixture':'value'}} for n,r in enumerate(['repeat','chase','collision','teleport'],1)]}
class Fake:
 def __init__(self,p,mode=None):self.p=p;self.mode=mode;self.calls=[];self.state={n:{} for n in range(1,5)}
 def call(self,action,room,**data):
  self.calls.append(action)
  if action=='inspect_room':return {'room_id':self.p['room_id'],'owner_id':self.p['owner_id'],'room_state':self.p['room_state'],'private_acceptance_room':True,'items':[] if self.mode=='wrong_room' else self.p['items']}
  if action=='configure_box':self.state[data['box_id']]=data['native'];return {'ack':True}
  return {'observed_via':'ack' if self.mode=='ack_only' else 'reopened_native_editor','settings':{} if self.mode=='mismatch' else self.state[data['box_id']]}
class NativeTests(unittest.TestCase):
 def apply(self,p,f):
  with contextlib.redirect_stdout(io.StringIO()):return apply_classic(p,f)
 def test_all_verified_not_gameplay(self):
  p=plan();f=Fake(p);r=self.apply(p,f);self.assertTrue(r['configuration_verified']);self.assertFalse(r['gameplay_verified']);self.assertFalse(r['video_recorded']);self.assertEqual(f.calls[:5],['inspect_room']+['read_box']*4)
 def test_drift_no_writes(self):
  p=plan();f=Fake(p,'wrong_room')
  with self.assertRaises(ModelError):self.apply(p,f)
  self.assertNotIn('configure_box',f.calls)
 def test_ack_not_readback(self):
  p=plan();f=Fake(p,'ack_only')
  with self.assertRaises(ModelError):self.apply(p,f)
  self.assertNotIn('configure_box',f.calls)
 def test_mismatch_stops(self):
  p=plan();f=Fake(p,'mismatch')
  with self.assertRaises(ModelError):self.apply(p,f)
  self.assertEqual(f.calls.count('configure_box'),1)
 def test_other_target(self):
  p=plan();p['target']='habbo.es'
  with self.assertRaises(ModelError):valid_manifest(p)
 def test_non_private(self):
  p=plan();p['private_acceptance_room']=False
  with self.assertRaises(ModelError):valid_manifest(p)
 def test_duplicate_boxes(self):
  p=plan();p['steps'][1]['box_id']=1
  with self.assertRaises(ModelError):valid_manifest(p)
 def test_no_native_parameters(self):
  p=plan();p['steps'][0].pop('native')
  with self.assertRaises(ModelError):valid_manifest(p)
class MobileInventoryTests(unittest.TestCase):
 def setUp(self):
  self.p=plan();self.p['mobile_item_ids']=[5];self.p['steps'][1]['native']={'selected_items':[5]};self.p['steps'][1]['expected']={'selected_items':[5]}
 def test_only_mobile_position_allowed(self):
  from wired_workbench.native import compare_inventory
  observed=copy.deepcopy(self.p['items']);observed[4]['position']=[3.25,6,0]
  self.assertTrue(compare_inventory(valid_manifest(self.p),observed))
 def test_fixed_position_rejected(self):
  from wired_workbench.native import compare_inventory
  observed=copy.deepcopy(self.p['items']);observed[0]['position']=[3,6,0]
  self.assertFalse(compare_inventory(valid_manifest(self.p),observed))
 def test_mobile_base_rejected(self):
  from wired_workbench.native import compare_inventory
  observed=copy.deepcopy(self.p['items']);observed[4]['base_id']=999
  self.assertFalse(compare_inventory(valid_manifest(self.p),observed))
 def test_invalid_mobile_positions_rejected(self):
  from wired_workbench.native import compare_inventory
  for position in [[float('nan'),1,0],['3',1,0],[True,1,0],[1,2]]:
   observed=copy.deepcopy(self.p['items']);observed[4]['position']=position
   self.assertFalse(compare_inventory(valid_manifest(self.p),observed))
 def test_wrong_mobile_target_rejected(self):
  self.p['mobile_item_ids']=[6]
  with self.assertRaises(ModelError):valid_manifest(self.p)
 def test_mobile_box_rejected(self):
  self.p['mobile_item_ids']=[1]
  with self.assertRaises(ModelError):valid_manifest(self.p)
 def test_multiple_mobile_rejected(self):
  self.p['mobile_item_ids']=[5,6]
  with self.assertRaises(ModelError):valid_manifest(self.p)
 def test_duplicate_observed_rejected(self):
  from wired_workbench.native import compare_inventory
  observed=copy.deepcopy(self.p['items']);observed[0]=observed[1]
  self.assertFalse(compare_inventory(valid_manifest(self.p),observed))
 def test_no_mobile_flag_is_strict(self):
  from wired_workbench.native import compare_inventory
  self.p.pop('mobile_item_ids');observed=copy.deepcopy(self.p['items']);observed[4]['position']=[3.25,6,0]
  self.assertFalse(compare_inventory(valid_manifest(self.p),observed))
