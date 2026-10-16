"""Local discovery, explicit mutual matches, messaging and safety workflows."""
import json, os, time
from datetime import datetime, timezone
from matching import eligible, compatibility, age
import media_store
import commerce

SCHEMA='''
CREATE TABLE IF NOT EXISTS account_roles(user_id INTEGER PRIMARY KEY,role TEXT);
CREATE TABLE IF NOT EXISTS media(id TEXT PRIMARY KEY,user_id INTEGER,type TEXT,data BLOB,created REAL);
CREATE TABLE IF NOT EXISTS thoughts(user_id INTEGER PRIMARY KEY,text TEXT,created REAL);
CREATE TABLE IF NOT EXISTS poll_votes(actor INTEGER,owner INTEGER,choice INTEGER,PRIMARY KEY(actor,owner));
CREATE TABLE IF NOT EXISTS take_invites(token TEXT PRIMARY KEY,user_id INTEGER,expires REAL);
CREATE TABLE IF NOT EXISTS friend_takes(id INTEGER PRIMARY KEY,user_id INTEGER,contributor TEXT,text TEXT,status TEXT DEFAULT 'pending',created REAL);

CREATE TABLE IF NOT EXISTS interests(id INTEGER PRIMARY KEY,sender INTEGER,recipient INTEGER,kind TEXT,target TEXT,comment TEXT,strength TEXT,status TEXT DEFAULT 'pending',created REAL,UNIQUE(sender,recipient));
CREATE TABLE IF NOT EXISTS connections(id INTEGER PRIMARY KEY,low_id INTEGER,high_id INTEGER,active INTEGER DEFAULT 1,created REAL,UNIQUE(low_id,high_id));
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,connection_id INTEGER,sender INTEGER,text TEXT,created REAL);
CREATE TABLE IF NOT EXISTS blocks(actor INTEGER,target INTEGER,created REAL,PRIMARY KEY(actor,target));
CREATE TABLE IF NOT EXISTS passes(actor INTEGER,target INTEGER,created REAL,PRIMARY KEY(actor,target));
CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY,reporter INTEGER,target INTEGER,reason TEXT,detail TEXT,status TEXT DEFAULT 'open',created REAL);
CREATE TABLE IF NOT EXISTS account_settings(user_id INTEGER PRIMARY KEY,data TEXT);
CREATE TABLE IF NOT EXISTS connection_settings(user_id INTEGER,connection_id INTEGER,hidden INTEGER DEFAULT 0,note TEXT DEFAULT '',feedback TEXT DEFAULT '',PRIMARY KEY(user_id,connection_id));
CREATE TABLE IF NOT EXISTS action_log(user_id INTEGER,action TEXT,created REAL);
CREATE TABLE IF NOT EXISTS notices(id INTEGER PRIMARY KEY,user_id INTEGER,text TEXT,seen INTEGER DEFAULT 0,created REAL);
CREATE TABLE IF NOT EXISTS support_requests(id INTEGER PRIMARY KEY,user_id INTEGER,subject TEXT,detail TEXT,status TEXT DEFAULT 'open',created REAL);
CREATE TABLE IF NOT EXISTS success_stories(id INTEGER PRIMARY KEY,user_id INTEGER,story TEXT,status TEXT DEFAULT 'pending',created REAL);
CREATE TABLE IF NOT EXISTS activity(user_id INTEGER PRIMARY KEY,last_active REAL);
'''
DEFAULT_SETTINGS={'paused':False,'show_active':False,'notifications':True,'comment_filter':True,'language':'en','units':'metric'}
VISIBLE=['pronouns','sexuality','job','education','religion','hometown','languages','race','height','children','pets','drinking','smoking','marijuana','drugs','politics','relationship_goal']

def settings(c,uid):
    row=c.execute('SELECT data FROM account_settings WHERE user_id=?',(uid,)).fetchone()
    return DEFAULT_SETTINGS | (json.loads(row[0]) if row else {})

def blocked(c,a,b):
    return bool(c.execute('SELECT 1 FROM blocks WHERE (actor=? AND target=?) OR (actor=? AND target=?)',(a,b,b,a)).fetchone())

