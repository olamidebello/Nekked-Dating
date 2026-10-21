import base64, struct, re
import hashlib, hmac, json, os, secrets, sqlite3, time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from http.cookies import SimpleCookie
from matching import overview, compatibility, eligible, matched, age, SORT_METHODS
from symbol_details import symbol_detail
from astrology_tools import match_report
import translation
import social
import dating
import commerce
import gateways
DB = os.environ.get('NEKKED_DB','nekked.sqlite3')
CATEGORIES = ['emotional','intimacy','financial','living','moods']
def connect():
    c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row
    c.executescript('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE,password TEXT,profile TEXT); CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER,expires REAL); CREATE TABLE IF NOT EXISTS photos(id TEXT PRIMARY KEY,user_id INTEGER,data BLOB); CREATE TABLE IF NOT EXISTS onboarding(user_id INTEGER PRIMARY KEY,data TEXT);')
    c.executescript(social.SCHEMA)
    c.executescript(dating.SCHEMA)
    if 'media_id' not in {r[1] for r in c.execute('PRAGMA table_info(messages)')}: c.execute("ALTER TABLE messages ADD COLUMN media_id TEXT DEFAULT ''")
    commerce.initialize(c,str(Path(DB).parent/'.nekked-commerce.key'))
    return c

def password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()

def validate(p):
    for k in ['first_name','last_name','birth_date','birth_location','bio']:
        if not isinstance(p.get(k),str) or not 1<=len(p[k].strip())<=1000: raise ValueError('Complete all profile fields.')
    dob=date.fromisoformat(p['birth_date']); today=date.today()
    if (today.year-dob.year-((today.month,today.day)<(dob.month,dob.day)))<18: raise ValueError('You must be at least 18.')
    if p.get('birth_time'): datetime.strptime(p['birth_time'],'%H:%M')
    if not isinstance(p.get('discoverable'),bool): raise ValueError('Choose profile visibility.')
    if set(p.get('preferences',{})) not in (set(CATEGORIES),set(CATEGORIES)|{'communication'}) or any(v not in ('similar','flexible','independent') for v in p['preferences'].values()): raise ValueError('Complete compatibility preferences.')
    q=p.get('answers',{})
    for k in ['animal','color','paradise','box']:
        a=q.get(k,{})
        if not isinstance(a.get('choice'),str) or not 1<=len(a['choice'])<=1000: raise ValueError('Complete each reflection.')
        if not isinstance(a.get('words'),list) or len(a['words'])!=3 or any(not isinstance(w,str) or not 1<=len(w.strip())<=500 for w in a['words']): raise ValueError('Provide three words for every reflection.')
    extra=demographics(p)
    method=p.get('preferred_match','overall')
    if method not in SORT_METHODS: raise ValueError('Invalid matching preference.')
    extra['preferred_match']=method
    for key,default in [('match_min_percent',0),('match_max_percent',100)]:
        value=p.get(key,default)
        if type(value) is not int or not 0<=value<=100:raise ValueError('Match percentages must be whole numbers from 0 to 100.')
        extra[key]=value
    if extra['match_min_percent']>extra['match_max_percent']:raise ValueError('Minimum match percentage cannot exceed maximum.')
    for key in ('desired_locations','preferred_languages'):
        value=p.get(key,'')
        if not isinstance(value,str) or len(value)>500:raise ValueError('Invalid matching preference.')
        extra[key]=value.strip()
    allowed={'gender':('woman','man','nonbinary','self-described'),'seeking':('woman','man','nonbinary','any'),'relationship_goal':('long-term','marriage','dating','friendship','open-to-exploring'),'children':('','prefer-not-to-say','want-children','have-children','do-not-want','open'),'smoking':('','prefer-not-to-say','non-smoker','smoker','open')}
    for k,choices in allowed.items():
        v=p.get(k,'')
        if v not in choices and v!='': raise ValueError('Invalid '+k)
        extra[k]=v
    for k,limit in [('birth_name',200),('current_location',200),('interests',500)]:
        v=p.get(k,'')
        if not isinstance(v,str) or len(v)>limit: raise ValueError('Invalid '+k)
        extra[k]=v.strip()
    for k,default in [('min_age',18),('max_age',120)]:
        v=p.get(k,default)
        if type(v) is not int or not 18<=v<=120: raise ValueError('Invalid age preference.')
        extra[k]=v
    for key in social.VISIBLE:
        if key in extra: continue
        value=p.get(key,'')
        if not isinstance(value,str) or len(value)>200: raise ValueError('Invalid profile detail.')
        extra[key]=value.strip()
    visible=p.get('visible_details',social.VISIBLE)
    if not isinstance(visible,list) or any(k not in social.VISIBLE for k in visible): raise ValueError('Invalid profile visibility.')
    extra['visible_details']=visible
    prompts=p.get('public_prompts',[])
    if not isinstance(prompts,list) or len(prompts)>3: raise ValueError('Choose up to three public prompts.')
    cleaned=[]
    for item in prompts:
        if not isinstance(item,dict): raise ValueError('Invalid prompt.')
        question=item.get('question',''); answer=item.get('answer','')
        if not isinstance(question,str) or not isinstance(answer,str) or not 1<=len(question)<=200 or not 1<=len(answer.strip())<=500: raise ValueError('Complete each public prompt.')
        cleaned.append({'question':question,'answer':answer.strip()})
    extra['public_prompts']=cleaned
    media=p.get('public_media',[])
    if not isinstance(media,list) or len(media)>2 or any(not isinstance(x,str) or len(x)>64 for x in media): raise ValueError('Invalid profile media.')
    extra['public_media']=media
    poll=p.get('poll')
    if poll:
        if not isinstance(poll,dict) or not isinstance(poll.get('question'),str) or not 1<=len(poll['question'])<=200 or not isinstance(poll.get('options'),list) or len(poll['options'])!=3 or any(not isinstance(x,str) or not 1<=len(x.strip())<=100 for x in poll['options']): raise ValueError('Provide a poll question and three choices.')
    extra['poll']=poll
    photos=p.get('photos',[])
    if not isinstance(photos,list) or len(photos)>12 or any(not isinstance(x,str) or len(x)>64 for x in photos) or len(set(photos))!=len(photos): raise ValueError('Invalid photos.')
    extra['photos']=photos
    return extra | {k:p[k] for k in ['first_name','last_name','birth_date','birth_location','bio','discoverable','preferences','answers']} | {'birth_time':p.get('birth_time','')}

