"""Role-protected platform operations and verified prepaid marketplace entitlements."""
import json,time,secrets,os,re,base64,hmac,hashlib
from pathlib import Path
from urllib.parse import urlsplit
from cryptography.fernet import Fernet,InvalidToken
import gateways
from datetime import datetime,timezone
KEY_PATH=None
SCHEMA='''
CREATE TABLE IF NOT EXISTS monthly_match_events(user_id INTEGER,other_id INTEGER,created REAL,UNIQUE(user_id,other_id,created));
CREATE INDEX IF NOT EXISTS monthly_match_user_time ON monthly_match_events(user_id,created);
CREATE TABLE IF NOT EXISTS app_identity(id INTEGER PRIMARY KEY,value INTEGER);
CREATE TABLE IF NOT EXISTS platform_config(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS account_controls(user_id INTEGER PRIMARY KEY,suspended INTEGER DEFAULT 0,reason TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS access_intents(email TEXT PRIMARY KEY,role TEXT,status TEXT,created REAL);
CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY,name TEXT,amount_minor INTEGER,currency TEXT,days INTEGER,tier TEXT,features TEXT,published INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY,name TEXT,amount_minor INTEGER,currency TEXT,kind TEXT,quantity INTEGER,published INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS gateway_config(name TEXT PRIMARY KEY,enabled INTEGER,mode TEXT,secrets TEXT);
CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,user_id INTEGER,item_type TEXT,item_id TEXT,title TEXT,amount_minor INTEGER,currency TEXT,gateway TEXT,mode TEXT,reference TEXT UNIQUE,provider_id TEXT,status TEXT,terms TEXT,created REAL,paid REAL,transaction_id TEXT);
CREATE TABLE IF NOT EXISTS entitlements(order_id TEXT PRIMARY KEY,user_id INTEGER,tier TEXT,expires REAL,roses INTEGER DEFAULT 0,revoked INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS audit_events(id INTEGER PRIMARY KEY,actor INTEGER,action TEXT,target TEXT,detail TEXT,created REAL);
CREATE TABLE IF NOT EXISTS refund_requests(id INTEGER PRIMARY KEY,order_id TEXT UNIQUE,user_id INTEGER,reason TEXT,status TEXT DEFAULT 'requested',created REAL);
'''
PROVIDERS={'stripe':['secret','webhook_secret'],'paypal':['client_id','secret','webhook_id'],'paystack':['secret'],'flutterwave':['secret','webhook_secret']}
CATALOG=['stripe','paypal','paystack','flutterwave','square','adyen','razorpay','mollie','authorize_net','braintree','checkout_com','payoneer','worldpay','klarna','amazon_pay','apple_pay','google_pay','bank_transfer','crypto']
DEFAULTS={'dating_rooms_open':True,'min_profile_photos':0,'max_profile_photos':6,'allow_match_percentage':True,'allow_match_location':True,'allow_preferred_languages':True,'registration_open':True,'maintenance':False,'support_email':'','copyright':'Nekked Dating is owned and operated by NEKKED DATING CORPORATIONS. Copyright 2026 NEKKED DATING CORPORATIONS. All rights reserved.','android_url':'','ios_url':'','marketplace_open':True}