def connection(c,a,b,active=True):
    low,high=sorted([a,b]); row=c.execute('SELECT * FROM connections WHERE low_id=? AND high_id=?',(low,high)).fetchone()
    return row if row and (not active or row['active']) and not blocked(c,a,b) else None

def match_allowed(c,a,b): return a!=b and bool(connection(c,a,b)) and not c.execute('SELECT 1 FROM account_controls WHERE user_id IN (?,?) AND suspended=1',(a,b)).fetchone()

def person(c,uid):
    row=c.execute('SELECT id,profile FROM users WHERE id=?',(uid,)).fetchone()
    return row, json.loads(row['profile']) if row and row['profile'] else None

def preference_allowed(c,p,q):
    conf=commerce.config(c)
    def terms(value):return {x.strip().casefold() for x in value.split(',') if x.strip()}
    if not conf['min_profile_photos']<=len(p.get('photos',[]))<=conf['max_profile_photos']:return False
    if conf['allow_match_percentage']:
        from matching import SORT_METHODS
        score=compatibility(p,q).get(SORT_METHODS.get(p.get('preferred_match','overall'),'score'))
        low,high=p.get('match_min_percent',0),p.get('match_max_percent',100)
        if (low>0 or high<100) and (score is None or not low<=score<=high):return False
    if conf['allow_match_location'] and terms(p.get('desired_locations','')) and q.get('current_location','').strip().casefold() not in terms(p['desired_locations']):return False
    if conf['allow_preferred_languages'] and terms(p.get('preferred_languages','')) and not terms(p['preferred_languages']) & terms(q.get('languages','')):return False
    return True

def candidate(c,a,p,b,q):
    return bool(not c.execute('SELECT 1 FROM account_controls WHERE user_id IN (?,?) AND suspended=1',(a,b)).fetchone() and a!=b and p and q and p.get('discoverable') and q.get('discoverable') and eligible(p,q) and preference_allowed(c,p,q) and preference_allowed(c,q,p) and not settings(c,a)['paused'] and not settings(c,b)['paused'] and not blocked(c,a,b) and not connection(c,a,b))

def teaser(c,row,p,matched=False):
    visible=set(p.get('visible_details',VISIBLE))
    data={'id':row['id'],'name':p['first_name'],'age':age(p),'bio':p['bio'],'photos':p.get('photos',[]) if matched else p.get('photos',[])[:1],'prompts':p.get('public_prompts',[]),'details':{k:p[k] for k in VISIBLE if k in visible and p.get(k)}}
    thought=c.execute('SELECT text,created FROM thoughts WHERE user_id=? AND created>?',(row['id'],time.time()-604800)).fetchone()
    if thought: data['thought']=thought['text']
    data['poll']=p.get('poll')
    data['media']=[{'id':r['id'],'type':r['type']} for r in c.execute('SELECT id,type FROM media WHERE user_id=?',(row['id'],)) if r['id'] in p.get('public_media',[])]
    data['friend_takes']=[dict(r) for r in c.execute("SELECT contributor,text FROM friend_takes WHERE user_id=? AND status='visible'",(row['id'],))]
    st=settings(c,row['id']); activity=c.execute('SELECT last_active FROM activity WHERE user_id=?',(row['id'],)).fetchone()
    if st['show_active'] and activity:
        elapsed=time.time()-activity[0]; data['activity']='Active now' if elapsed<300 else 'Active today' if elapsed<86400 else None
    return data

def notify(c,uid,text):
    if settings(c,uid)['notifications']: c.execute('INSERT INTO notices(user_id,text,created) VALUES(?,?,?)',(uid,text,time.time()))

def connection_row(c,uid,cid):
    row=c.execute('SELECT * FROM connections WHERE id=? AND active=1 AND (low_id=? OR high_id=?)',(cid,uid,uid)).fetchone()
    if not row: return None
    if c.execute('SELECT 1 FROM account_controls WHERE user_id IN (?,?) AND suspended=1',(row['low_id'],row['high_id'])).fetchone():return None
    other=row['high_id'] if row['low_id']==uid else row['low_id']
    return (row,other) if not blocked(c,uid,other) else None

def text(data,key,limit,required=False):
    value=data.get(key,'')
    if not isinstance(value,str) or len(value)>limit or (required and not value.strip()): raise ValueError('Invalid '+key)
    return value.strip()

