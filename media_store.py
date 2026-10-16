import base64,secrets,time
TYPES={'audio/webm':b'\x1aE\xdf\xa3','video/webm':b'\x1aE\xdf\xa3','audio/ogg':b'OggS'}

def upload(c,uid,data):
    mime=data.get('type'); encoded=data.get('data')
    if mime not in TYPES or not isinstance(encoded,str): raise ValueError('Choose WebM audio/video or Ogg audio.')
    raw=base64.b64decode(encoded,validate=True)
    if not 8<=len(raw)<=4_000_000 or not raw.startswith(TYPES[mime]): raise ValueError('Invalid media or file too large.')
    totals=c.execute('SELECT COUNT(*),COALESCE(SUM(length(data)),0) FROM media WHERE user_id=?',(uid,)).fetchone()
    if totals[0]>=10 or totals[1]+len(raw)>20_000_000: raise ValueError('Remove an older recording before adding another.')
    ident=secrets.token_hex(16); c.execute('INSERT INTO media VALUES(?,?,?,?,?)',(ident,uid,mime,raw,time.time()))
    return {'id':ident,'type':mime}