def initialize(c,key_path):
    global KEY_PATH
    KEY_PATH=Path(key_path);c.executescript(SCHEMA)
    plans=[]
    for tier,prices in [('plus',[999,2699,4999,9999]),('premium',[1999,5499,9999,19999])]:
        features=['Unlimited mutual matches','Unlimited Likes','Unlimited Undo','All incoming Likes']+(['Five additional Roses per term'] if tier=='premium' else [])
        for suffix,label,days,price in zip(['month','3-months','6-months','year'],['1 month (30 days)','3 months (90 days)','6 months (180 days)','1 year (365 days)'],[30,90,180,365],prices):
            plans.append((tier+'-'+suffix,tier.title()+' · '+label,price,'USD',days,tier,features))
    c.executemany('INSERT OR IGNORE INTO plans VALUES(?,?,?,?,?,?,?,0)',[row[:6]+(json.dumps(row[6]),) for row in plans])
    c.execute("INSERT OR IGNORE INTO products VALUES('roses-5','Five Roses',499,'USD','roses',5,0)")
    for key,value in DEFAULTS.items():c.execute('INSERT OR IGNORE INTO platform_config VALUES(?,?)',(key,json.dumps(value)))
    c.execute('UPDATE platform_config SET value=? WHERE key=? AND value=?',(json.dumps(DEFAULTS['copyright']),'copyright',json.dumps('Copyright 2026 Olamide Olatayo Bello. All rights reserved.')))
    if not c.execute("SELECT 1 FROM platform_config WHERE key='membership_catalog_v2'").fetchone():
        for item in plans:
            c.execute('UPDATE plans SET features=?,published=1 WHERE id=? AND amount_minor=? AND days=? AND tier=?',(json.dumps(item[6]),item[0],item[2],item[4],item[5]))
        c.execute("INSERT OR REPLACE INTO platform_config VALUES('marketplace_open','true')")
        c.execute("INSERT INTO platform_config VALUES('membership_catalog_v2','true')")
        for row in c.execute('SELECT low_id,high_id,created FROM connections').fetchall():
            c.executemany('INSERT OR IGNORE INTO monthly_match_events VALUES(?,?,?)',[(row[0],row[1],row[2]),(row[1],row[0],row[2])])
    if not c.execute("SELECT 1 FROM platform_config WHERE key='membership_catalog_v3'").fetchone():
        for item in plans:
            c.execute('UPDATE plans SET name=?,features=?,published=1 WHERE id=? AND amount_minor=? AND days=? AND tier=?',(item[1],json.dumps(item[6]),item[0],item[2],item[4],item[5]))
        c.execute("INSERT INTO platform_config VALUES('membership_catalog_v3','true')")
    c.execute('INSERT OR IGNORE INTO app_identity SELECT 1,COALESCE(MAX(id),0) FROM users')
    c.execute('UPDATE app_identity SET value=MAX(value,(SELECT COALESCE(MAX(id),0) FROM users)) WHERE id=1')
    c.commit()

def role(c,uid):
    row=c.execute('SELECT role FROM account_roles WHERE user_id=?',(uid,)).fetchone();return row[0] if row else 'user'
def superuser(c,uid):return role(c,uid)=='super_admin'
def config(c):return DEFAULTS|{r['key']:json.loads(r['value']) for r in c.execute('SELECT * FROM platform_config') if r['key'] in DEFAULTS}
def audit(c,uid,action,target='',detail=''):
    c.execute('INSERT INTO audit_events(actor,action,target,detail,created) VALUES(?,?,?,?,?)',(uid,action,str(target),detail,time.time()))