def ident(data,key):
    value=data.get(key)
    if type(value) is not int or value<1: raise ValueError('Invalid '+key)
    return value

def allowance(c,uid,action,limit,seconds):
    membership=commerce.entitlements(c,uid)
    if action in ('like','undo') and membership['tier'] in ('plus','premium'):return True
    count=c.execute('SELECT COUNT(*) FROM action_log WHERE user_id=? AND action=? AND created>?',(uid,action,time.time()-seconds)).fetchone()[0]
    if count>=limit:
        if action=='rose':
            credit=c.execute('SELECT order_id FROM entitlements WHERE user_id=? AND revoked=0 AND expires>? AND roses>0 ORDER BY expires LIMIT 1',(uid,time.time())).fetchone()
            if credit:
                c.execute('UPDATE entitlements SET roses=roses-1 WHERE order_id=? AND roses>0',(credit[0],));return True
        return False
    c.execute('INSERT INTO action_log VALUES(?,?,?)',(uid,action,time.time())); return True

def is_admin(c,u): return bool(c.execute("SELECT 1 FROM account_roles WHERE user_id=? AND role IN ('admin','super_admin')",(u['id'],)).fetchone())

def dispatch(method,path,data,c,u,p):
    uid=u['id']; parts=path.strip('/').split('/')[1:]
    if method=='GET':
        if path=='/api/preview':
            if not p: return 400,{'error':'Save your profile first.'}
            return 200,{'profile':teaser(c,{'id':uid},p,matched=True)}
        if path=='/api/capabilities': return 200,{'messaging':True,'likes':True,'translation':'local','payments':any(x['enabled'] and x['ready'] for x in commerce.gateway_list(c)),'sms_verification':False,'social_login':False,'selfie_verification':False,'voice_video':True}
        if path=='/api/settings': return 200,{'settings':settings(c,uid),'admin':is_admin(c,u)}
        if path in ('/api/discover','/api/standouts'):
            if not p: return 400,{'error':'Save your profile first.'}
            out=[]
            for row in c.execute('SELECT id,profile FROM users WHERE id!=? AND profile IS NOT NULL',(uid,)):
                q=json.loads(row['profile'])
                if not candidate(c,uid,p,row['id'],q): continue
                if c.execute('SELECT 1 FROM passes WHERE actor=? AND target=?',(uid,row['id'])).fetchone(): continue
                if c.execute("SELECT 1 FROM interests WHERE sender=? AND recipient=? AND status='pending'",(uid,row['id'])).fetchone(): continue
                item=teaser(c,row,q); item['_rank']=compatibility(p,q)['score']; out.append(item)
            out.sort(key=lambda x:(x['_rank'],-x['id']),reverse=True)
            if path.endswith('standouts'): out=out[:5]
            for item in out: item.pop('_rank')
            return 200,{'profiles':out,'notice':'Detailed symbols and comparison scores unlock only after an accepted Like or mutual interest.'}
        if path=='/api/likes':
            out=[]
            for row in c.execute("SELECT * FROM interests WHERE recipient=? AND status='pending' ORDER BY CASE strength WHEN 'rose' THEN 0 ELSE 1 END,created DESC",(uid,)):
                other,q=person(c,row['sender'])
                if other and candidate(c,uid,p,other['id'],q): out.append({'id':row['id'],'profile':teaser(c,other,q),'comment':row['comment'],'strength':row['strength'],'kind':row['kind'],'target':row['target'],'created':row['created']})
            return 200,{'likes':out if commerce.entitlements(c,uid)['tier']!='free' else out[:1],'total':len(out)}
        if path=='/api/conversations':
            out=[]
            for row in c.execute('SELECT * FROM connections WHERE active=1 AND (low_id=? OR high_id=?)',(uid,uid)):
                oid=row['high_id'] if row['low_id']==uid else row['low_id']; other,q=person(c,oid)
                if not q or blocked(c,uid,oid): continue
                prefs=c.execute('SELECT * FROM connection_settings WHERE user_id=? AND connection_id=?',(uid,row['id'])).fetchone()
                latest=c.execute('SELECT text,sender,created FROM messages WHERE connection_id=? ORDER BY id DESC LIMIT 1',(row['id'],)).fetchone()
                out.append({'id':row['id'],'profile_id':oid,'name':q['first_name'],'hidden':bool(prefs['hidden']) if prefs else False,'note':prefs['note'] if prefs else '','feedback':prefs['feedback'] if prefs else '','last_message':dict(latest) if latest else None,'your_turn':bool(latest and latest['sender']!=uid)})
            return 200,{'conversations':sorted(out,key=lambda x:x['last_message']['created'] if x['last_message'] else 0,reverse=True)}
        if len(parts)==3 and parts[0]=='conversations' and parts[2]=='messages' and parts[1].isdigit():
            cid=int(parts[1]); pair=connection_row(c,uid,cid)
            if not pair: return 404,{'error':'This connection is no longer available.'}
            rows=c.execute('SELECT id,sender,text,media_id,created FROM messages WHERE connection_id=? ORDER BY id DESC LIMIT 200',(cid,)).fetchall()
            return 200,{'messages':[dict(r)|{'mine':r['sender']==uid} for r in reversed(rows)]}
        if path=='/api/past-connections':
            out=[]
            for row in c.execute('SELECT * FROM connections WHERE active=0 AND (low_id=? OR high_id=?)',(uid,uid)):
                oid=row['high_id'] if row['low_id']==uid else row['low_id']; other,q=person(c,oid)
                if q: out.append({'id':oid,'name':q['first_name']})
            return 200,{'profiles':out}
        if path=='/api/friend-takes': return 200,{'takes':[dict(r) for r in c.execute('SELECT id,contributor,text,status FROM friend_takes WHERE user_id=? ORDER BY id DESC',(uid,))]}
        if path=='/api/my-media': return 200,{'media':[{'id':r['id'],'type':r['type']} for r in c.execute('SELECT id,type FROM media WHERE user_id=?',(uid,))]}
        if path=='/api/notifications': return 200,{'notifications':[dict(r) for r in c.execute('SELECT id,text,seen,created FROM notices WHERE user_id=? ORDER BY id DESC LIMIT 100',(uid,))]}
        if path=='/api/export':
            return 200,{'email':u['email'],'profile':p,'settings':settings(c,uid),'sent_messages':[dict(r) for r in c.execute('SELECT id,connection_id,text,created FROM messages WHERE sender=?',(uid,))],'submitted_reports':[dict(r) for r in c.execute('SELECT target,reason,detail,status,created FROM reports WHERE reporter=?',(uid,))],'photos':p.get('photos',[]) if p else []}
        if path=='/api/support': return 200,{'requests':[dict(r) for r in c.execute('SELECT id,subject,detail,status,created FROM support_requests WHERE user_id=? ORDER BY id DESC',(uid,))]}
        if path=='/api/admin/reports':
            if not is_admin(c,u): return 403,{'error':'Administrator access required.'}
            return 200,{'reports':[dict(r) for r in c.execute('SELECT * FROM reports ORDER BY id DESC')],'support':[dict(r) for r in c.execute('SELECT * FROM support_requests ORDER BY id DESC')],'stories':[dict(r) for r in c.execute('SELECT * FROM success_stories ORDER BY id DESC')]}
        return None
    if method!='POST': return None
    if path=='/api/media/delete':
        mid=text(data,'id',64,True)
        c.execute('DELETE FROM media WHERE id=? AND user_id=?',(mid,uid))
        if p:
            p['public_media']=[x for x in p.get('public_media',[]) if x!=mid]; c.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(p),uid))
        return 200,{'ok':True}
    if path=='/api/media': return 200,media_store.upload(c,uid,data)
    if path=='/api/thought':
        value=text(data,'text',500)
        if value: c.execute('INSERT OR REPLACE INTO thoughts VALUES(?,?,?)',(uid,value,time.time()))
        else: c.execute('DELETE FROM thoughts WHERE user_id=?',(uid,))
        return 200,{'ok':True}
    if path=='/api/poll/vote':
        oid=ident(data,'recipient'); other,q=person(c,oid); choice=data.get('choice')
        if not candidate(c,uid,p,oid,q) and not match_allowed(c,uid,oid): return 404,{'error':'Profile unavailable.'}
        if type(choice) is not int or not q.get('poll') or not 0<=choice<len(q['poll']['options']): raise ValueError('Invalid poll choice.')
        c.execute('INSERT OR REPLACE INTO poll_votes VALUES(?,?,?)',(uid,oid,choice)); return 200,{'ok':True}
    if path=='/api/friend-takes/invite':
        import secrets
        token=secrets.token_urlsafe(32); c.execute('INSERT INTO take_invites VALUES(?,?,?)',(token,uid,time.time()+604800))
        return 200,{'path':'/take/'+token,'expires_days':7}
    if path=='/api/friend-takes/review':
        rid=ident(data,'id'); action=data.get('action')
        if action=='delete': c.execute('DELETE FROM friend_takes WHERE id=? AND user_id=?',(rid,uid))
        elif action in ('visible','hidden'): c.execute('UPDATE friend_takes SET status=? WHERE id=? AND user_id=?',(action,rid,uid))
        else: raise ValueError('Invalid review.')
        return 200,{'ok':True}
    if path=='/api/settings':
        current=settings(c,uid)
        for key in ['paused','show_active','notifications','comment_filter']:
            if key in data:
                if type(data[key]) is not bool: raise ValueError('Invalid setting.')
                current[key]=data[key]
        for key,choices in [('language',('en','es','fr','de','pt','ar','yo')),('units',('metric','imperial'))]:
            if key in data:
                if data[key] not in choices: raise ValueError('Invalid setting.')
                current[key]=data[key]
        c.execute('INSERT OR REPLACE INTO account_settings VALUES(?,?)',(uid,json.dumps(current))); return 200,{'ok':True,'settings':current}
    if path=='/api/presence':
        c.execute('INSERT OR REPLACE INTO activity VALUES(?,?)',(uid,time.time())); return 200,{'ok':True}
    if path=='/api/likes':
        oid=ident(data,'recipient'); other,q=person(c,oid)
        if not candidate(c,uid,p,oid,q): return 404,{'error':'This profile is not available for a new connection.'}
        kind=data.get('kind','profile'); target=text(data,'target',100); comment=text(data,'comment',500); strength=data.get('strength','like')
        if kind not in ('profile','photo','prompt') or strength not in ('like','rose'): raise ValueError('Invalid interest.')
        if kind=='photo' and target not in q.get('photos',[])[:1]: raise ValueError('Unknown photo.')
        if kind=='prompt' and (not target.isdigit() or int(target)>=len(q.get('public_prompts',[]))): raise ValueError('Unknown prompt.')
        if c.execute("SELECT 1 FROM interests WHERE sender=? AND recipient=? AND status='pending'",(uid,oid)).fetchone(): return 409,{'error':'Your interest is already waiting for a reply.'}
        if settings(c,oid)['comment_filter'] and any(word in comment.lower().split() for word in ['fuck','shit','bitch']): return 400,{'error':'Please rephrase your comment respectfully.'}
        if not allowance(c,uid,'rose' if strength=='rose' else 'like',1 if strength=='rose' else 8,604800 if strength=='rose' else 86400): return 429,{'error':'Your free interest allowance has been used. Please try again after it resets.'}
        now=time.time(); c.execute('INSERT INTO interests(sender,recipient,kind,target,comment,strength,created) VALUES(?,?,?,?,?,?,?) ON CONFLICT(sender,recipient) DO UPDATE SET kind=excluded.kind,target=excluded.target,comment=excluded.comment,strength=excluded.strength,status=\'pending\',created=excluded.created',(uid,oid,kind,target,comment,strength,now))
        incoming=c.execute("SELECT id FROM interests WHERE sender=? AND recipient=? AND status='pending'",(oid,uid)).fetchone()
        if incoming:
            return accept(c,uid,oid,p,q)
        notify(c,oid,'Someone sent you a Rose.' if strength=='rose' else 'Someone liked your profile.')
        return 200,{'ok':True,'matched':False}
    if len(parts)==3 and parts[0]=='likes' and parts[1].isdigit() and parts[2] in ('accept','decline'):
        interest=c.execute("SELECT * FROM interests WHERE id=? AND recipient=? AND status='pending'",(int(parts[1]),uid)).fetchone()
        if not interest: return 404,{'error':'This interest is no longer available.'}
        if parts[2]=='decline':
            c.execute("UPDATE interests SET status='declined' WHERE id=?",(interest['id'],)); return 200,{'ok':True}
        other,q=person(c,interest['sender'])
        if not candidate(c,uid,p,interest['sender'],q): return 404,{'error':'This profile is no longer available.'}
        return accept(c,uid,interest['sender'],p,q,text(data,'message',2000))
    if path=='/api/discover/skip':
        oid=ident(data,'recipient'); other,q=person(c,oid)
        if not candidate(c,uid,p,oid,q): return 404,{'error':'Profile unavailable.'}
        c.execute('INSERT OR REPLACE INTO passes VALUES(?,?,?)',(uid,oid,time.time())); return 200,{'ok':True}
    if path=='/api/discover/undo':
        row=c.execute('SELECT target FROM passes WHERE actor=? ORDER BY created DESC LIMIT 1',(uid,)).fetchone()
        if not row: return 400,{'error':'There is no skipped profile to undo.'}
        if not allowance(c,uid,'undo',1,604800): return 429,{'error':'Your free weekly Undo has been used.'}
        c.execute('DELETE FROM passes WHERE actor=? AND target=?',(uid,row[0])); return 200,{'ok':True}
    if len(parts)==3 and parts[0]=='conversations' and parts[1].isdigit():
        cid=int(parts[1]); pair=connection_row(c,uid,cid)
        if not pair: return 404,{'error':'This connection is no longer available.'}
        action=parts[2]
        if action=='messages':
            message=text(data,'text',2000); media_id=data.get('media_id','')
            if not isinstance(media_id,str) or len(media_id)>64 or (not message and not media_id): raise ValueError('Write a message or attach audio.')
            if media_id and not c.execute("SELECT 1 FROM media WHERE id=? AND user_id=? AND type LIKE 'audio/%'",(media_id,uid)).fetchone(): raise ValueError('Invalid voice note.')
            if not allowance(c,uid,'message',30,60): return 429,{'error':'Please wait before sending more messages.'}
            c.execute('INSERT INTO messages(connection_id,sender,text,media_id,created) VALUES(?,?,?,?,?)',(cid,uid,message,media_id,time.time())); notify(c,pair[1],'You have a new message.'); return 200,{'ok':True}
        if action=='unmatch':
            c.execute('UPDATE connections SET active=0 WHERE id=?',(cid,)); return 200,{'ok':True}
        if action in ('hide','note','feedback'):
            c.execute('INSERT OR IGNORE INTO connection_settings(user_id,connection_id) VALUES(?,?)',(uid,cid))
            if action=='hide':
                value=data.get('hidden',True)
                if type(value) is not bool: raise ValueError('Invalid visibility.')
                c.execute('UPDATE connection_settings SET hidden=? WHERE user_id=? AND connection_id=?',(value,uid,cid))
            else: c.execute('UPDATE connection_settings SET '+action+'=? WHERE user_id=? AND connection_id=?',(text(data,action,1000),uid,cid))
            return 200,{'ok':True}
    if path in ('/api/block','/api/report'):
        oid=ident(data,'recipient')
        if oid==uid or not c.execute('SELECT 1 FROM users WHERE id=?',(oid,)).fetchone(): raise ValueError('Invalid profile.')
        if path=='/api/report':
            reason=text(data,'reason',100,True); detail=text(data,'detail',2000)
            row=c.execute('INSERT INTO reports(reporter,target,reason,detail,created) VALUES(?,?,?,?,?)',(uid,oid,reason,detail,time.time())); return 200,{'ok':True,'report_id':row.lastrowid}
        c.execute('INSERT OR REPLACE INTO blocks VALUES(?,?,?)',(uid,oid,time.time()))
        low,high=sorted([uid,oid]); c.execute('UPDATE connections SET active=0 WHERE low_id=? AND high_id=?',(low,high)); return 200,{'ok':True}
    if path=='/api/notifications/read':
        c.execute('UPDATE notices SET seen=1 WHERE user_id=?',(uid,)); return 200,{'ok':True}
    if path=='/api/support':
        subject=text(data,'subject',200,True); detail=text(data,'detail',3000,True)
        row=c.execute('INSERT INTO support_requests(user_id,subject,detail,created) VALUES(?,?,?,?)',(uid,subject,detail,time.time())); return 200,{'ok':True,'id':row.lastrowid}
    if path=='/api/success-story':
        story=text(data,'story',3000,True); row=c.execute('INSERT INTO success_stories(user_id,story,created) VALUES(?,?,?)',(uid,story,time.time())); return 200,{'ok':True,'id':row.lastrowid,'status':'pending review'}
    if path=='/api/admin/review':
        if not is_admin(c,u): return 403,{'error':'Administrator access required.'}
        table=data.get('type'); status=data.get('status'); rid=ident(data,'id')
        if table not in ('reports','support_requests','success_stories') or status not in ('open','resolved','dismissed','approved','rejected'): raise ValueError('Invalid review.')
        c.execute('UPDATE '+table+' SET status=? WHERE id=?',(status,rid)); return 200,{'ok':True}
    return None

