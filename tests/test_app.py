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
        b['seeking']='woman'; a['max_age']=20; self.assertTrue(eligible(a,b))
    def test_name_and_range_validation(self):
        p=profile(); p['birth_name']='Ada Middle Bello'
        self.assertNotEqual(overview(p)['name_number'],overview(profile())['name_number'])
        p.update(min_age=50,max_age=25)
        self.assertEqual(server.validate(p)['max_age'],25)
        p=profile(); p['birth_name']='中文'; self.assertIsNone(overview(p)['name_number'])
    def test_profile_preferences_do_not_rank(self):
        a,b=profile(),profile(); a['relationship_goal']=b['relationship_goal']='marriage'
        aligned=compatibility(a,b)['score']; b['relationship_goal']='friendship'
        self.assertEqual(compatibility(a,b)['score'],aligned)
    def test_private_number_breakdown_and_public_meanings(self):
        p=profile(); public=overview(p); private=overview(p,private=True)
        self.assertNotIn('breakdown',public)
        self.assertIn('A(1)',private['breakdown']['name_number'])
        self.assertIn('11',private['breakdown']['life_path'])
        self.assertEqual(set(public['meanings']),{'sun_sign','chinese_zodiac','life_path','name_number'})
    def test_four_domains_and_legacy_communication(self):
        a,b=profile(),profile(); b['preferences']['communication']='independent'
        result=compatibility(a,b)
        self.assertEqual(set(result['domains']),{'Love','Living','Money','Communication'})
        self.assertEqual(result['domains']['Communication']['score'],50)
        self.assertEqual(result['domains']['Love']['score'],90)
        a['preferences']['communication']='independent'
        self.assertEqual(compatibility(a,b)['domains']['Communication']['score'],90)
        self.assertIn('communication',server.validate(a)['preferences'])
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
    def setUp(self):
        with server.connect() as db:
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall(): db.execute('DELETE FROM '+row[0])
    def client(self): return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(self,c,path,data=None,headers=None):
        r=urllib.request.Request(self.url+'/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json',**(headers or {})})
        try:
            with c.open(r) as response: return response.status,json.load(response)
        except urllib.error.HTTPError as e: return e.code,json.load(e)
    def make_match(self,a,b):
        uid=self.call(b,'me')[1]['id']
        self.assertEqual(self.call(a,'likes',{'recipient':uid})[0],200)
        incoming=self.call(b,'likes')[1]['likes']
        self.assertEqual(len(incoming),1)
        status,result=self.call(b,'likes/'+str(incoming[0]['id'])+'/accept',{})
        self.assertEqual(status,200)
        return result['connection_id']
    def end_match(self,a):
        rows=self.call(a,'conversations')[1]['conversations']
        for row in rows: self.call(a,'conversations/'+str(row['id'])+'/unmatch',{})
    def test_full_account_and_privacy_flow(self):
        a,b=self.client(),self.client()
        self.assertEqual(self.call(a,'me')[0],401)
        for c,email in [(a,'ada@example.com'),(b,'bea@example.com')]:
            self.assertEqual(self.call(c,'register',dict(email=email,password='strong password 123',adult=True))[0],200)
            self.assertEqual(self.call(c,'profile',profile())[0],200)
        self.make_match(a,b)
        status,result=self.call(a,'matches'); self.assertEqual(status,200); self.assertEqual(len(result['matches']),1)
        public=json.dumps(result); self.assertNotIn('birth_date',public); self.assertNotIn('answers',public); self.assertNotIn('Bello',public); self.assertNotIn('@example',public)
        p=profile(); p['discoverable']=False; self.call(b,'profile',p)
        self.end_match(a)
        self.assertEqual(self.call(a,'matches')[1]['matches'],[])
        self.assertEqual(self.call(a,'profile',p,{'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.call(a,'delete',{})[0],200); self.assertEqual(self.call(a,'me')[0],401)
        self.call(b,'logout',{}); self.assertEqual(self.call(b,'me')[0],401)
        self.assertEqual(self.call(b,'login',{'email':'bea@example.com','password':'wrong password 123'})[0],401)
        self.assertEqual(self.call(b,'login',{'email':'bea@example.com','password':'strong password 123'})[0],200)
    def test_uploaded_photo_attaches_and_primary_order_persists(self):
        import base64
        a,b=self.client(),self.client()
        for c,email in [(a,'upload-a@example.com'),(b,'upload-b@example.com')]:
            self.call(c,'register',dict(email=email,password='strong password 123',adult=True))
            self.call(c,'profile',profile())
        image=base64.b64encode(bytes.fromhex('ffd8ffc00008080010001003ffd9')).decode()
        first=self.call(a,'photos',{'image':image})[1]
        second=self.call(a,'photos',{'image':image})[1]
        self.assertTrue(first['attached'])
        self.assertEqual(self.call(a,'me')[1]['profile']['photos'],[first['id'],second['id']])
        self.assertEqual(self.call(b,'photos/order',{'photos':[first['id']]})[0],400)
        self.assertEqual(self.call(a,'photos/order',{'photos':[second['id'],first['id']]})[0],200)
        self.assertEqual(self.call(a,'me')[1]['profile']['photos'][0],second['id'])
        self.assertEqual(self.call(a,'photos/order',{'photos':[first['id']]})[0],400)

    def test_photo_ownership_visibility_and_deletion(self):
        # Bounded JPEG frame fixture tests storage/authorization; image decode is a browser responsibility.
        import base64
        image=bytes.fromhex('ffd8ffc00008080010001003ffd9')
        encoded=base64.b64encode(image).decode()
        a,b,outsider=self.client(),self.client(),self.client()
        for c,email in [(a,'photos-a@example.com'),(b,'photos-b@example.com'),(outsider,'photos-c@example.com')]:
            self.assertEqual(self.call(c,'register',dict(email=email,password='strong password 123',adult=True))[0],200)
        self.assertEqual(self.call(a,'photos',{'image':'invalid'})[0],400)
        code,r=self.call(a,'photos',{'image':encoded}); self.assertEqual(code,200); ident=r['id']
        pa=profile(); pa['photos']=[ident]
        self.assertEqual(self.call(a,'profile',pa)[0],200)
        self.assertEqual(self.call(b,'profile',pa)[0],400)
        self.call(b,'profile',profile())
        self.make_match(a,b)
        with b.open(self.url+'/api/photos/'+ident) as response: self.assertEqual(response.read(),image)
        with self.assertRaises(urllib.error.HTTPError): outsider.open(self.url+'/api/photos/'+ident)
        with self.assertRaises(urllib.error.HTTPError): self.client().open(self.url+'/api/photos/'+ident)
        public=self.call(b,'matches')[1]
        self.assertNotIn('breakdown',json.dumps(public)); self.assertIn('domains',public['matches'][0]['compatibility'])
        pa['discoverable']=False; self.call(a,'profile',pa)
        self.end_match(a)
        with self.assertRaises(urllib.error.HTTPError): b.open(self.url+'/api/photos/'+ident)
        self.assertEqual(self.call(b,'matches')[1]['matches'],[])
        self.call(a,'photos/delete',{'id':ident})
        with self.assertRaises(urllib.error.HTTPError): a.open(self.url+'/api/photos/'+ident)
        self.assertEqual(self.call(a,'me')[1]['profile']['photos'],[])
        for i in range(6): self.assertEqual(self.call(a,'photos',{'image':encoded})[0],200)
        self.assertEqual(self.call(a,'photos',{'image':encoded})[0],400)
        ids=self.call(a,'me')[1]['uploaded_photos']; self.assertEqual(len(ids),6)
        self.call(a,'delete',{})
        with server.connect() as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM photos WHERE id=?',(ids[0],)).fetchone()[0],0)
    def test_symbol_pages_and_match_authorization(self):
        a,b=self.client(),self.client()
        for c,email in [(a,'symbols-a@example.com'),(b,'symbols-b@example.com')]:
            self.call(c,'register',dict(email=email,password='strong password 123',adult=True))
            self.call(c,'profile',profile())
        self.make_match(a,b)
        with a.open(self.url+'/symbols/me/life_path') as r: self.assertIn(b'/symbol.js',r.read())
        self.assertEqual(self.call(self.client(),'symbols/me/life_path')[0],401)
        own=self.call(a,'symbols/me/name_number')[1]['detail']
        self.assertIn('B(2)',own['calculation'])
        matches=self.call(a,'matches')[1]['matches']
        ident=next(m['id'] for m in matches if m['name']=='Ada' and m['overview']['life_path']==11)
        for kind in ['sun_sign','chinese_zodiac','life_path','name_number']:
            code,result=self.call(a,f'symbols/{ident}/{kind}'); self.assertEqual(code,200)
            d=result['detail']; self.assertIsNone(d['calculation'])
            for field in ['personality','strengths','growth','relationships','method','matching','perspective']: self.assertTrue(d[field])
            self.assertNotIn('Bello',json.dumps(result)); self.assertNotIn('1990-04-15',json.dumps(result))
        # Identify the exact second account regardless of other test fixtures.
        with server.connect() as db: ident=db.execute('SELECT id FROM users WHERE email=?',('symbols-b@example.com',)).fetchone()[0]
        p=profile(); p['discoverable']=False; self.call(b,'profile',p)
        self.end_match(a)
        self.assertEqual(self.call(a,f'symbols/{ident}/life_path')[0],404)
        p['discoverable']=True; p.update(gender='man',seeking='woman'); self.call(b,'profile',p)
        self.assertEqual(self.call(a,f'symbols/{ident}/life_path')[0],404)
        self.assertEqual(self.call(a,'symbols/me/unknown')[0],404)
    def test_every_symbol_has_personality_content(self):
        from symbol_details import symbol_detail
        for year in range(1980,1992):
            for month in range(1,13):
                p=profile(); p['birth_date']=f'{year}-{month:02d}-15'
                for key in ['sun_sign','chinese_zodiac','life_path','name_number']:
                    detail=symbol_detail(p,key)
                    self.assertTrue(detail['personality']); self.assertIsNone(detail['calculation'])
    def test_personal_only_numbers_and_matched_only_comparisons(self):
        a,b=self.client(),self.client()
        for c,email in [(a,'tools-a@example.com'),(b,'tools-b@example.com')]:
            self.assertEqual(self.call(c,'register',dict(email=email,password='strong password 123',adult=True,birth_date='1990-04-15',race='Black / African descent',languages='English, Yoruba',religion='Christian'))[0],200)
            initial=self.call(c,'me')[1]['onboarding']; self.assertEqual(initial['languages'],'English, Yoruba')
            p=profile(); p.update(race='Black / African descent',religion='Christian',languages='English, Yoruba')
            self.call(c,'profile',p)
        for path,data in [('numerology/calculate',{'name':'John'}),('numerology/compatibility',{'first':1,'second':2}),('numerology/angel',{'sequence':'111'}),('astrology/compatibility',{'first':'Aries','second':'Leo'})]:
            self.assertEqual(self.call(a,path,data)[0],404)
        self.make_match(a,b)
        own=self.call(a,'numerology/me')[1]['overview']
        self.assertEqual(own['master_numbers'],[11]); self.assertNotIn('core',own)
        with server.connect() as db: ident=db.execute('SELECT id FROM users WHERE email=?',('tools-b@example.com',)).fetchone()[0]
        code,result=self.call(a,f'compatibility/{ident}'); self.assertEqual(code,200)
        self.assertEqual(set(result['report']['methods']),{'zodiac','numerology','life_path','chinese_zodiac'})
        for text in ['birth_date','Bello','1990-04-15','"answers"']: self.assertNotIn(text,json.dumps(result))
        matches=self.call(a,'matches')[1]; self.assertEqual(matches['matches'][0]['profile_details']['languages'],'English, Yoruba')
        self.assertEqual(self.call(a,'match-preference',{'method':'life_path'})[0],200)
        self.assertEqual(self.call(a,'matches')[1]['preferred_match'],'life_path')
        self.assertEqual(self.call(a,'match-preference',{'method':'religion'})[0],400)
        p['discoverable']=False; self.call(b,'profile',p)
        self.end_match(a)
        self.assertEqual(self.call(a,f'compatibility/{ident}')[0],404)
        with a.open(self.url+'/tools') as r:
            html=r.read(); self.assertNotIn(b'chart-form',html); self.assertNotIn(b'pair-directory',html)
    def test_demographics_do_not_affect_symbolic_scores(self):
        a,b=profile(),profile(); before=compatibility(a,b)
        b.update(age=70,race='Other',languages='French',religion='Other',min_age=100,max_age=100)
        self.assertEqual(before,compatibility(a,b)); self.assertTrue(eligible(a,b))
    def test_matched_bio_translation_and_access_control(self):
        from unittest.mock import patch
        import translation
        a,b=self.client(),self.client()
        for c,email in [(a,'translate-a@example.com'),(b,'translate-b@example.com')]:
            self.call(c,'register',dict(email=email,password='strong password 123',adult=True)); self.call(c,'profile',profile())
        with server.connect() as db: ident=db.execute('SELECT id FROM users WHERE email=?',('translate-b@example.com',)).fetchone()[0]
        self.make_match(a,b)
        calls=[]
        def provider(path,payload=None):
            calls.append((path,payload))
            if path=='/languages': return [{'code':'en','name':'English'},{'code':'fr','name':'French'}]
            self.assertEqual(payload['q'],profile()['bio']); self.assertEqual(payload['target'],'fr')
            return {'translatedText':'Des conversations importantes.'}
        with patch.object(translation,'provider',side_effect=provider):
            self.assertTrue(self.call(a,'translation/languages')[1]['available'])
            code,result=self.call(a,f'matches/{ident}/translate',{'target':'fr'}); self.assertEqual(code,200); self.assertIn('conversations',result['text'])
            self.assertEqual(self.call(a,f'matches/{ident}/translate',{'target':'xx'})[0],400)
            p=profile(); p['discoverable']=False; self.call(b,'profile',p); self.end_match(a); calls.clear()
            self.assertEqual(self.call(a,f'matches/{ident}/translate',{'target':'fr'})[0],404); self.assertEqual(calls,[])
        with patch.object(translation,'provider',side_effect=OSError('offline')):
            self.assertFalse(self.call(a,'translation/languages')[1]['available'])
    def test_signup_rejects_underage_birth_date(self):
        code,result=self.call(self.client(),'register',dict(email='minor@example.com',password='strong password 123',adult=True,birth_date=date.today().isoformat()))
        self.assertEqual(code,400)
    def test_static_and_no_path_traversal(self):
        c=self.client()
        with c.open(self.url+'/') as response: self.assertIn(b'Be yourself',response.read())
        with self.assertRaises(urllib.error.HTTPError): c.open(self.url+'/../server.py')