def cipher():
    if not KEY_PATH.exists():
        try:
            fd=os.open(str(KEY_PATH),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(Fernet.generate_key())
        except FileExistsError:pass
    return Fernet(KEY_PATH.read_bytes())
def read_gateway(c,name):
    row=c.execute('SELECT * FROM gateway_config WHERE name=?',(name,)).fetchone()
    if not row:return {'enabled':False,'mode':'test'},{}
    try:keys=json.loads(cipher().decrypt(row['secrets'].encode())) if row['secrets'] else {}
    except (InvalidToken,OSError,ValueError):keys={}
    return {'enabled':bool(row['enabled']),'mode':row['mode']},keys
def gateway_list(c,admin=False):
    out=[]
    for name in CATALOG:
        conf,keys=read_gateway(c,name);implemented=name in PROVIDERS
        needed=PROVIDERS.get(name,[]);ready=implemented and all(keys.get(k) for k in needed if k not in ('webhook_secret','webhook_id'))
        row={'name':name,'implemented':implemented,'enabled':conf['enabled'],'mode':conf['mode'],'ready':ready,'required_fields':needed if admin else [],'configured_fields':[k for k in needed if keys.get(k)] if admin else []}
        if name in ('apple_pay','google_pay','klarna'):row['note']='Available only when offered by the configured hosted checkout and merchant account.'
        elif not implemented:row['note']='Listed for planning; no checkout adapter is installed.'
        out.append(row)
    return out

def entitlements(c,uid):
    rows=c.execute('SELECT * FROM entitlements WHERE user_id=? AND revoked=0 AND expires>?',(uid,time.time())).fetchall()
    tier='premium' if any(r['tier']=='premium' for r in rows) else 'plus' if any(r['tier']=='plus' for r in rows) else 'free'
    return {'tier':tier,'expires':max((r['expires'] for r in rows if r['tier']!='free'),default=None),'rose_credits':sum(r['roses'] for r in rows)}

def match_quota(c,uid):
    now=datetime.now(timezone.utc)
    start=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    end=start.replace(year=start.year+1,month=1) if start.month==12 else start.replace(month=start.month+1)
    used=c.execute('SELECT COUNT(*) FROM monthly_match_events WHERE user_id=? AND created>=? AND created<?',(uid,start.timestamp(),end.timestamp())).fetchone()[0]
    paid=entitlements(c,uid)['tier']!='free'
    return {'used':used,'limit':None if paid else 20,'remaining':None if paid else max(0,20-used),'resets_at':end.isoformat(),'timezone':'UTC'}

def verify_order(c,order):
    if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
    order=c.execute('SELECT * FROM orders WHERE id=?',(order['id'],)).fetchone()
    if order['status']=='paid':return {'status':'paid','id':order['id']}
    if order['status'] not in ('pending','checkout_ready'):return {'status':order['status'],'id':order['id']}
    conf,keys=read_gateway(c,order['gateway']);conf['mode']=order['mode']
    result=gateways.verify(order['gateway'],conf,keys,dict(order))
    if result.get('mode')!=order['mode']:raise ValueError('Provider test/live mode does not match this order.')
    expected=order['id'] if order['gateway'] in ('stripe','paypal') else order['reference']
    if not result['paid']:return {'status':'pending','id':order['id']}
    if result['reference']!=expected or result['amount_minor']!=order['amount_minor'] or result['currency']!=order['currency']:raise ValueError('Payment verification did not match the order amount, currency and reference.')
    # Only live verified orders grant production benefits. Test orders are tracked distinctly.
    if order['mode']=='test':
        c.execute("UPDATE orders SET status='test_paid',paid=?,transaction_id=? WHERE id=?",(time.time(),result.get('transaction'),order['id']));return {'status':'test_paid','id':order['id']}
    c.execute("UPDATE orders SET status='paid',paid=?,transaction_id=? WHERE id=? AND status IN ('pending','checkout_ready')",(time.time(),result.get('transaction'),order['id']))
    terms=json.loads(order['terms']);now=time.time()
    if order['item_type']=='plan':
        end=c.execute("SELECT MAX(expires) FROM entitlements WHERE user_id=? AND revoked=0 AND tier!='free'",(order['user_id'],)).fetchone()[0] or now
        c.execute('INSERT OR IGNORE INTO entitlements VALUES(?,?,?,?,?,0)',(order['id'],order['user_id'],terms['tier'],max(now,end)+terms['days']*86400,5 if terms['tier']=='premium' else 0))
    else:c.execute('INSERT OR IGNORE INTO entitlements VALUES(?,?,?,?,?,0)',(order['id'],order['user_id'],'free',now+365*86400,terms['quantity']))
    audit(c,order['user_id'],'payment_verified',order['id']);return {'status':'paid','id':order['id']}

def integer(data,key,minval,maxval):
    val=data.get(key)
    if type(val) is not int or not minval<=val<=maxval:raise ValueError('Invalid '+key)
    return val

def short(data,key,limit=200):
    val=data.get(key,'')
    if not isinstance(val,str) or len(val)>limit:raise ValueError('Invalid '+key)
    return val.strip()

def dispatch(method,path,data,c,u,verify_password):
    uid=u['id'];is_super=superuser(c,uid)
    if path.startswith('/api/super/') and not is_super:return 403,{'error':'Super-admin access required.'}
    if method=='GET':
        if path=='/api/marketplace':return 200,{'plans':[dict(r)|{'features':json.loads(r['features'])} for r in c.execute('SELECT * FROM plans WHERE published=1')],'products':[dict(r) for r in c.execute('SELECT * FROM products WHERE published=1')],'gateways':[r for r in gateway_list(c) if r['implemented'] and r['enabled'] and r['ready']],'open':config(c)['marketplace_open'],'entitlements':entitlements(c,uid),'match_quota':match_quota(c,uid),'free_plan':{'name':'Free','amount_minor':0,'currency':'USD','features':['Up to 20 new mutual matches per calendar month (UTC)','Message existing matches','Personal symbols and matched compatibility','8 Likes per rolling 24 hours']},'billing':'Prepaid fixed-term access; no automatic recurring charges.'}
        if path=='/api/orders':return 200,{'orders':[dict(r) for r in c.execute('SELECT id,title,amount_minor,currency,gateway,mode,status,created,paid FROM orders WHERE user_id=? ORDER BY created DESC LIMIT 100',(uid,))]}
        if path=='/api/super/overview':
            counts={name:c.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in ['users','connections','messages','reports','support_requests','orders']}
            revenue=[dict(r) for r in c.execute("SELECT currency,SUM(amount_minor) amount_minor FROM orders WHERE status='paid' GROUP BY currency")]
            return 200,{'counts':counts,'revenue':revenue,'active_memberships':c.execute("SELECT COUNT(DISTINCT user_id) FROM entitlements WHERE tier!='free' AND revoked=0 AND expires>?",(time.time(),)).fetchone()[0]}
        if path=='/api/super/users':return 200,{'users':[{'id':r['id'],'email':r['email'],'name':json.loads(r['profile']).get('first_name','') if r['profile'] else '', 'role':role(c,r['id']),'suspended':bool(c.execute('SELECT suspended FROM account_controls WHERE user_id=?',(r['id'],)).fetchone()[0]) if c.execute('SELECT 1 FROM account_controls WHERE user_id=?',(r['id'],)).fetchone() else False} for r in c.execute('SELECT id,email,profile FROM users ORDER BY id DESC LIMIT 500')]}
        if path=='/api/super/catalog':return 200,{'plans':[dict(r)|{'features':json.loads(r['features'])} for r in c.execute('SELECT * FROM plans')],'products':[dict(r) for r in c.execute('SELECT * FROM products')]}
        if path=='/api/super/gateways':return 200,{'gateways':gateway_list(c,True)}
        if path=='/api/super/settings':return 200,config(c)
        if path=='/api/super/orders':return 200,{'orders':[dict(r) for r in c.execute('SELECT id,user_id,title,amount_minor,currency,gateway,mode,status,created,paid FROM orders ORDER BY created DESC LIMIT 200')],'refunds':[dict(r) for r in c.execute('SELECT * FROM refund_requests ORDER BY id DESC')]}
        if path=='/api/super/audit':return 200,{'events':[dict(r) for r in c.execute('SELECT * FROM audit_events ORDER BY id DESC LIMIT 200')]}
        return None
    if method!='POST':return None
    if path=='/api/super/user':
        target=integer(data,'user_id',1,2147483647);action=data.get('action');row=c.execute('SELECT id FROM users WHERE id=?',(target,)).fetchone()
        if not row:raise ValueError('User not found.')
        if action in ('role','suspend'):
            if not verify_password(short(data,'password',128)):return 403,{'error':'Confirm your current password.'}
            current=role(c,target)
            if current=='super_admin' and c.execute("SELECT COUNT(*) FROM account_roles WHERE role='super_admin'").fetchone()[0]<=1 and ((action=='suspend' and data.get('suspended') is True) or (action=='role' and data.get('role')!='super_admin')):raise ValueError('The last super admin cannot be suspended or demoted.')
        if action=='role':
            value=data.get('role')
            if value not in ('user','admin','super_admin'):raise ValueError('Invalid role.')
            c.execute('INSERT OR REPLACE INTO account_roles VALUES(?,?)',(target,value))
        elif action=='suspend':
            value=data.get('suspended')
            if type(value) is not bool:raise ValueError('Choose account state.')
            c.execute('INSERT OR REPLACE INTO account_controls VALUES(?,?,?)',(target,value,short(data,'reason')))
            c.execute('DELETE FROM sessions WHERE user_id=?',(target,))
        elif action=='revoke_sessions':c.execute('DELETE FROM sessions WHERE user_id=?',(target,))
        else:raise ValueError('Unknown account action.')
        audit(c,uid,'user_'+action,target);return 200,{'ok':True}
    if path=='/api/super/plan':
        ident=short(data,'id',80);name=short(data,'name');currency=short(data,'currency',3).upper();tier=data.get('tier');features=data.get('features',[])
        if not re.fullmatch('[a-z0-9-]+',ident) or not name or currency not in ('USD','NGN','EUR','GBP','CAD','AUD','GHS','ZAR','KES') or tier not in ('plus','premium') or not isinstance(features,list) or len(features)>10 or any(not isinstance(x,str) or len(x)>200 for x in features):raise ValueError('Invalid plan.')
        published=data.get('published',False)
        if type(published) is not bool:raise ValueError('Invalid publication state.')
        c.execute('INSERT OR REPLACE INTO plans VALUES(?,?,?,?,?,?,?,?)',(ident,name,integer(data,'amount_minor',100,100000000),currency,integer(data,'days',1,730),tier,json.dumps(features),published));audit(c,uid,'save_plan',ident);return 200,{'ok':True}
    if path=='/api/super/product':
        ident=short(data,'id',80);name=short(data,'name');currency=short(data,'currency',3).upper()
        if not re.fullmatch('[a-z0-9-]+',ident) or not name or currency not in ('USD','NGN','EUR','GBP','CAD','AUD','GHS','ZAR','KES'):raise ValueError('Invalid product.')
        if type(data.get('published',False)) is not bool:raise ValueError('Invalid publication state.')
        c.execute('INSERT OR REPLACE INTO products VALUES(?,?,?,?,?,?,?)',(ident,name,integer(data,'amount_minor',100,100000000),currency,'roses',integer(data,'quantity',1,100),data.get('published',False)));audit(c,uid,'save_product',ident);return 200,{'ok':True}
    if path=='/api/super/gateway':
        name=data.get('name')
        if name not in PROVIDERS:raise ValueError('Only installed gateway adapters can be configured.')
        if not verify_password(short(data,'password',128)):return 403,{'error':'Confirm your current password.'}
        if data.get('mode') not in ('test','live') or type(data.get('enabled')) is not bool:raise ValueError('Choose gateway mode and state.')
        conf,keys=read_gateway(c,name);new=data.get('keys',{})
        if not isinstance(new,dict) or any(k not in PROVIDERS[name] or not isinstance(v,str) or len(v)>2000 for k,v in new.items()):raise ValueError('Invalid gateway credentials.')
        keys.update({k:v for k,v in new.items() if v})
        if data['enabled'] and not all(keys.get(k) for k in PROVIDERS[name] if k not in ('webhook_secret','webhook_id')):raise ValueError('Complete required gateway credentials before enabling.')
        encrypted=cipher().encrypt(json.dumps(keys).encode()).decode();c.execute('INSERT OR REPLACE INTO gateway_config VALUES(?,?,?,?)',(name,data['enabled'],data['mode'],encrypted));audit(c,uid,'save_gateway',name,'mode='+data['mode']);return 200,{'ok':True}
    if path=='/api/super/settings':
        allowed=set(DEFAULTS)
        if any(k not in allowed for k in data):raise ValueError('Unknown setting.')
        proposed=config(c)|data
        if any(type(proposed[k]) is not int or not 0<=proposed[k]<=12 for k in ('min_profile_photos','max_profile_photos')) or proposed['max_profile_photos']<1 or proposed['min_profile_photos']>proposed['max_profile_photos']:raise ValueError('Photo limits must satisfy 0 <= minimum <= maximum <= 12, with maximum at least 1.')
        for key,val in data.items():
            if type(DEFAULTS[key]) is int:
                if type(val) is not int:raise ValueError('Invalid numeric setting.')
            elif isinstance(DEFAULTS[key],bool):
                if type(val) is not bool:raise ValueError('Invalid toggle.')
            else:
                if not isinstance(val,str) or len(val)>500:raise ValueError('Invalid text setting.')
                if key=='support_email' and val and (not re.fullmatch(r'[^\s@]+@[^\s@]+[.][^\s@]+',val)):raise ValueError('Enter a valid support email.')
                if key in ('android_url','ios_url') and val:
                    url=urlsplit(val)
                    if url.scheme!='https' or not url.hostname or url.username or url.password:raise ValueError('Download links must use HTTPS.')
            c.execute('INSERT OR REPLACE INTO platform_config VALUES(?,?)',(key,json.dumps(val)))
        audit(c,uid,'save_platform_settings');return 200,{'ok':True}
    if path=='/api/checkout':
        if not config(c)['marketplace_open']:return 409,{'error':'Marketplace checkout is not open.'}
        kind=data.get('item_type');ident=short(data,'item_id',80);name=data.get('gateway')
        if kind not in ('plan','product') or name not in PROVIDERS:raise ValueError('Choose an available product and gateway.')
        table='plans' if kind=='plan' else 'products';item=c.execute('SELECT * FROM '+table+' WHERE id=? AND published=1',(ident,)).fetchone()
        if not item:raise ValueError('This item is not available.')
        conf,keys=read_gateway(c,name)
        if not conf['enabled'] or not all(keys.get(k) for k in PROVIDERS[name] if k not in ('webhook_secret','webhook_id')):return 409,{'error':'Gateway is not ready.'}
        oid=secrets.token_hex(16);ref='nekked-'+oid;origin=os.environ.get('NEKKED_ORIGIN','https://nekkeddating.com')
        if not origin.startswith('https://'):raise ValueError('Configure HTTPS before accepting payments.')
        order={'id':oid,'amount_minor':item['amount_minor'],'currency':item['currency'],'title':item['name'],'reference':ref,'email':u['email']}
        provider,url=gateways.checkout(name,conf,keys,order,origin);url=gateways.safe_checkout_url(name,url)
        terms={'tier':item['tier'],'days':item['days']} if kind=='plan' else {'quantity':item['quantity']}
        c.execute('INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,uid,kind,ident,item['name'],item['amount_minor'],item['currency'],name,conf['mode'],ref,provider,'checkout_ready',json.dumps(terms),time.time(),None,None))
        audit(c,uid,'checkout_created',oid);return 200,{'order_id':oid,'url':url,'mode':conf['mode']}
    if path in ('/api/orders/verify','/api/super/order-verify'):
        oid=short(data,'order_id',64);order=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
        if not order or (order['user_id']!=uid and not is_super):return 404,{'error':'Order not found.'}
        return 200,verify_order(c,order)
    if path=='/api/refund-request':
        oid=short(data,'order_id',64);order=c.execute("SELECT id FROM orders WHERE id=? AND user_id=? AND status='paid'",(oid,uid)).fetchone()
        if not order:raise ValueError('Choose your paid order.')
        c.execute('INSERT OR IGNORE INTO refund_requests(order_id,user_id,reason,created) VALUES(?,?,?,?)',(oid,uid,short(data,'reason',1000),time.time()));return 200,{'ok':True}
    if path=='/api/super/refund-review':
        rid=integer(data,'id',1,2147483647);status=data.get('status')
        if status not in ('reviewing','declined','completed_externally'):raise ValueError('Choose refund state.')
        row=c.execute('SELECT * FROM refund_requests WHERE id=?',(rid,)).fetchone()
        if not row:raise ValueError('Refund request not found.')
        if status=='completed_externally':
            if not verify_password(short(data,'password',128)) or not short(data,'reference',200):return 403,{'error':'Confirm your password and provider refund reference.'}
            c.execute('UPDATE entitlements SET revoked=1 WHERE order_id=?',(row['order_id'],));c.execute("UPDATE orders SET status='refunded' WHERE id=?",(row['order_id'],))
        c.execute('UPDATE refund_requests SET status=? WHERE id=?',(status,rid));audit(c,uid,'refund_'+status,row['order_id'],short(data,'reference',200));return 200,{'ok':True}
    return None

def webhook(name,raw,data,headers,c):
    if name not in PROVIDERS:return 404,{'error':'Unknown gateway.'}
    conf,keys=read_gateway(c,name)
    if not conf['enabled']:return 403,{'error':'Gateway disabled.'}
    valid=False;oid=None;resource=data.get('data',{})
    if name=='stripe':
        try:
            parts=headers.get('Stripe-Signature','').split(',');timestamp=next(v[2:] for v in parts if v.startswith('t='));sigs=[v[3:] for v in parts if v.startswith('v1=')]
            expected=hmac.new(keys.get('webhook_secret','').encode(),timestamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
            valid=bool(keys.get('webhook_secret')) and abs(time.time()-int(timestamp))<300 and any(hmac.compare_digest(expected,x) for x in sigs)
            oid=data.get('data',{}).get('object',{}).get('client_reference_id')
        except (StopIteration,ValueError):pass
    elif name=='paystack':
        expected=hmac.new(keys.get('secret','').encode(),raw,hashlib.sha512).hexdigest();valid=bool(keys.get('secret')) and hmac.compare_digest(expected,headers.get('x-paystack-signature',''))
        row=c.execute('SELECT id FROM orders WHERE gateway=? AND reference=?',(name,resource.get('reference'))).fetchone();oid=row[0] if row else None
    elif name=='flutterwave':
        secret=keys.get('webhook_secret','');signature=headers.get('flutterwave-signature','');legacy=headers.get('verif-hash','')
        expected=base64.b64encode(hmac.new(secret.encode(),raw,hashlib.sha256).digest()).decode()
        valid=bool(secret) and ((bool(signature) and hmac.compare_digest(expected,signature)) or (bool(legacy) and hmac.compare_digest(secret,legacy)))
        row=c.execute('SELECT id FROM orders WHERE gateway=? AND reference=?',(name,resource.get('tx_ref'))).fetchone();oid=row[0] if row else None
    elif name=='paypal':
        if keys.get('webhook_id'):
            token=gateways.pp_token(conf,keys)
            response=gateways.request(gateways.pp_base(conf)+'/v1/notifications/verify-webhook-signature',{'auth_algo':headers.get('PAYPAL-AUTH-ALGO'),'cert_url':headers.get('PAYPAL-CERT-URL'),'transmission_id':headers.get('PAYPAL-TRANSMISSION-ID'),'transmission_sig':headers.get('PAYPAL-TRANSMISSION-SIG'),'transmission_time':headers.get('PAYPAL-TRANSMISSION-TIME'),'webhook_id':keys['webhook_id'],'webhook_event':data},gateways.bearer(token))
            valid=response.get('verification_status')=='SUCCESS'
        provider=data.get('resource',{}).get('supplementary_data',{}).get('related_ids',{}).get('order_id') or data.get('resource',{}).get('id')
        row=c.execute('SELECT id FROM orders WHERE gateway=? AND provider_id=?',(name,provider)).fetchone();oid=row[0] if row else None
    if not valid:return 403,{'error':'Invalid webhook signature.'}
    order=c.execute('SELECT * FROM orders WHERE id=? AND gateway=?',(oid,name)).fetchone() if oid else None
    if not order:return 200,{'received':True,'matched_order':False}
    return 200,verify_order(c,order)
