import json, os, tempfile, threading, unittest, urllib.request, urllib.error, http.cookiejar
from datetime import date
import server
from matching import overview, compatibility, eligible

def profile():
    return dict(first_name='Ada',last_name='Bello',birth_date='1990-04-15',birth_time='10:00',birth_location='Lagos',bio='I like meaningful conversations.',discoverable=True,preferences={k:'similar' for k in server.CATEGORIES},answers={k:{'choice':'My reflection','words':['calm','open','curious']} for k in ['animal','color','paradise','box']})
class MatchingTests(unittest.TestCase):
    def test_overview(self):
        o=overview(profile()); self.assertEqual(o['sun_sign'],'Aries'); self.assertEqual(o['chinese_zodiac'],'Horse'); self.assertEqual(o['life_path'],11)
    def test_boundaries(self):
        p=profile(); p['birth_date']='1990-12-22'; self.assertEqual(overview(p)['sun_sign'],'Capricorn')
        p['birth_date']='1990-01-19'; self.assertEqual(overview(p)['sun_sign'],'Capricorn')
        p['birth_date']='1990-01-20'; self.assertEqual(overview(p)['sun_sign'],'Aquarius')
    def test_reflections_do_not_rank(self):
        a,b=profile(),profile(); original=compatibility(a,b); b['answers']['animal']['choice']='Anything'; self.assertEqual(original,compatibility(a,b))
    def test_mutual_preferences(self):
        a,b=profile(),profile()
        a.update(gender='woman',seeking='man',min_age=18,max_age=120)
        b.update(gender='man',seeking='woman',min_age=18,max_age=120)
        self.assertTrue(eligible(a,b))
        b['seeking']='man'; self.assertFalse(eligible(a,b))
        b['seeking']='woman'; a['max_age']=20; self.assertFalse(eligible(a,b))
    def test_name_and_range_validation(self):
        p=profile(); p['birth_name']='Ada Middle Bello'
        self.assertNotEqual(overview(p)['name_number'],overview(profile())['name_number'])
        p.update(min_age=50,max_age=25)
        with self.assertRaises(ValueError): server.validate(p)
        p=profile(); p['birth_name']='中文'; self.assertIsNone(overview(p)['name_number'])
    def test_goals_affect_alignment(self):
        a,b=profile(),profile(); a['relationship_goal']=b['relationship_goal']='marriage'
        aligned=compatibility(a,b)['score']; b['relationship_goal']='friendship'
        self.assertLess(compatibility(a,b)['score'],aligned)
    def test_underage_rejected(self):
        p=profile(); p['birth_date']=date.today().isoformat()
        with self.assertRaises(ValueError): server.validate(p)
class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(); server.DB=os.path.join(cls.temp.name,'test.db')
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.url='http://127.0.0.1:'+str(cls.http.server_port)
        threading.Thread(target=cls.http.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls): cls.http.shutdown(); cls.http.server_close(); cls.temp.cleanup()
    def client(self): return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(self,c,path,data=None,headers=None):
        r=urllib.request.Request(self.url+'/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json',**(headers or {})})
        try:
            with c.open(r) as response: return response.status,json.load(response)
        except urllib.error.HTTPError as e: return e.code,json.load(e)
    def test_full_account_and_privacy_flow(self):
        a,b=self.client(),self.client()
        self.assertEqual(self.call(a,'me')[0],401)
        for c,email in [(a,'ada@example.com'),(b,'bea@example.com')]:
            self.assertEqual(self.call(c,'register',dict(email=email,password='strong password 123',adult=True))[0],200)
            self.assertEqual(self.call(c,'profile',profile())[0],200)
        status,result=self.call(a,'matches'); self.assertEqual(status,200); self.assertEqual(len(result['matches']),1)
        public=json.dumps(result); self.assertNotIn('birth_date',public); self.assertNotIn('answers',public); self.assertNotIn('Bello',public); self.assertNotIn('@example',public)
        p=profile(); p['discoverable']=False; self.call(b,'profile',p)
        self.assertEqual(self.call(a,'matches')[1]['matches'],[])
        self.assertEqual(self.call(a,'profile',p,{'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.call(a,'delete',{})[0],200); self.assertEqual(self.call(a,'me')[0],401)
        self.call(b,'logout',{}); self.assertEqual(self.call(b,'me')[0],401)
        self.assertEqual(self.call(b,'login',{'email':'bea@example.com','password':'wrong password 123'})[0],401)
        self.assertEqual(self.call(b,'login',{'email':'bea@example.com','password':'strong password 123'})[0],200)
    def test_static_and_no_path_traversal(self):
        c=self.client()
        with c.open(self.url+'/') as response: self.assertIn(b'Be yourself',response.read())
        with self.assertRaises(urllib.error.HTTPError): c.open(self.url+'/../server.py')