def accept(c,a,b,p,q,opening=''):
    # Both an accepted incoming Like and reciprocal Likes are explicit mutual consent.
    existing=connection(c,a,b)
    if existing:return 200,{'ok':True,'matched':True,'connection_id':existing['id']}
    for uid in (a,b):
        quota=commerce.match_quota(c,uid)
        if quota['remaining']==0:
            return 409,{'error':'Your free plan has reached 10 new matches this month. Visit Marketplace to upgrade or wait until next month.' if uid==a else 'This member has reached their monthly match limit. This interest can be accepted after their limit resets or they upgrade.','code':'monthly_match_limit','upgrade_url':'/marketplace','resets_at':quota['resets_at']}
    low,high=sorted([a,b]); now=time.time()
    c.executemany('INSERT INTO monthly_match_events VALUES(?,?,?)',[(a,b,now),(b,a,now)])
    c.execute('INSERT INTO connections(low_id,high_id,created) VALUES(?,?,?) ON CONFLICT(low_id,high_id) DO UPDATE SET active=1,created=excluded.created',(low,high,now))
    c.execute("UPDATE interests SET status='accepted' WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?)",(a,b,b,a))
    row=connection(c,a,b)
    if opening: c.execute('INSERT INTO messages(connection_id,sender,text,created) VALUES(?,?,?,?)',(row['id'],a,opening,time.time()))
    notify(c,a,'You have a new match.'); notify(c,b,'You have a new match.')
    return 200,{'ok':True,'matched':True,'connection_id':row['id']}

