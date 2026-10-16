import unittest, json, hmac,hashlib,time,subprocess,sys
from unittest.mock import patch
import test_social as social_tests
import test_app as app_tests
import server,commerce,gateways
class CommerceTests(unittest.TestCase):
    setUpClass=classmethod(app_tests.APITests.setUpClass.__func__)
    tearDownClass=classmethod(app_tests.APITests.tearDownClass.__func__)
    setUp=app_tests.APITests.setUp
    client=app_tests.APITests.client
    call=app_tests.APITests.call
    accounts=social_tests.SocialTests.accounts
    def bootstrap(self):
        (a,aid),(b,bid)=self.accounts()
        with server.connect() as db:db.execute("INSERT INTO account_roles VALUES(?,'super_admin')",(aid,))
        return a,aid,b,bid
    def test_photo_policy_and_preference_controls(self):
        a,aid,b,bid=self.bootstrap()
        self.assertEqual(self.call(b,'super/settings',{'max_profile_photos':2})[0],403)
        self.assertEqual(self.call(a,'super/settings',{'min_profile_photos':3,'max_profile_photos':2})[0],400)
        self.assertEqual(self.call(a,'super/settings',{'min_profile_photos':1,'max_profile_photos':2,'allow_match_percentage':False,'allow_match_location':False,'allow_preferred_languages':False})[0],200)
        p=self.call(b,'me')[1]['profile']
        self.assertEqual(self.call(b,'profile',p)[0],400)
        p['discoverable']=False
        self.assertEqual(self.call(b,'profile',p)[0],200)
        self.assertFalse(self.call(b,'public/platform')[1]['allow_match_location'])

    def gateway(self,a,mode='test'):
        return self.call(a,'super/gateway',{'name':'stripe','enabled':True,'mode':mode,'password':'strong password 123','keys':{'secret':'merchant-test-secret','webhook_secret':'webhook-secret'}})
    def publish(self,a):
        with server.connect() as db:
            db.execute("UPDATE plans SET published=1 WHERE id='plus-month'")
        self.call(a,'super/settings',{'marketplace_open':True})
    def checkout(self,b):
        with patch.object(gateways,'checkout',return_value=('session-1','https://checkout.stripe.com/example')):
            code,result=self.call(b,'checkout',{'item_type':'plan','item_id':'plus-month','gateway':'stripe','amount_minor':1})
            self.assertEqual(code,200)
            return result['order_id']
    def test_roles_last_admin_and_encrypted_credentials(self):
        a,aid,b,bid=self.bootstrap()
        self.assertEqual(self.call(b,'super/overview')[0],403)
        self.assertEqual(self.call(b,'super/settings',{'marketplace_open':True})[0],403)
        self.assertEqual(self.call(a,'super/user',{'user_id':aid,'action':'role','role':'user','password':'strong password 123'})[0],400)
        self.assertEqual(self.gateway(a)[0],200)
        public=json.dumps(self.call(a,'super/gateways')[1]);self.assertNotIn('merchant-test-secret',public);self.assertNotIn('webhook-secret',public)
        with server.connect() as db:
            encrypted=db.execute("SELECT secrets FROM gateway_config WHERE name='stripe'").fetchone()[0]
            self.assertNotIn('merchant-test-secret',encrypted)
            self.assertNotIn('merchant-test-secret',json.dumps([dict(r) for r in db.execute('SELECT * FROM audit_events')]))
        self.assertEqual(self.call(a,'super/gateway',{'name':'square','enabled':True,'mode':'test','keys':{},'password':'strong password 123'})[0],400)
    def test_suspension_maintenance_and_registration_controls(self):
        a,aid,b,bid=self.bootstrap()
        self.assertEqual(self.call(a,'super/user',{'user_id':bid,'action':'suspend','suspended':True,'password':'strong password 123','reason':'Operator review'})[0],200)
        self.assertEqual(self.call(b,'me')[0],401)
        self.assertEqual(self.call(self.client(),'login',{'email':'social1@example.com','password':'strong password 123'})[0],403)
        self.call(a,'super/settings',{'registration_open':False,'maintenance':True})
        self.assertEqual(self.call(self.client(),'register',{'email':'new@example.com','password':'strong password 123','adult':True})[0],403)
        self.assertEqual(self.call(a,'super/overview')[0],200)
    def test_test_order_never_grants_live_benefits(self):
        a,aid,b,bid=self.bootstrap();self.gateway(a);self.publish(a);oid=self.checkout(b)
        with server.connect() as db:self.assertEqual(db.execute('SELECT amount_minor FROM orders WHERE id=?',(oid,)).fetchone()[0],999)
        response={'paid':True,'amount_minor':999,'currency':'USD','reference':oid,'transaction':'pi-1','mode':'test'}
        with patch.object(gateways,'verify',return_value=response):
            result=self.call(b,'orders/verify',{'order_id':oid})[1];self.assertEqual(result['status'],'test_paid')
        self.assertEqual(self.call(b,'marketplace')[1]['entitlements']['tier'],'free')
    def test_live_verification_is_idempotent_and_checks_amount(self):
        a,aid,b,bid=self.bootstrap();self.gateway(a,'live');self.publish(a);oid=self.checkout(b)
        wrong={'paid':True,'amount_minor':1,'currency':'USD','reference':oid,'transaction':'pi-1','mode':'live'}
        with patch.object(gateways,'verify',return_value=wrong):self.assertEqual(self.call(b,'orders/verify',{'order_id':oid})[0],400)
        self.assertEqual(self.call(b,'marketplace')[1]['entitlements']['tier'],'free')
        correct=wrong|{'amount_minor':999}
        with patch.object(gateways,'verify',return_value=correct):
            self.assertEqual(self.call(b,'orders/verify',{'order_id':oid})[1]['status'],'paid')
            self.assertEqual(self.call(b,'orders/verify',{'order_id':oid})[1]['status'],'paid')
        with server.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM entitlements WHERE order_id=?',(oid,)).fetchone()[0],1)
        self.assertEqual(self.call(b,'marketplace')[1]['entitlements']['tier'],'plus')
        self.assertEqual(self.call(b,'refund-request',{'order_id':oid,'reason':'Requested'})[0],200)
        rid=self.call(a,'super/orders')[1]['refunds'][0]['id']
        self.assertEqual(self.call(a,'super/refund-review',{'id':rid,'status':'completed_externally','reference':'refund-provider-1','password':'strong password 123'})[0],200)
        self.assertEqual(self.call(b,'marketplace')[1]['entitlements']['tier'],'free')
    def test_signed_webhook_verifies_provider_and_ignores_replay(self):
        a,aid,b,bid=self.bootstrap();self.gateway(a,'live');self.publish(a);oid=self.checkout(b)
        event={'type':'checkout.session.completed','data':{'object':{'client_reference_id':oid}}};raw=json.dumps(event).encode();ts=str(int(time.time()));sig=hmac.new(b'webhook-secret',ts.encode()+b'.'+raw,hashlib.sha256).hexdigest()
        self.assertEqual(self.call(self.client(),'webhooks/stripe',event,{'Stripe-Signature':'bad'})[0],403)
        verified={'paid':True,'amount_minor':999,'currency':'USD','reference':oid,'transaction':'pi-hook','mode':'live'}
        with patch.object(gateways,'verify',return_value=verified):
            for i in range(2):self.assertEqual(self.call(self.client(),'webhooks/stripe',event,{'Stripe-Signature':f't={ts},v1={sig}'})[1]['status'],'paid')
        with server.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM entitlements WHERE order_id=?',(oid,)).fetchone()[0],1)
    def test_download_settings_and_existing_account_promotion(self):
        a,aid,b,bid=self.bootstrap()
        self.assertEqual(self.call(a,'super/settings',{'android_url':'javascript:alert(1)'})[0],400)
        self.assertEqual(self.call(a,'super/settings',{'android_url':'https://nekkeddating.com/releases/app.apk'})[0],200)
        with self.client().open(self.url+'/api/public/platform') as response:self.assertIn('releases/app.apk',json.load(response)['android_url'])
        completed=subprocess.run([sys.executable,'scripts/grant-admin.py','--db',server.DB,'--email','social1@example.com','--role','super_admin','--defer'],capture_output=True,text=True)
        self.assertEqual(completed.returncode,0);self.assertIn('APPLIED',completed.stdout)
        self.assertEqual(self.call(b,'super/overview')[0],200)
        missing=subprocess.run([sys.executable,'scripts/grant-admin.py','--db',server.DB,'--email','kendollreign@gmail.com','--role','super_admin','--defer'],capture_output=True,text=True)
        self.assertIn('PENDING',missing.stdout)
        with server.connect() as db:self.assertEqual(db.execute("SELECT status FROM access_intents WHERE email='kendollreign@gmail.com'").fetchone()[0],'pending_existing_account')
