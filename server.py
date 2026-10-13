import hashlib, hmac, json, os, secrets, sqlite3, time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from http.cookies import SimpleCookie
from matching import overview, compatibility, eligible
DB = os.environ.get('NEKKED_DB','nekked.sqlite3')
CATEGORIES = ['emotional','intimacy','financial','living','moods']
def connect():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.executescript('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE,password TEXT,profile TEXT); CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER,expires REAL);')
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
    if set(p.get('preferences',{}))!=set(CATEGORIES) or any(v not in ('similar','flexible','independent') for v in p['preferences'].values()): raise ValueError('Complete compatibility preferences.')
    q=p.get('answers',{})
    for k in ['animal','color','paradise','box']:
        a=q.get(k,{})
        if not isinstance(a.get('choice'),str) or not 1<=len(a['choice'])<=1000: raise ValueError('Complete each reflection.')
        if not isinstance(a.get('words'),list) or len(a['words'])!=3 or any(not isinstance(w,str) or not 1<=len(w.strip())<=80 for w in a['words']): raise ValueError('Provide three words for every reflection.')
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
    return extra | {k:p[k] for k in ['first_name','last_name','birth_date','birth_location','bio','discoverable','preferences','answers']} | {'birth_time':p.get('birth_time','')}

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
                if self.path=='/api/me': return self.reply(200,{'email':u['email'],'profile':p,'overview':overview(p) if p else None})
                if self.path=='/api/matches':
                    if not p: return self.reply(400,{'error':'Save your profile first.'})
                    matches=[]
                    for row in c.execute('SELECT id,profile FROM users WHERE id!=? AND profile IS NOT NULL',(u['id'],)):
                        other=json.loads(row['profile'])
                        if other['discoverable'] and eligible(p,other): matches.append({'id':row['id'],'name':other['first_name'],'bio':other['bio'],'overview':overview(other),'compatibility':compatibility(p,other)})
                    return self.reply(200,{'matches':sorted(matches,key=lambda m:m['compatibility']['score'],reverse=True)})
                return self.reply(404,{'error':'Not found.'})
        files={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/logo.png':'logo.png'}
        if self.path not in files: return self.reply(404,{'error':'Not found.'})
        path=Path(__file__).parent/'static'/files[self.path]; self.send_response(200)
        self.send_header('Content-Type',{'html':'text/html; charset=utf-8','js':'text/javascript','css':'text/css','png':'image/png'}[path.suffix[1:]])
        self.send_header('Content-Security-Policy',"default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(path.read_bytes())
    def do_POST(self):
        if self.headers.get('Sec-Fetch-Site')=='cross-site': return self.reply(403,{'error':'Cross-site request rejected.'})
        if self.headers.get('Origin') and self.headers['Origin']!=os.environ.get('NEKKED_ORIGIN','http://'+self.headers.get('Host','')): return self.reply(403,{'error':'Origin rejected.'})
        try:
            size=int(self.headers.get('Content-Length',0))
            if not 0<size<=20000: raise ValueError('Invalid request size.')
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
                if self.path=='/api/profile':
                    p=validate(data); c.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(p),u['id']))
                    return self.reply(200,{'ok':True,'overview':overview(p)})
                if self.path in ('/api/logout','/api/delete'):
                    c.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],))
                    if self.path=='/api/delete': c.execute('DELETE FROM users WHERE id=?',(u['id'],))
                    self.cookies=['session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0']; return self.reply(200,{'ok':True})
                return self.reply(404,{'error':'Not found.'})
        except (ValueError,TypeError,KeyError): self.reply(400,{'error':'Invalid input. Check dates and complete required fields.'})
    def log_message(self,*args): pass
if __name__=='__main__':
    with connect(): pass
    ThreadingHTTPServer((os.environ.get('NEKKED_HOST','127.0.0.1'),int(os.environ.get('PORT','8000'))),Handler).serve_forever()