def demographics(data):
    result={}
    for key in ['race','religion','languages']:
        value=data.get(key,'')
        if not isinstance(value,str) or len(value)>200: raise ValueError('Invalid profile information.')
        result[key]=value.strip()
    return result

def onboarding_data(data):
    result=demographics(data)
    if data.get('birth_date'):
        result['birth_date']=data['birth_date']
        if not isinstance(result['birth_date'],str) or age(result)<18: raise ValueError('Adults only.')
    return result

def validate_jpeg(image):
    if len(image)>500000 or not image.startswith(b'\xff\xd8') or not image.endswith(b'\xff\xd9'): raise ValueError('Invalid JPEG.')
    i=2
    while i+4<=len(image):
        if image[i]!=255: raise ValueError('Invalid JPEG marker.')
        marker=image[i+1]; length=int.from_bytes(image[i+2:i+4],'big')
        if length<2 or i+2+length>len(image): raise ValueError('Invalid JPEG length.')
        if marker in (192,193,194):
            if length<8: raise ValueError('Invalid JPEG dimensions.')
            height,width=struct.unpack('>HH',image[i+5:i+9])
            if not 1<=width<=1600 or not 1<=height<=1600: raise ValueError('Photo too large.')
            return
        i+=2+length
    raise ValueError('Missing JPEG dimensions.')

