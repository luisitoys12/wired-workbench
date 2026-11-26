import unittest,copy,contextlib,io
from wired_workbench.native import apply_classic,valid_manifest
from wired_workbench.core import ModelError
from test_native import plan,Fake
class Drift(Fake):
 def __init__(self,p,key,value,after=2):super().__init__(p);self.key=key;self.value=value;self.after=after;self.inspections=0
 def call(self,action,room,**data):
  out=super().call(action,room,**data)
  if action=='inspect_room':
   self.inspections+=1;out=copy.deepcopy(out)
   if self.inspections>=self.after:out[self.key]=self.value
  return out
class FreshGuardTests(unittest.TestCase):
 def invoke(self,p,f):
  with contextlib.redirect_stdout(io.StringIO()):return apply_classic(p,f)
 def test_owner_drift_zero_writes(self):
  p=plan();f=Drift(p,'owner_id',999)
  with self.assertRaises(ModelError):self.invoke(p,f)
  self.assertNotIn('configure_box',f.calls)
 def test_room_state_drift_zero_writes(self):
  p=plan();f=Drift(p,'room_state','open')
  with self.assertRaises(ModelError):self.invoke(p,f)
  self.assertNotIn('configure_box',f.calls)
 def test_room_id_drift_zero_writes(self):
  p=plan();f=Drift(p,'room_id',902)
  with self.assertRaises(ModelError):self.invoke(p,f)
  self.assertNotIn('configure_box',f.calls)
 def test_late_drift_stops_after_one(self):
  p=plan();f=Drift(p,'owner_id',999,after=3)
  with self.assertRaises(ModelError):self.invoke(p,f)
  self.assertEqual(f.calls.count('configure_box'),1)
 def test_inventory_drift_zero_writes(self):
  p=plan();items=copy.deepcopy(p['items']);items[0]['base_id']+=1;f=Drift(p,'items',items)
  with self.assertRaises(ModelError):self.invoke(p,f)
  self.assertNotIn('configure_box',f.calls)
 def test_every_write_has_fresh_inspection(self):
  p=plan();f=Fake(p);self.invoke(p,f)
  for i,x in enumerate(f.calls):
   if x=='configure_box':self.assertEqual(f.calls[i-1],'inspect_room')
 def test_missing_owner_rejected(self):
  p=plan();p.pop('owner_id')
  with self.assertRaises(ModelError):valid_manifest(p)
 def test_role_items_box_disagrees(self):
  p=plan();p['role_items']={'repeat':2,'chase':1,'collision':3,'teleport':4,'duck':5,'start':6}
  with self.assertRaises(ModelError):valid_manifest(p)