def delete_user(c,uid):
    c.execute('DELETE FROM monthly_match_events WHERE user_id=?',(uid,))
    c.execute('DELETE FROM entitlements WHERE user_id=?',(uid,))
    c.execute('DELETE FROM account_controls WHERE user_id=?',(uid,))
    c.execute('UPDATE orders SET user_id=NULL WHERE user_id=?',(uid,))
    c.execute('UPDATE refund_requests SET user_id=NULL WHERE user_id=?',(uid,))
    c.execute('UPDATE audit_events SET actor=NULL WHERE actor=?',(uid,))
    row=c.execute('SELECT email FROM users WHERE id=?',(uid,)).fetchone()
    if row:c.execute('DELETE FROM access_intents WHERE email=?',(row[0],))
    for table,key in [('account_roles','user_id'),('account_settings','user_id'),('connection_settings','user_id'),('action_log','user_id'),('notices','user_id'),('support_requests','user_id'),('success_stories','user_id'),('activity','user_id'),('messages','sender'),('media','user_id'),('thoughts','user_id'),('take_invites','user_id'),('friend_takes','user_id')]: c.execute('DELETE FROM '+table+' WHERE '+key+'=?',(uid,))
    for table,a,b in [('interests','sender','recipient'),('blocks','actor','target'),('passes','actor','target')]: c.execute('DELETE FROM '+table+' WHERE '+a+'=? OR '+b+'=?',(uid,uid))
    c.execute('DELETE FROM poll_votes WHERE actor=? OR owner=?',(uid,uid))
    c.execute('UPDATE connections SET active=0 WHERE low_id=? OR high_id=?',(uid,uid))
    c.execute('UPDATE reports SET reporter=NULL WHERE reporter=?',(uid,)); c.execute('UPDATE reports SET target=NULL WHERE target=?',(uid,))
