import unittest, json, base64, os
import test_app as app_tests
profile=app_tests.profile
import server

class SocialTests(unittest.TestCase):
    setUpClass=classmethod(app_tests.APITests.setUpClass.__func__)
    tearDownClass=classmethod(app_tests.APITests.tearDownClass.__func__)
    setUp=app_tests.APITests.setUp
    client=app_tests.APITests.client
    call=app_tests.APITests.call
    make_match=app_tests.APITests.make_match
    end_match=app_tests.APITests.end_match
    def accounts(self,count=2):
        result=[]
        for i in range(count):
            c=self.client(); self.assertEqual(self.call(c,'register',{'email':f'social{i}@example.com','password':'strong password 123','adult':True})[0],200)
            p=profile();p.update(first_name=f'Member{i}',public_prompts=[{'question':'Ask me about…','answer':'Travel and books'}],visible_details=['languages'],languages='English',religion='Private belief')
            self.assertEqual(self.call(c,'profile',p)[0],200);result.append((c,self.call(c,'me')[1]['id']))
        return result
    def test_notification_badges_isolated_and_cursor_safe(self):
        import social
        (a,aid),(b,bid)=self.accounts()
        with server.connect() as c:
            social.notify(c,aid,'Someone liked your profile.')
            social.notify(c,aid,'Someone sent you a Rose.')
            social.notify(c,aid,'You have a new message.')
            social.notify(c,aid,'You have a new match.')
        first=self.call(a,'notifications/summary')[1]
        self.assertEqual(first['counts'],{'likes':2,'messages':1,'matches':1})
        self.assertEqual(self.call(b,'notifications/summary')[1]['counts'],{'likes':0,'messages':0,'matches':0})
        with server.connect() as c:social.notify(c,aid,'Someone liked your profile.')
        self.assertEqual(self.call(a,'notifications/read',{'category':'likes','through_id':first['through_id']})[0],200)
        self.assertEqual(self.call(a,'notifications/summary')[1]['counts'],{'likes':1,'messages':1,'matches':1})
        self.assertEqual(self.call(a,'notifications/read',{'category':'invalid','through_id':0})[0],400)
        self.call(a,'notifications/read',{})
        self.assertEqual(self.call(a,'notifications/summary')[1]['counts'],{'likes':0,'messages':0,'matches':0})

    def test_password_change_revokes_all_sessions(self):
        (a,aid),(b,bid)=self.accounts()
        second=self.client()
        self.assertEqual(self.call(second,'login',{'email':'social0@example.com','password':'strong password 123'})[0],200)
        endpoint='account/password'
        self.assertEqual(self.call(a,endpoint,{'current_password':'wrong','new_password':'replacement password 123'})[0],403)
        self.assertEqual(self.call(a,endpoint,{'current_password':'strong password 123','new_password':'short'})[0],400)
        self.assertEqual(self.call(a,endpoint,{'current_password':'strong password 123','new_password':'replacement password 123'})[0],200)
        self.assertEqual(self.call(a,'me')[0],401)
        self.assertEqual(self.call(second,'me')[0],401)
        self.assertEqual(self.call(b,'me')[0],200)
        self.assertEqual(self.call(second,'login',{'email':'social0@example.com','password':'strong password 123'})[0],401)
        self.assertEqual(self.call(second,'login',{'email':'social0@example.com','password':'replacement password 123'})[0],200)

    def test_mutual_percentage_location_language_filters(self):
        (a,aid),(b,bid)=self.accounts()
        p=self.call(a,'me')[1]['profile'];p.update(match_min_percent=100,match_max_percent=100)
        self.assertEqual(self.call(a,'profile',p)[0],200)
        self.assertEqual(self.call(b,'discover')[1]['profiles'],[])
        self.assertEqual(self.call(b,'likes',{'recipient':aid})[0],404)
        p.update(match_min_percent=0,desired_locations='Lagos',preferred_languages='Yoruba')
        self.call(a,'profile',p)
        q=self.call(b,'me')[1]['profile'];q.update(current_location='Lagos',languages='English, Yoruba')
        self.call(b,'profile',q)
        self.assertEqual(len(self.call(a,'discover')[1]['profiles']),1)
        self.call(b,'likes',{'recipient':aid})
        p['desired_locations']='Dallas';self.call(a,'profile',p)
        with server.connect() as c:interest=c.execute('SELECT id FROM interests WHERE recipient=?',(aid,)).fetchone()[0]
        self.assertEqual(self.call(a,f'likes/{interest}/accept',{})[0],404)
        p.update(match_min_percent=101);self.assertEqual(self.call(a,'profile',p)[0],400)

    def test_gallery_only_after_mutual_match(self):
        (a,aid),(b,bid)=self.accounts()
        p=self.call(b,'me')[1]['profile'];p['photos']=['primary-test','gallery-test']
        with server.connect() as c:
            c.executemany('INSERT INTO photos VALUES(?,?,?)',[(x,bid,b'test-image') for x in p['photos']])
        self.assertEqual(self.call(b,'profile',p)[0],200)
        self.assertEqual(self.call(a,'discover')[1]['profiles'][0]['photos'],['primary-test'])
        self.assertEqual(self.call(a,'photos/gallery-test')[0],404)
        self.assertEqual(self.call(a,'likes',{'recipient':bid,'kind':'photo','target':'gallery-test'})[0],400)
        self.call(a,'likes',{'recipient':bid});self.call(b,'likes',{'recipient':aid})
        self.assertEqual(self.call(a,'matches')[1]['matches'][0]['public_profile']['photos'],p['photos'])
        cid=self.call(a,'matches')[1]['matches'][0]['connection_id']
        self.call(a,f'conversations/{cid}/unmatch',{})
        self.assertEqual(self.call(a,'photos/gallery-test')[0],404)

    def test_dating_rooms_consent_safety_and_moderation(self):
        (a,aid),(b,bid),(outsider,oid)=self.accounts(3)
        route='dating/rooms/dating/'
        self.assertEqual(self.call(a,route+'messages')[0],403)
        self.assertEqual(self.call(a,route+'join',{})[0],400)
        for client in (a,b):self.assertEqual(self.call(client,route+'join',{'consent':True})[0],200)
        self.assertEqual(self.call(a,route+'messages',{'text':'Coffee meetup ideas?'})[0],200)
        msg=self.call(b,route+'messages')[1]['messages'][0]
        self.assertNotIn('photos',msg);self.assertNotIn('compatibility',msg)
        self.assertEqual(self.call(outsider,route+'messages')[0],403)
        self.assertEqual(self.call(b,route+'delete',{'message_id':msg['id']})[0],403)
        self.assertEqual(self.call(b,route+'report',{'message_id':msg['id'],'reason':'Review this'})[0],200)
        self.call(b,'block',{'recipient':aid})
        self.assertEqual(self.call(b,route+'messages')[1]['messages'],[])
        self.assertEqual(self.call(a,route+'delete',{'message_id':msg['id']})[0],200)
        self.call(a,route+'leave',{})
        self.assertEqual(self.call(a,route+'messages')[0],403)

    def test_meetup_requires_match_and_invitee_consent(self):
        from datetime import datetime,timezone,timedelta
        (a,aid),(b,bid),(outsider,oid)=self.accounts(3)
        proposal={'connection_id':999,'place':'Public café','location':'Dallas','scheduled':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'note':'Daytime, budget $20'}
        self.assertEqual(self.call(a,'dating/meetups',proposal)[0],404)
        self.call(a,'likes',{'recipient':bid});cid=self.call(b,'likes',{'recipient':aid})[1]['connection_id']
        proposal['connection_id']=cid
        self.assertEqual(self.call(a,'dating/meetups',proposal)[0],200)
        meetup=self.call(b,'dating/meetups')[1]['proposals'][0]['id']
        self.assertEqual(self.call(a,f'dating/meetups/{meetup}/accept',{})[0],403)
        self.assertEqual(self.call(outsider,f'dating/meetups/{meetup}/accept',{})[0],404)
        self.assertEqual(self.call(b,f'dating/meetups/{meetup}/accept',{})[0],200)
        self.assertEqual(self.call(b,f'dating/meetups/{meetup}/decline',{})[0],409)
        self.call(a,f'conversations/{cid}/unmatch',{})
        self.assertEqual(self.call(b,'dating/meetups')[1]['proposals'],[])
        self.assertEqual(self.call(b,f'dating/meetups/{meetup}/accept',{})[0],404)

    def test_explicit_matching_and_revocation(self):
        (a,aid),(b,bid)=self.accounts()
        suggestions=self.call(a,'discover')[1]['profiles']; self.assertEqual(len(suggestions),1)
        self.assertNotIn('overview',suggestions[0]);self.assertNotIn('compatibility',suggestions[0]);self.assertNotIn('religion',suggestions[0]['details'])
        self.assertEqual(self.call(a,'matches')[1]['matches'],[])
        self.assertEqual(self.call(a,f'compatibility/{bid}')[0],404)
        self.assertEqual(self.call(a,'likes',{'recipient':bid,'kind':'prompt','target':'0','comment':'I like books too'})[0],200)
        self.assertEqual(self.call(a,'matches')[1]['matches'],[])
        incoming=self.call(b,'likes')[1]['likes']; self.assertEqual(incoming[0]['comment'],'I like books too')
        r=self.call(b,f"likes/{incoming[0]['id']}/accept",{'message':'Hello there'})[1]; cid=r['connection_id']
        self.assertEqual(len(self.call(a,'matches')[1]['matches']),1)
        self.assertEqual(self.call(a,f'compatibility/{bid}')[0],200)
        self.assertEqual(self.call(a,f'conversations/{cid}/messages')[1]['messages'][0]['text'],'Hello there')
        self.call(a,'settings',{'paused':True})
        self.assertEqual(self.call(a,'discover')[1]['profiles'],[])
        self.assertEqual(self.call(a,f'compatibility/{bid}')[0],200)
        self.assertEqual(self.call(a,f'conversations/{cid}/messages',{'text':'Nice to meet you'})[0],200)
        self.assertTrue(self.call(b,'conversations')[1]['conversations'][0]['your_turn'])
        self.call(a,f'conversations/{cid}/unmatch',{})
        self.assertEqual(self.call(a,f'compatibility/{bid}')[0],404)
        self.assertEqual(self.call(a,f'conversations/{cid}/messages')[0],404)
        self.assertEqual(self.call(a,f'conversations/{cid}/messages',{'text':'No'})[0],404)
        self.assertEqual(self.call(a,'report',{'recipient':bid,'reason':'Unwanted behavior'})[0],200)
        self.assertEqual(self.call(a,'past-connections')[1]['profiles'][0]['id'],bid)
    def test_reciprocal_interests_and_blocking(self):
        (a,aid),(b,bid),(third,tid)=self.accounts(3)
        self.call(a,'likes',{'recipient':bid}); r=self.call(b,'likes',{'recipient':aid})[1]
        self.assertTrue(r['matched']);cid=r['connection_id']
        self.assertEqual(self.call(third,f'conversations/{cid}/messages')[0],404)
        self.call(a,'block',{'recipient':bid})
        self.assertEqual(self.call(b,'matches')[1]['matches'],[])
        self.assertEqual(self.call(b,f'symbols/{aid}/life_path')[0],404)
        self.assertEqual(self.call(b,'likes',{'recipient':aid})[0],404)
        self.assertNotIn(aid,[x['id'] for x in self.call(b,'discover')[1]['profiles']])
    def test_skips_limits_and_decline(self):
        (a,aid),(b,bid)=self.accounts()
        self.call(a,'discover/skip',{'recipient':bid});self.assertEqual(self.call(a,'discover')[1]['profiles'],[])
        self.assertEqual(self.call(a,'discover/undo',{})[0],200)
        self.call(a,'discover/skip',{'recipient':bid});self.assertEqual(self.call(a,'discover/undo',{})[0],429)
        self.assertEqual(self.call(b,'likes',{'recipient':aid,'strength':'rose'})[0],200)
        interest=self.call(a,'likes')[1]['likes'][0]['id'];self.call(a,f'likes/{interest}/decline',{})
        self.assertEqual(self.call(a,'matches')[1]['matches'],[])
        self.assertEqual(self.call(b,'likes',{'recipient':aid,'strength':'rose'})[0],429)
    def test_media_notes_prompts_poll_and_takes(self):
        (a,aid),(b,bid)=self.accounts()
        media={'type':'audio/webm','data':base64.b64encode(bytes.fromhex('1a45dfa3')+b'voice-test').decode()}
        code,result=self.call(a,'media',media);self.assertEqual(code,200);mid=result['id']
        self.assertEqual(self.call(a,'media',{'type':'text/html','data':media['data']})[0],400)
        cid=self.make_match(a,b)
        self.assertEqual(self.call(a,f'conversations/{cid}/messages',{'media_id':mid})[0],200)
        with b.open(self.url+'/api/media/'+mid) as r:self.assertEqual(r.headers['Content-Type'],'audio/webm')
        self.assertEqual(self.call(a,f'conversations/{cid}/note',{'note':'Private reminder'})[0],200)
        self.assertNotIn('Private reminder',json.dumps(self.call(b,'conversations')[1]))
        self.call(a,'thought',{'text':'A lovely day'});self.call(a,'settings',{'paused':False})
        invite=self.call(a,'friend-takes/invite',{})[1]['path']
        self.assertEqual(self.call(self.client(),'public'+invite,{'contributor':'A friend','text':'Kind and thoughtful'})[0],200)
        takes=self.call(a,'friend-takes')[1]['takes'];self.assertEqual(takes[0]['status'],'pending')
        self.call(a,'friend-takes/review',{'id':takes[0]['id'],'action':'visible'})
        self.assertEqual(self.call(b,'friend-takes/review',{'id':takes[0]['id'],'action':'delete'})[0],200)
        self.assertEqual(len(self.call(a,'friend-takes')[1]['takes']),1)
        self.end_match(a)
        import urllib.error
        with self.assertRaises(urllib.error.HTTPError): b.open(self.url+'/api/media/'+mid)
    def test_message_translation_checks_connection_and_message(self):
        from unittest.mock import patch
        import translation
        (a,aid),(b,bid),(outsider,oid)=self.accounts(3);cid=self.make_match(a,b)
        self.call(a,f'conversations/{cid}/messages',{'text':'Hello'})
        mid=self.call(b,f'conversations/{cid}/messages')[1]['messages'][0]['id']
        def provider(path,payload=None):
            if path=='/languages':return [{'code':'fr','name':'French'}]
            self.assertEqual(payload['q'],'Hello');return {'translatedText':'Bonjour'}
        with patch.object(translation,'provider',side_effect=provider):
            self.assertEqual(self.call(b,f'conversations/{cid}/translate',{'message_id':mid,'target':'fr'})[1]['text'],'Bonjour')
            self.assertEqual(self.call(outsider,f'conversations/{cid}/translate',{'message_id':mid,'target':'fr'})[0],404)
            self.end_match(a)
            self.assertEqual(self.call(b,f'conversations/{cid}/translate',{'message_id':mid,'target':'fr'})[0],404)
    def test_admin_support_export_and_deletion(self):
        (a,aid),(b,bid)=self.accounts()
        self.assertEqual(self.call(a,'admin/reports')[0],403)
        self.call(b,'support',{'subject':'Help','detail':'Please review my account'})
        self.call(b,'success-story',{'story':'A thoughtful connection'})
        with server.connect() as db:db.execute("INSERT INTO account_roles VALUES(?,'admin')",(aid,))
        r=self.call(a,'admin/reports')[1];self.assertEqual(len(r['support']),1)
        story=r['stories'][0]['id'];self.call(a,'admin/review',{'type':'success_stories','id':story,'status':'approved'})
        with self.client().open(self.url+'/api/public/stories') as response:self.assertIn(b'A thoughtful connection',response.read())
        self.assertEqual(self.call(b,'export')[1]['email'],'social1@example.com')
        self.call(b,'delete',{})
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM success_stories WHERE user_id=?',(bid,)).fetchone()[0],0)
