import base64, struct, re
import hashlib, hmac, json, os, secrets, sqlite3, time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from http.cookies import SimpleCookie
from matching import overview, compatibility, eligible
from symbol_details import symbol_detail
DB = os.environ.get('NEKKED_DB','nekked.sqlite3')
CATEGORIES = ['emotional','intimacy','financial','living','moods']
def connect():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.executescript('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE,password TEXT,profile TEXT); CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER,expires REAL); CREATE TABLE IF NOT EXISTS photos(id TEXT PRIMARY KEY,user_id INTEGER,data BLOB);')
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
    extra={}
    allowed={'gender':('woman','man','nonbinary','self-described'),'seeking':('woman','man','nonbinary','any'),'relationship_goal':('long-term','marriage','dating','friendship','open-to-exploring'),'children':('','prefer-not-to-say','want-children','have-children','do-not-want','open'),'smoking':('','prefer-not-to-say','non-smoker','smoker','open')}
    for k,choices in allowed.items():
        v=p.get(k,'')
        if v not in choices and not (v=='' and k not in p): raise ValueError('Invalid '+k)
        extra[k]=v
    for k,limit in [('birth_name',200),('current_location',200),('interests',500)]:
        v=p.get(k,'')
        if not isinstance(v,str) or len(v)>limit: raise ValueError('Invalid '+k)
        extra[k]=v.strip()
    for k,default in [('min_age',18),('max_age',120)]:
        v=p.get(k,default)
        if type(v) is not int or not 18<=v<=120: raise ValueError('Invalid age preference.')
        extra[k]=v
    if extra['min_age']>extra['max_age']: raise ValueError('Age range is reversed.')
    photos=p.get('photos',[])
    if not isinstance(photos,list) or len(photos)>6 or any(not isinstance(x,str) or len(x)>64 for x in photos) or len(set(photos))!=len(photos): raise ValueError('Invalid photos.')
    extra['photos']=photos
    return extra | {k:p[k] for k in ['first_name','last_name','birth_date','birth_location','bio','discoverable','preferences','answers']} | {'birth_time':p.get('birth_time','')}

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
        return c.execute('SELECT users.* FROM users JOIN sessions ON user_id=users.id WHERE token=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
    def do_GET(self):
        if self.path.startswith('/api/'):
            with connect() as c:
                u=self.user(c)
                if not u: return self.reply(401,{'error':'Please sign in.'})
                p=json.loads(u['profile']) if u['profile'] else None
                detail_route=re.fullmatch(r'/api/symbols/(me|[1-9][0-9]*)/(sun_sign|chinese_zodiac|life_path|name_number)',self.path)
                if detail_route:
                    subject,key=detail_route.groups()
                    if subject=='me':
                        if not p: return self.reply(400,{'error':'Save your profile first.'})
                        return self.reply(200,{'subject':'Your profile','detail':symbol_detail(p,key,private=True)})
                    row=c.execute('SELECT profile FROM users WHERE id=? AND id!=?',(int(subject),u['id'])).fetchone()
                    other=json.loads(row['profile']) if row and row['profile'] else None
                    if not p or not other or not p['discoverable'] or not other['discoverable'] or not eligible(p,other): return self.reply(404,{'error':'This match is no longer available.'})
                    return self.reply(200,{'subject':other['first_name'],'detail':symbol_detail(other,key)})
                if self.path=='/api/me': return self.reply(200,{'email':u['email'],'profile':p,'uploaded_photos':[r[0] for r in c.execute('SELECT id FROM photos WHERE user_id=?',(u['id'],))],'overview':overview(p, private=True) if p else None})
                if self.path.startswith('/api/photos/'):
                    photo=c.execute('SELECT * FROM photos WHERE id=?',(self.path.rsplit('/',1)[-1],)).fetchone()
                    if not photo: return self.reply(404,{'error':'Not found.'})
                    if photo['user_id']!=u['id']:
                        owner=c.execute('SELECT profile FROM users WHERE id=?',(photo['user_id'],)).fetchone()
                        other=json.loads(owner['profile']) if owner and owner['profile'] else None
                        if not p or not other or not p['discoverable'] or not other['discoverable'] or not eligible(p,other) or photo['id'] not in other.get('photos',[]): return self.reply(404,{'error':'Not found.'})
                    self.send_response(200); self.send_header('Content-Type','image/jpeg'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(photo['data']); return
                if self.path=='/api/matches':
                    if not p: return self.reply(400,{'error':'Save your profile first.'})
                    matches=[]
                    for row in c.execute('SELECT id,profile FROM users WHERE id!=? AND profile IS NOT NULL',(u['id'],)):
                        other=json.loads(row['profile'])
                        if p['discoverable'] and other['discoverable'] and eligible(p,other): matches.append({'id':row['id'],'name':other['first_name'],'bio':other['bio'],'photos':other.get('photos',[]),'overview':overview(other),'compatibility':compatibility(p,other)})
                    return self.reply(200,{'matches':sorted(matches,key=lambda m:m['compatibility']['score'],reverse=True)})
                return self.reply(404,{'error':'Not found.'})
        files={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/logo.png':'logo.png'}
        if re.fullmatch(r'/symbols/(me|[1-9][0-9]*)/(sun_sign|chinese_zodiac|life_path|name_number)',self.path): files[self.path]='symbol.html'
        files['/symbol.js']='symbol.js'
        if self.path not in files: return self.reply(404,{'error':'Not found.'})
        path=Path(__file__).parent/'static'/files[self.path]; self.send_response(200)
        self.send_header('Content-Type',{'html':'text/html; charset=utf-8','js':'text/javascript','css':'text/css','png':'image/png'}[path.suffix[1:]])
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(path.read_bytes())
    def do_POST(self):
        if self.headers.get('Sec-Fetch-Site')=='cross-site': return self.reply(403,{'error':'Cross-site request rejected.'})
        if self.headers.get('Origin') and self.headers['Origin']!=os.environ.get('NEKKED_ORIGIN','http://'+self.headers.get('Host','')): return self.reply(403,{'error':'Origin rejected.'})
        try:
            size=int(self.headers.get('Content-Length',0))
            if not 0<size<=(700000 if self.path=='/api/photos' else 20000): raise ValueError('Invalid request size.')
            data=json.loads(self.rfile.read(size)); self.cookies=[]
            with connect() as c:
                if self.path in ('/api/register','/api/login'):
                    email=data.get('email','').strip().lower(); password=data.get('password','')
                    if '@' not in email or len(email)>254 or not 12<=len(password)<=128: raise ValueError('Use an email and a password of 12–128 characters.')
                    if self.path=='/api/register':
                        if data.get('adult') is not True: raise ValueError('Confirm you are 18 or older.')
                        try: c.execute('INSERT INTO users(email,password) VALUES(?,?)',(email,password_hash(password)))
                        except sqlite3.IntegrityError: raise ValueError('Account cannot be created with that email.')
                    u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
                    if not u or not hmac.compare_digest(password_hash(password,u['password'].split(':')[0]),u['password']): return self.reply(401,{'error':'Invalid email or password.'})
                    token=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),u['id'],time.time()+86400))
                    secure='; Secure' if os.environ.get('NEKKED_SECURE_COOKIE')=='1' else ''
                    self.cookies=['session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400'+secure]
                    return self.reply(200,{'ok':True})
                u=self.user(c)
                if not u: return self.reply(401,{'error':'Please sign in.'})
                if self.path=='/api/photos':
                    if c.execute('SELECT COUNT(*) FROM photos WHERE user_id=?',(u['id'],)).fetchone()[0]>=6: raise ValueError('Six photos maximum.')
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
                    if not set(p['photos'])<=owned: raise ValueError('Invalid photo ownership.')
                    c.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(p),u['id']))
                    return self.reply(200,{'ok':True,'overview':overview(p, private=True)})
                if self.path in ('/api/logout','/api/delete'):
                    c.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],))
                    if self.path=='/api/delete':
                        c.execute('DELETE FROM photos WHERE user_id=?',(u['id'],)); c.execute('DELETE FROM users WHERE id=?',(u['id'],))
                    self.cookies=['session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0']; return self.reply(200,{'ok':True})
                return self.reply(404,{'error':'Not found.'})
        except (ValueError,TypeError,KeyError): self.reply(400,{'error':'Invalid input. Check dates and complete required fields.'})
    def log_message(self,*args): pass
if __name__=='__main__':
    with connect(): pass
    ThreadingHTTPServer((os.environ.get('NEKKED_HOST','127.0.0.1'),int(os.environ.get('PORT','8000'))),Handler).serve_forever()
