"""Same-host translation; only matched public bios are submitted by the server."""
import json, os, urllib.request, urllib.error
BASE='http://127.0.0.1:18084'

def provider(path, payload=None):
    body=json.dumps(payload).encode() if payload is not None else None
    request=urllib.request.Request(BASE+path,data=body,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=30 if payload else 3) as response:
        return json.loads(response.read(100000))

def languages():
    try:
        rows=provider('/languages')
        if not isinstance(rows,list): raise ValueError('Invalid language list.')
        return {'available':True,'languages':[{'code':r['code'],'name':r['name'],'targets':r.get('targets',[])} for r in rows if isinstance(r,dict) and isinstance(r.get('code'),str) and isinstance(r.get('name'),str)]}
    except (OSError,ValueError,KeyError):
        return {'available':False,'languages':[],'message':'Translation is not ready on this server. You can still read the original profile.'}

def translate_bio(text,target):
    supported=languages()
    if not supported['available']: raise RuntimeError(supported['message'])
    if target not in {r['code'] for r in supported['languages']}: raise ValueError('Choose an installed translation language.')
    try:
        result=provider('/translate',{'q':text,'source':'auto','target':target,'format':'text'})
        output=result.get('translatedText')
        if not isinstance(output,str): raise ValueError('Missing translation.')
        return {'text':output,'target':target,'notice':'Machine translation may miss tone or meaning. The original is always available.'}
    except (OSError,ValueError): raise RuntimeError('Translation could not be completed. Please try again.')
