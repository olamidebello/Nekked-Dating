"""Opt-in dating rooms and meetup proposals between existing mutual matches."""
import time
from datetime import datetime
import social,commerce
ROOMS={'introductions':'Introductions','dating':'Dating conversations','meetup-ideas':'Meetup ideas'}
SCHEMA='''
CREATE TABLE IF NOT EXISTS dating_room_members(user_id INTEGER,room TEXT,PRIMARY KEY(user_id,room));
CREATE TABLE IF NOT EXISTS dating_room_messages(id INTEGER PRIMARY KEY,room TEXT,sender INTEGER,text TEXT,created REAL,deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS meetup_proposals(id INTEGER PRIMARY KEY,connection_id INTEGER,creator INTEGER,place TEXT,location TEXT,scheduled TEXT,note TEXT,status TEXT DEFAULT 'proposed',created REAL);
'''
IDEAS=[{'name':'Coffee or tea shop','why':'A short daytime visit, clear prices and an easy exit.'},{'name':'Casual restaurant','why':'A public meal with staff nearby; agree on the budget first.'},{'name':'Museum or gallery','why':'Conversation starters in a staffed public setting; check hours and tickets.'},{'name':'Busy park café','why':'A daytime outdoor meeting with people nearby; check weather and accessibility.'}]
def dispatch(method,path,data,c,u,p):
    if not path.startswith('/api/dating/'):return None
    uid=u['id'];parts=path.split('/')[3:]
    if not p:return 400,{'error':'Save your adult profile before joining dating activities.'}
    if commerce.config(c)['maintenance'] and not commerce.superuser(c,uid):return 503,{'error':'Dating activities are temporarily in maintenance mode.'}
    if parts==['meetups']:
        if method=='GET':
            rows=c.execute('SELECT m.* FROM meetup_proposals m JOIN connections x ON x.id=m.connection_id WHERE x.active=1 AND (x.low_id=? OR x.high_id=?) ORDER BY m.created DESC LIMIT 100',(uid,uid)).fetchall()
            return 200,{'ideas':IDEAS,'proposals':[dict(r) for r in rows if social.connection_row(c,uid,r['connection_id'])]}
        cid=social.ident(data,'connection_id')
        if not social.connection_row(c,uid,cid):return 404,{'error':'An active mutual match is required.'}
        place=social.text(data,'place',200,True);location=social.text(data,'location',300,True);scheduled=social.text(data,'scheduled',60,True)
        try:
            dt=datetime.fromisoformat(scheduled.replace('Z','+00:00'))
            if dt.tzinfo is None or dt.timestamp()<=time.time():raise ValueError()
        except ValueError:raise ValueError('Choose a future time including its time zone.')
        if not social.allowance(c,uid,'meetup',10,86400):return 429,{'error':'Please wait before creating more meetup proposals.'}
        c.execute('INSERT INTO meetup_proposals(connection_id,creator,place,location,scheduled,note,created) VALUES(?,?,?,?,?,?,?)',(cid,uid,place,location,scheduled,social.text(data,'note',500),time.time()))
        return 200,{'ok':True}
    if len(parts)==3 and parts[0]=='meetups' and parts[1].isdigit() and parts[2] in ('accept','decline','cancel') and method=='POST':
        row=c.execute('SELECT * FROM meetup_proposals WHERE id=?',(int(parts[1]),)).fetchone()
        if not row or not social.connection_row(c,uid,row['connection_id']):return 404,{'error':'Meetup unavailable.'}
        action=parts[2]
        if (action=='cancel' and uid!=row['creator']) or (action!='cancel' and uid==row['creator']):return 403,{'error':'Only the invited match may accept or decline; the proposer may cancel.'}
        if row['status'] not in (('proposed','accepted') if action=='cancel' else ('proposed',)):return 409,{'error':'This proposal has already been answered.'}
        c.execute('UPDATE meetup_proposals SET status=? WHERE id=?',({'accept':'accepted','decline':'declined','cancel':'cancelled'}[action],row['id']))
        return 200,{'ok':True}
    if not commerce.config(c)['dating_rooms_open']:return 503,{'error':'Community chat rooms are closed.'}
    if parts==['rooms'] and method=='GET':return 200,{'rooms':[{'id':k,'name':v,'joined':bool(c.execute('SELECT 1 FROM dating_room_members WHERE room=? AND user_id=?',(k,uid)).fetchone())} for k,v in ROOMS.items()],'moderator':social.is_admin(c,u)}
    if len(parts)!=3 or parts[0]!='rooms' or parts[1] not in ROOMS:return 404,{'error':'Room unavailable.'}
    room,action=parts[1:]
    if method=='POST' and action in ('join','leave'):
        if action=='join':
            if data.get('consent') is not True:raise ValueError('Agree to share your first name and messages with room members.')
            c.execute('INSERT OR IGNORE INTO dating_room_members VALUES(?,?)',(uid,room))
        else:c.execute('DELETE FROM dating_room_members WHERE user_id=? AND room=?',(uid,room))
        return 200,{'ok':True}
    if not c.execute('SELECT 1 FROM dating_room_members WHERE user_id=? AND room=?',(uid,room)).fetchone():return 403,{'error':'Join this room to read or post.'}
    if action=='messages':
        if method=='GET':
            rows=c.execute('SELECT m.*,u.profile FROM dating_room_messages m JOIN users u ON u.id=m.sender WHERE room=? AND deleted=0 ORDER BY m.id DESC LIMIT 200',(room,)).fetchall()
            import json
            return 200,{'messages':[{'id':r['id'],'sender':r['sender'],'name':json.loads(r['profile'])['first_name'],'text':r['text'],'created':r['created']} for r in reversed(rows) if r['profile'] and not social.blocked(c,uid,r['sender']) and not c.execute('SELECT 1 FROM account_controls WHERE user_id=? AND suspended=1',(r['sender'],)).fetchone()]}
        text=social.text(data,'text',1000,True)
        if not social.allowance(c,uid,'room_message',10,60):return 429,{'error':'Please wait before posting again.'}
        c.execute('INSERT INTO dating_room_messages(room,sender,text,created) VALUES(?,?,?,?)',(room,uid,text,time.time()));return 200,{'ok':True}
    if method=='POST' and action in ('report','delete'):
        message=c.execute('SELECT * FROM dating_room_messages WHERE id=? AND room=? AND deleted=0',(social.ident(data,'message_id'),room)).fetchone()
        if not message or social.blocked(c,uid,message['sender']):return 404,{'error':'Message unavailable.'}
        if action=='report':
            c.execute('INSERT INTO reports(reporter,target,reason,detail,created) VALUES(?,?,?,?,?)',(uid,message['sender'],'Chat room message',room+' #'+str(message['id'])+': '+social.text(data,'reason',500,True)+' | '+message['text'],time.time()))
        else:
            if uid!=message['sender'] and not social.is_admin(c,u):return 403,{'error':'Only the author or a moderator can remove this message.'}
            c.execute('UPDATE dating_room_messages SET deleted=1 WHERE id=?',(message['id'],));commerce.audit(c,uid,'remove_room_message',message['id'])
        return 200,{'ok':True}
    return 404,{'error':'Action unavailable.'}
