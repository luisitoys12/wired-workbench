import sys,unittest
from wired_workbench.core import ModelError
from wired_workbench.native import NativeExecutor
class ExecutorTransportTests(unittest.TestCase):
 def invoke(self,code):
  with NativeExecutor([sys.executable,'-c',code],timeout=.1) as executor:
   return executor.call('inspect_room',901)
 def test_timeout(self):
  with self.assertRaisesRegex(ModelError,'timed out'):self.invoke('import time;time.sleep(1)')
 def test_closed(self):
  with self.assertRaisesRegex(ModelError,'closed'):self.invoke('pass')
 def test_wrong_request_id(self):
  with self.assertRaisesRegex(ModelError,'identity mismatch'):
   self.invoke('print(\'{"protocol":"hgz-classic-editor/1","request_id":99,"room_id":901,"ok":true}\',flush=True)')
 def test_invalid_json(self):
  with self.assertRaises(ValueError):self.invoke('print("not-json",flush=True)')
 def test_explicit_rejection(self):
  with self.assertRaisesRegex(ModelError,'rejected'):
   self.invoke('print(\'{"protocol":"hgz-classic-editor/1","request_id":1,"room_id":901,"ok":false}\',flush=True)')
 def test_good_transport(self):
  result=self.invoke('print(\'{"protocol":"hgz-classic-editor/1","request_id":1,"room_id":901,"ok":true}\',flush=True)')
  self.assertTrue(result['ok'])
 def test_cooperative_stop_and_no_cleanup_claim(self):
  code='import sys,json\nfor line in sys.stdin:\n r=json.loads(line);r["ok"]=True;print(json.dumps(r),flush=True)\n if r["action"]=="stop":break\n'
  executor=NativeExecutor([sys.executable,'-c',code],timeout=.2)
  with executor:executor.call('inspect_room',901)
  self.assertEqual(executor.close_status,{'stop_acknowledged':True,'exit_code':0,'ticket_cleanup_verified':False})
