import http.client,json,threading,unittest
from wired_workbench.ui import create_server
class UI(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.s=create_server();cls.t=threading.Thread(target=cls.s.serve_forever);cls.t.start();cls.port=cls.s.server_port
 @classmethod
 def tearDownClass(cls):cls.s.shutdown();cls.s.server_close();cls.t.join()
 def req(self,method,path,body=None,headers=None):
  c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=3);c.request(method,path,body,headers or {});r=c.getresponse();data=r.read();status=r.status;c.close();return status,data
 def headers(self):
  _,data=self.req('GET','/session');return {'Origin':f'http://127.0.0.1:{self.port}','X-Workbench-Token':json.loads(data)['token'],'Content-Type':'application/json'}
 def test_home(self):s,b=self.req('GET','/');self.assertEqual(s,200);self.assertIn(b'WIRED Workbench',b)
 def test_foreign_host(self):self.assertEqual(self.req('GET','/',headers={'Host':'other.example'})[0],403)
 def test_no_token(self):self.assertEqual(self.req('POST','/api/plan','{}')[0],403)
 def test_foreign_origin(self):
  h=self.headers();h['Origin']='https://other.example';self.assertEqual(self.req('POST','/api/plan','{}',h)[0],403)
 def test_plan(self):
  s,b=self.req('POST','/api/plan',json.dumps({'recipe':'switch-lamp','target':'habbo.es'}),self.headers());self.assertEqual(s,200);self.assertEqual(json.loads(b)['target'],'habbo.es')
 def test_bad_json(self):self.assertEqual(self.req('POST','/api/analyze','{',self.headers())[0],400)
 def test_no_path_traversal(self):self.assertEqual(self.req('GET','/../core.py')[0],404)
 def test_limit(self):
  h=self.headers();h['Content-Length']='1048577';self.assertEqual(self.req('POST','/api/analyze',None,h)[0],413)
 def test_invalid_shape(self):
  s,b=self.req('POST','/api/analyze','[]',self.headers());self.assertEqual(s,200);self.assertTrue(json.loads(b)['issues'])