class Handler(BaseHTTPRequestHandler):
    def reply(self,status,data):
        body=json.dumps(data).encode(); self.send_response(status)
        self.send_header('Content-Type','application/json'); self.send_header('Cache-Control','no-store')
        for v in getattr(self,'cookies',[]): self.send_header('Set-Cookie',v)
        self.end_headers(); self.wfile.write(body)
    def user(self,c):
        cookies=SimpleCookie(); cookies.load(self.headers.get('Cookie',''))
        token=cookies.get('session'); token=token.value if token else ''
        user=c.execute('SELECT users.* FROM users JOIN sessions ON user_id=users.id WHERE token=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        if user and c.execute('SELECT 1 FROM account_controls WHERE user_id=? AND suspended=1',(user['id'],)).fetchone():return None
        return user
    def do_GET(self):
        self.path=self.path.split('?',1)[0]
        if self.path=='/api/public/platform':
            with connect() as c:return self.reply(200,commerce.config(c))
        if self.path=='/api/public/stories':
            with connect() as c: return self.reply(200,{'stories':[dict(r) for r in c.execute("SELECT story FROM success_stories WHERE status='approved' ORDER BY id DESC LIMIT 30")]})
        if self.path.startswith('/api/'):
            with connect() as c:
                u=self.user(c)
                if not u: return self.reply(401,{'error':'Please sign in.'})
                p=json.loads(u['profile']) if u['profile'] else None
                if commerce.config(c)['maintenance'] and not commerce.superuser(c,u['id']) and self.path in ('/api/discover','/api/standouts','/api/likes','/api/matches'):return self.reply(503,{'error':'The platform is temporarily in maintenance mode.'})
                handled=commerce.dispatch('GET',self.path,{},c,u,lambda _:False)
                if handled is not None:return self.reply(*handled)
                handled=dating.dispatch('GET',self.path,{},c,u,p)
                if handled is not None:return self.reply(*handled)
                handled=social.dispatch('GET',self.path,{},c,u,p)
                if handled is not None: return self.reply(*handled)
                if self.path.startswith('/api/media/'):
                    media=c.execute('SELECT * FROM media WHERE id=?',(self.path.rsplit('/',1)[-1],)).fetchone()
                    if not media: return self.reply(404,{'error':'Media unavailable.'})
                    allowed=media['user_id']==u['id']
                    if not allowed:
                        owner,other=social.person(c,media['user_id'])
                        public=other and media['id'] in other.get('public_media',[]) and (social.candidate(c,u['id'],p,media['user_id'],other) or social.match_allowed(c,u['id'],media['user_id']))
                        attached=c.execute('SELECT connection_id FROM messages WHERE media_id=?',(media['id'],)).fetchall()
                        allowed=public or any(social.connection_row(c,u['id'],r[0]) for r in attached)
                    if not allowed: return self.reply(404,{'error':'Media unavailable.'})
                    self.send_response(200); self.send_header('Content-Type',media['type']); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(media['data']); return
                detail_route=re.fullmatch(r'/api/symbols/(me|[1-9][0-9]*)/(sun_sign|chinese_zodiac|life_path|name_number)',self.path)
                if detail_route:
                    subject,key=detail_route.groups()
                    if subject=='me':
                        if not p: return self.reply(400,{'error':'Save your profile first.'})
                        return self.reply(200,{'subject':'Your profile','detail':symbol_detail(p,key,private=True)})
                    row=c.execute('SELECT profile FROM users WHERE id=? AND id!=?',(int(subject),u['id'])).fetchone()
                    other=json.loads(row['profile']) if row and row['profile'] else None
                    if not social.match_allowed(c,u['id'],int(subject)): return self.reply(404,{'error':'This match is no longer available.'})
                    return self.reply(200,{'subject':other['first_name'],'detail':symbol_detail(other,key)})
                if self.path=='/api/numerology/me':
                    if not p: return self.reply(400,{'error':'Save your profile first.'})
                    return self.reply(200,{'overview':overview(p,private=True)})
                comparison=re.fullmatch(r'/api/compatibility/([1-9][0-9]*)',self.path)
                if comparison:
                    row=c.execute('SELECT profile FROM users WHERE id=? AND id!=?',(int(comparison[1]),u['id'])).fetchone()
                    other=json.loads(row['profile']) if row and row['profile'] else None
                    if not social.match_allowed(c,u['id'],int(comparison[1])): return self.reply(404,{'error':'This match is no longer available.'})
                    return self.reply(200,{'name':other['first_name'],'report':match_report(p,other)})
                if self.path=='/api/translation/languages': return self.reply(200,translation.languages())
                if self.path=='/api/me': return self.reply(200,{'id':u['id'],'role':commerce.role(c,u['id']),'email':u['email'],'profile':p,'onboarding':json.loads(c.execute('SELECT data FROM onboarding WHERE user_id=?',(u['id'],)).fetchone()[0]) if c.execute('SELECT 1 FROM onboarding WHERE user_id=?',(u['id'],)).fetchone() else {},'uploaded_photos':[r[0] for r in c.execute('SELECT id FROM photos WHERE user_id=?',(u['id'],))],'overview':overview(p, private=True) if p else None})
                if self.path.startswith('/api/photos/'):
                    photo=c.execute('SELECT * FROM photos WHERE id=?',(self.path.rsplit('/',1)[-1],)).fetchone()
                    if not photo: return self.reply(404,{'error':'Not found.'})
                    if photo['user_id']!=u['id']:
                        owner=c.execute('SELECT profile FROM users WHERE id=?',(photo['user_id'],)).fetchone()
                        other=json.loads(owner['profile']) if owner and owner['profile'] else None
                        if (not social.match_allowed(c,u['id'],photo['user_id']) and not social.candidate(c,u['id'],p,photo['user_id'],other)) or photo['id'] not in (other.get('photos',[]) if social.match_allowed(c,u['id'],photo['user_id']) else other.get('photos',[])[:1]): return self.reply(404,{'error':'Not found.'})
                    self.send_response(200); self.send_header('Content-Type','image/jpeg'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(photo['data']); return
                if self.path=='/api/matches':
                    if not p: return self.reply(400,{'error':'Save your profile first.'})
                    matches=[]
                    for row in c.execute('SELECT id,profile FROM users WHERE id!=? AND profile IS NOT NULL',(u['id'],)):
                        other=json.loads(row['profile'])
                        if social.match_allowed(c,u['id'],row['id']): matches.append({'id':row['id'],'connection_id':social.connection(c,u['id'],row['id'])['id'],'public_profile':social.teaser(c,row,other,matched=True),'name':other['first_name'],'bio':other['bio'],'profile_details':{'age':age(other),**{k:other.get(k,'') for k in ['race','religion','languages'] if k in other.get('visible_details',social.VISIBLE)}},'photos':other.get('photos',[]),'overview':overview(other),'compatibility':compatibility(p,other)})
                    method=p.get('preferred_match','overall'); key=SORT_METHODS.get(method,'score')
                    return self.reply(200,{'preferred_match':method,'matches':sorted(matches,key=lambda m: (m['compatibility'].get(key) if m['compatibility'].get(key) is not None else -1,m['compatibility']['score'],-m['id']),reverse=True)})
                return self.reply(404,{'error':'Not found.'})
        files={'/take.js':'take.js','/':'index.html','/app.js':'app.js','/style.css':'style.css','/logo.png':'logo.png'}
        if re.fullmatch(r'/take/[A-Za-z0-9_-]{40,60}',self.path): files[self.path]='take.html'
        if re.fullmatch(r'/symbols/(me|[1-9][0-9]*)/(sun_sign|chinese_zodiac|life_path|name_number)',self.path): files[self.path]='symbol.html'
        files.update({'/dating':'dating.html','/dating.js':'dating.js','/platform.js':'platform.js','/admin':'admin.html','/admin.js':'admin.js','/marketplace':'marketplace.html','/marketplace.js':'marketplace.js','/download':'download.html','/download.js':'download.js','/icon-192.png':'icon-192.png','/icon-512.png':'icon-512.png','/manifest.webmanifest':'manifest.webmanifest','/sw.js':'sw.js','/community':'community.html','/community.js':'community.js','/mobile.js':'mobile.js','/social.js':'social.js','/symbol.js':'symbol.js','/tools':'tools.html','/tools.js':'tools.js'})
        if self.path not in files: return self.reply(404,{'error':'Not found.'})
        path=Path(__file__).parent/'static'/files[self.path]; self.send_response(200)
        self.send_header('Content-Type',{'html':'text/html; charset=utf-8','js':'text/javascript','css':'text/css','png':'image/png','webmanifest':'application/manifest+json'}[path.suffix[1:]])
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(path.read_bytes())
    def do_POST(self):
        if self.headers.get('Sec-Fetch-Site')=='cross-site': return self.reply(403,{'error':'Cross-site request rejected.'})
        if self.headers.get('Origin') and self.headers['Origin']!=os.environ.get('NEKKED_ORIGIN','http://'+self.headers.get('Host','')): return self.reply(403,{'error':'Origin rejected.'})
        try:
            size=int(self.headers.get('Content-Length',0))
            if not 0<size<=(6000000 if self.path=='/api/media' else 700000 if self.path=='/api/photos' else 60000): raise ValueError('Invalid request size.')
            raw=self.rfile.read(size);data=json.loads(raw); self.cookies=[]
            if not isinstance(data,dict): raise ValueError('Expected an object.')
            with connect() as c:
                webhook=re.fullmatch(r'/api/webhooks/(stripe|paypal|paystack|flutterwave)',self.path)
                if webhook:return self.reply(*commerce.webhook(webhook[1],raw,data,self.headers,c))
                take=re.fullmatch(r'/api/public/take/([A-Za-z0-9_-]{40,60})',self.path)
                if take:
                    invite=c.execute('SELECT * FROM take_invites WHERE token=? AND expires>?',(take[1],time.time())).fetchone()
                    if not invite: return self.reply(404,{'error':'This invitation expired.'})
                    if c.execute('SELECT COUNT(*) FROM friend_takes WHERE user_id=? AND created>?',(invite['user_id'],time.time()-86400)).fetchone()[0]>=10: return self.reply(429,{'error':'Please try later.'})
                    name=social.text(data,'contributor',100,True); text=social.text(data,'text',1000,True)
                    c.execute('INSERT INTO friend_takes(user_id,contributor,text,created) VALUES(?,?,?,?)',(invite['user_id'],name,text,time.time()))
                    return self.reply(200,{'ok':True,'status':'Submitted for profile-owner review.'})
                if self.path in ('/api/register','/api/login'):
                    email=data.get('email','').strip().lower(); password=data.get('password','')
                    if '@' not in email or len(email)>254 or not 12<=len(password)<=128: raise ValueError('Use an email and a password of 12–128 characters.')
                    if self.path=='/api/register':
                        if not commerce.config(c)['registration_open']:return self.reply(403,{'error':'Registration is currently closed.'})
                        if data.get('adult') is not True: raise ValueError('Confirm you are 18 or older.')
                        initial=onboarding_data(data)
                        try:
                            c.execute('BEGIN IMMEDIATE')
                            next_id=c.execute('SELECT value+1 FROM app_identity WHERE id=1').fetchone()[0]
                            c.execute('UPDATE app_identity SET value=? WHERE id=1',(next_id,))
                            created=c.execute('INSERT INTO users(id,email,password) VALUES(?,?,?)',(next_id,email,password_hash(password)))
                            c.execute('INSERT INTO onboarding VALUES(?,?)',(created.lastrowid,json.dumps(initial)))
                        except sqlite3.IntegrityError: raise ValueError('Account cannot be created with that email.')
                    u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
                    if not u or not hmac.compare_digest(password_hash(password,u['password'].split(':')[0]),u['password']): return self.reply(401,{'error':'Invalid email or password.'})
                    if c.execute('SELECT 1 FROM account_controls WHERE user_id=? AND suspended=1',(u['id'],)).fetchone():return self.reply(403,{'error':'This account is suspended. Contact support.'})
                    token=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),u['id'],time.time()+86400))
                    secure='; Secure' if os.environ.get('NEKKED_SECURE_COOKIE')=='1' else ''
                    self.cookies=['session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400'+secure]
                    return self.reply(200,{'ok':True})
                u=self.user(c)
                if not u: return self.reply(401,{'error':'Please sign in.'})
                if self.path=='/api/account/password':
                    old=data.get('current_password'); new=data.get('new_password')
                    if not isinstance(old,str) or not isinstance(new,str) or not 12<=len(new)<=128 or len(old)>128:
                        raise ValueError('Use a new password of 12–128 characters.')
                    c.execute('BEGIN IMMEDIATE')
                    if not social.allowance(c,u['id'],'password_change',5,900):
                        return self.reply(429,{'error':'Please wait before trying again.'})
                    if not hmac.compare_digest(password_hash(old,u['password'].split(':')[0]),u['password']):
                        return self.reply(403,{'error':'Current password is incorrect.'})
                    if old==new: raise ValueError('Choose a different password.')
                    c.execute('UPDATE users SET password=? WHERE id=?',(password_hash(new),u['id']))
                    c.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],))
                    secure='; Secure' if os.environ.get('NEKKED_SECURE_COOKIE')=='1' else ''
                    self.cookies=['session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'+secure]
                    return self.reply(200,{'ok':True,'sign_in_required':True})
                p=json.loads(u['profile']) if u['profile'] else None
                if commerce.config(c)['maintenance'] and not commerce.superuser(c,u['id']) and (self.path=='/api/likes' or self.path.startswith('/api/conversations/')):return self.reply(503,{'error':'The platform is temporarily in maintenance mode.'})
                handled=commerce.dispatch('POST',self.path,data,c,u,lambda password:hmac.compare_digest(password_hash(password,u['password'].split(':')[0]),u['password']))
                if handled is not None:return self.reply(*handled)
                c.execute('BEGIN IMMEDIATE')
                handled=dating.dispatch('POST',self.path,data,c,u,p)
                if handled is not None:return self.reply(*handled)
                handled=social.dispatch('POST',self.path,data,c,u,p)
                if handled is not None: return self.reply(*handled)
                c.commit()
                if self.path=='/api/match-preference':
                    p=json.loads(u['profile']) if u['profile'] else None
                    if not p: return self.reply(400,{'error':'Save your profile first.'})
                    method=data.get('method')
                    if method not in SORT_METHODS: raise ValueError('Invalid matching preference.')
                    p['preferred_match']=method; c.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(p),u['id']))
                    return self.reply(200,{'ok':True})
                message_translation=re.fullmatch(r'/api/conversations/([1-9][0-9]*)/translate',self.path)
                if message_translation:
                    cid=int(message_translation[1])
                    if not social.connection_row(c,u['id'],cid): return self.reply(404,{'error':'This connection is no longer available.'})
                    mid=data.get('message_id'); target=data.get('target')
                    if type(mid) is not int or not isinstance(target,str): raise ValueError('Choose a message and language.')
                    msg=c.execute('SELECT text FROM messages WHERE id=? AND connection_id=?',(mid,cid)).fetchone()
                    if not msg or not msg['text']: return self.reply(404,{'error':'No text to translate.'})
                    try: result=translation.translate_bio(msg['text'],target)
                    except RuntimeError as error: return self.reply(503,{'error':str(error)})
                    return self.reply(200,result)
                translate_route=re.fullmatch(r'/api/matches/([1-9][0-9]*)/translate',self.path)
                if translate_route:
                    p=json.loads(u['profile']) if u['profile'] else None
                    row=c.execute('SELECT profile FROM users WHERE id=? AND id!=?',(int(translate_route[1]),u['id'])).fetchone()
                    other=json.loads(row['profile']) if row and row['profile'] else None
                    if not social.match_allowed(c,u['id'],int(translate_route[1])): return self.reply(404,{'error':'This match is no longer available.'})
                    target=data.get('target')
                    if not isinstance(target,str) or not re.fullmatch('[a-z]{2,3}(?:-[A-Za-z]{2,4})?',target): raise ValueError('Invalid language.')
                    try: result=translation.translate_bio(other['bio'],target)
                    except RuntimeError as error: return self.reply(503,{'error':str(error)})
                    return self.reply(200,result)
                if self.path=='/api/photos':
                    if c.execute('SELECT COUNT(*) FROM photos WHERE user_id=?',(u['id'],)).fetchone()[0]>=commerce.config(c)['max_profile_photos']: raise ValueError('The platform photo limit has been reached.')
                    image=base64.b64decode(data['image'],validate=True)
                    validate_jpeg(image)
                    ident=secrets.token_hex(16); c.execute('INSERT INTO photos VALUES(?,?,?)',(ident,u['id'],image))
                    return self.reply(200,{'id':ident})
                if self.path=='/api/photos/delete':
                    c.execute('DELETE FROM photos WHERE id=? AND user_id=?',(data['id'],u['id']))
                    if u['profile']:
                        p=json.loads(u['profile']); p['photos']=[x for x in p.get('photos',[]) if x!=data['id']]; c.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(p),u['id']))
                    return self.reply(200,{'ok':True})
                if self.path=='/api/profile':
                    p=validate(data)
                    owned={r[0] for r in c.execute('SELECT id FROM photos WHERE user_id=?',(u['id'],))}
                    limits=commerce.config(c)
                    if len(p['photos'])>limits['max_profile_photos'] or (p['discoverable'] and len(p['photos'])<limits['min_profile_photos']):raise ValueError('Discovery requires between '+str(limits['min_profile_photos'])+' and '+str(limits['max_profile_photos'])+' photos.')
                    if not set(p['photos'])<=owned: raise ValueError('Invalid photo ownership.')
                    owned_media={r[0] for r in c.execute('SELECT id FROM media WHERE user_id=?',(u['id'],))}
                    if not set(p['public_media'])<=owned_media: raise ValueError('Invalid media ownership.')
                    c.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(p),u['id']))
                    return self.reply(200,{'ok':True,'overview':overview(p, private=True)})
                if self.path in ('/api/logout','/api/delete'):
                    c.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],))
                    if self.path=='/api/delete':
                        if commerce.superuser(c,u['id']) and c.execute("SELECT COUNT(*) FROM account_roles WHERE role='super_admin'").fetchone()[0]<=1:return self.reply(400,{'error':'Promote another super admin before deleting this operator account.'})
                        social.delete_user(c,u['id'])
                        c.execute('DELETE FROM onboarding WHERE user_id=?',(u['id'],)); c.execute('DELETE FROM photos WHERE user_id=?',(u['id'],)); c.execute('DELETE FROM users WHERE id=?',(u['id'],))
                    self.cookies=['session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0']; return self.reply(200,{'ok':True})
                return self.reply(404,{'error':'Not found.'})
        except gateways.GatewayError as error:self.reply(502,{'error':str(error)})
        except (ValueError,TypeError,KeyError): self.reply(400,{'error':'Invalid input. Check dates and complete required fields.'})
    def log_message(self,*args): pass
if __name__=='__main__':
    with connect(): pass
    ThreadingHTTPServer((os.environ.get('NEKKED_HOST','127.0.0.1'),int(os.environ.get('PORT','8000'))),Handler).serve_forever()
