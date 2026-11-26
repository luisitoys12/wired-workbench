import copy,json,tempfile,unittest
from pathlib import Path
from wired_workbench.core import *
from wired_workbench.layout import *
from wired_workbench.__main__ import main
class Core(unittest.TestCase):
 def setUp(self):self.room=plan('switch-lamp','habbogz',guard=True)
 def test_plan(self):self.assertEqual(validate(self.room),[])
 def test_both_targets(self):
  for t in LABELS:self.assertEqual(validate(plan('pressure-gate',t)),[])
 def test_explanation(self):self.assertEqual(len(explain(self.room)['explanation']),1)
 def test_simulate_guard(self):
  r=simulate(self.room,[{'kind':'trigger.use','object':'control'}]*2);self.assertEqual(r['states']['output'],1);self.assertEqual([x['conditionsPassed']for x in r['trace']],[True,False])
 def test_wrong_event(self):self.assertEqual(simulate(self.room,[{'kind':'trigger.step','object':'control'}])['trace'],[])
 def test_keyword(self):
  r=plan('keyword-message','habbo.es');self.assertEqual(simulate(r,[{'kind':'trigger.keyword','text':'hola'}])['messages'],['Bienvenido'])
 def test_wrong_keyword_kind(self):
  r=plan('keyword-message','habbo.es');r['furniture']=[{'id':'control','name':'a','states':2,'state':0}];self.assertEqual(simulate(r,[{'kind':'trigger.use','object':'control'}])['messages'],[])
 def test_unsupported(self):self.room['stacks'][0]['trigger']['kind']='native-unknown';self.assertTrue(validate(self.room))
 def test_foreign(self):self.room['stacks'][0]['effects'][0]['object']='foreign';self.assertTrue(validate(self.room))
 def test_boolean_not_state(self):self.room['furniture'][0]['state']=True;self.assertTrue(validate(self.room))
 def test_duplicate(self):self.room['furniture']*=2;self.assertTrue(validate(self.room))
 def test_extra(self):self.room['token']='not-accepted';self.assertTrue(validate(self.room))
 def test_invalid_shapes(self):
  for x in [None,[],{}, {'schema':SCHEMA,'furniture':[None],'stacks':[None]}]:self.assertTrue(validate(x))
 def test_nested_fields(self):
  for val in [None,[],{},True]:
   r=copy.deepcopy(self.room);r['stacks'][0]['effects'][0]['params']=val;self.assertTrue(validate(r))
 def test_wrong_role(self):self.room['stacks'][0]['trigger']={'kind':'effect.message','params':{'text':'hi'}};self.assertTrue(validate(self.room))
 def test_invalid_initial(self):self.room['furniture'][0]['state']=3;self.assertTrue(validate(self.room))
 def test_idempotent_no_mutation(self):
  before=copy.deepcopy(self.room);simulate(self.room,[{'kind':'trigger.use','object':'control'}]);self.assertEqual(before,self.room)
 def test_event_bounds(self):
  with self.assertRaises(ModelError):simulate(self.room,[{}]*257)
 def test_bad_event(self):
  for x in [{},[],{'kind':'trigger.use','object':'foreign'}]:
   with self.assertRaises(ModelError):simulate(self.room,[x])
 def test_parser_rejects_duplicate(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'x';p.write_text('{"x":1,"x":2}')
   with self.assertRaises(ModelError):load_file(p)
 def test_parser_rejects_large(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'x';p.write_bytes(b' '* (MAX_BYTES+1))
   with self.assertRaises(ModelError):load_file(p)
 def test_no_native_claim(self):self.assertFalse(explain(self.room)['canApply'])
class Layout(unittest.TestCase):
 def setUp(self):self.data={'schema':'wired-layout/1','target':'habbo.es','width':8,'height':6,'inventory':[{'id':'A','name':'Block','width':2,'depth':1,'height':1},{'id':'B','name':'Block','width':2,'depth':1,'height':1}],'placements':[{'id':'A','x':1,'y':1,'z':0,'rotation':0},{'id':'B','x':3,'y':1,'z':0,'rotation':0}]}
 def test_valid(self):self.assertEqual(validate_layout(self.data),[])
 def test_overlap(self):self.data['placements'][1]['x']=2;self.assertTrue(validate_layout(self.data))
 def test_outside(self):self.data['placements'][0]['x']=8;self.assertTrue(validate_layout(self.data))
 def test_inventory_limit(self):self.data['placements'][0]['id']='new';self.assertTrue(validate_layout(self.data))
 def test_stack_is_not_physics(self):self.data['placements'][1].update(x=1,z=1);self.assertEqual(validate_layout(self.data),[]);self.assertFalse(layout_report(self.data)['canApply'])
 def test_duplicate(self):self.data['placements']*=2;self.assertTrue(validate_layout(self.data))
 def test_escape_svg(self):self.data['inventory'][0]['id']='<script>';self.data['placements'][0]['id']='<script>';s=svg_preview(self.data);self.assertNotIn('<script>',s);self.assertIn('&lt;script&gt;',s)
 def test_rotation(self):self.data['placements'][0]['rotation']=45;self.assertTrue(validate_layout(self.data))
if __name__=='__main__':unittest.main()

class Defensive(unittest.TestCase):
 def test_mutated_shapes_do_not_crash_validator(self):
  samples=[None,True,0,[],{},'x']
  baseline=plan('switch-lamp','habbogz')
  for key in baseline:
   for v in samples:
    r=copy.deepcopy(baseline);r[key]=v
    with self.subTest(key=key,value=v):self.assertIsInstance(validate(r),list)
 def test_import_has_no_network_modules(self):
  import ast
  root=Path(__file__).parent.parent/'wired_workbench'
  for path in root.glob('*.py'):
   if path.name=='ui.py':continue
   tree=ast.parse(path.read_text())
   for n in ast.walk(tree):
    if isinstance(n,ast.Import):self.assertTrue(all(a.name.split('.')[0]not in ({'socket','requests','urllib'} if path.name=='native.py' else {'socket','requests','urllib','subprocess'})for a in n.names))
 def test_nonfinite(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'x';p.write_text('{"x":NaN}')
   with self.assertRaises(ModelError):load_file(p)
 def test_no_native_operation(self):
  for t in LABELS:
   self.assertFalse(explain(plan('switch-lamp',t))['canApply'])
