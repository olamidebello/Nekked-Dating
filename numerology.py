"""Original, transparent numerology tools. No third-party service calls or stored tool inputs."""
from collections import Counter
from datetime import date
import unicodedata
from matching import reduce_number, reduction_steps, NUMBER_MEANINGS

CHALDEAN={letter:value for value,letters in enumerate(['AIJQY','BKR','CGLS','DMT','EHNX','UVW','OZ','FP'],1) for letter in letters}
NOTICE='Symbolic entertainment and self-reflection only. These numbers do not determine personality, compatibility, future events or business outcomes.'

def root(n):
    while n>9: n=sum(map(int,str(n)))
    return n

def letters(name):
    return [c for c in unicodedata.normalize('NFKD',name).upper() if 'A'<=c<='Z']

def reading(total, method, available=True, master=True):
    number=(reduce_number(total) if master else root(total)) if available else None
    return {'number':number,'compound':total if available else None,'steps':reduction_steps(total) if available and master else (f'{total} → {number}' if available else 'No supported letters.'),'method':method,'meaning':NUMBER_MEANINGS.get(number,'Unavailable for these inputs.')}

def word_breakdown(text):
    result=[]
    for word in text.split():
        chars=letters(word)
        if chars: result.append({'word':word,'pythagorean':sum((ord(c)-65)%9+1 for c in chars),'chaldean':sum(CHALDEAN[c] for c in chars)})
    return result

def chart(data):
    if not isinstance(data,dict): raise ValueError('Invalid chart input.')
    name=data.get('name',''); business=data.get('business_name','')
    if not isinstance(name,str) or len(name)>200 or not isinstance(business,str) or len(business)>200: raise ValueError('Names must be at most 200 characters.')
    if not data.get('birth_date'): return name_chart(data)
    dob=date.fromisoformat(data['birth_date'])
    if dob>date.today(): raise ValueError('Birth date cannot be in the future.')
    target=date.fromisoformat(data.get('target_date') or date.today().isoformat())
    if not 1900<=target.year<=2200: raise ValueError('Choose a target year from 1900 to 2200.')
    y_vowel=data.get('y_vowel',False)
    if type(y_vowel) is not bool: raise ValueError('Invalid Y option.')
    method=data.get('life_path_method','components')
    if method not in ('components','all_digits'): raise ValueError('Invalid life-path method.')
    chars=letters(name); values=[(ord(c)-65)%9+1 for c in chars]
    vowels='AEIOUY' if y_vowel else 'AEIOU'
    vowel_values=[v for c,v in zip(chars,values) if c in vowels]; consonants=[v for c,v in zip(chars,values) if c not in vowels]
    month,day,year=map(reduce_number,(dob.month,dob.day,dob.year))
    life_total=month+day+year if method=='components' else sum(int(c) for c in dob.isoformat() if c.isdigit())
    py_total=reduce_number(dob.month)+reduce_number(dob.day)+reduce_number(target.year)
    core={
      'life_path':reading(life_total, f'{method}: '+(f'month {dob.month} → {month}; day {dob.day} → {day}; year {dob.year} → {year}; then add.' if method=='components' else 'Add all birth-date digits at once.')),
      'expression':reading(sum(values),'Pythagorean values of all supported name letters.',bool(chars)),
      'soul_urge':reading(sum(vowel_values),'Pythagorean values of vowels; Y is '+('a vowel.' if y_vowel else 'a consonant.'),bool(vowel_values)),
      'personality':reading(sum(consonants),'Pythagorean values of consonants.',bool(consonants)),
      'birthday':reading(dob.day,'Reduce the day of the month.'),
      'personal_year':reading(py_total,f'Reduced birth month + birth day + selected calendar year {target.year}.'),
    }
    core['personal_month']=reading(core['personal_year']['number']+target.month,'Personal year + selected calendar month.')
    core['personal_day']=reading(core['personal_month']['number']+target.day,'Personal month + selected calendar day.')
    core['maturity']=reading(core['life_path']['number']+(core['expression']['number'] or 0),'Life path + expression.',bool(chars))
    core['chaldean']=reading(sum(CHALDEAN[c] for c in chars),'Chaldean 1–8 mapping; compound retained, final root reduced without master-number stops.',bool(chars),False)
    bc=letters(business)
    core['business_pythagorean']=reading(sum((ord(c)-65)%9+1 for c in bc),'Pythagorean business-name letter sum.',bool(bc))
    core['business_chaldean']=reading(sum(CHALDEAN[c] for c in bc),'Chaldean business-name letter sum; reduce to one digit.',bool(bc),False)
    counts=Counter(values); digits=Counter(int(c) for c in dob.isoformat() if c.isdigit() and c!='0')
    a,b,c=map(root,(dob.month,dob.day,dob.year))
    p1,p2=reduce_number(month+day),reduce_number(day+year)
    pinnacle_values=[p1,p2,reduce_number(p1+p2),reduce_number(month+year)]
    challenge_values=[abs(a-b),abs(b-c),abs(abs(a-b)-abs(b-c)),abs(a-c)]
    end=36-root(core['life_path']['number'])
    ranges=[(0,end),(end+1,end+9),(end+10,end+18),(end+19,None)]
    periods=[{'stage':i+1,'ages':f'{start}–{finish}' if finish is not None else f'{start}+','pinnacle':n,'meaning':NUMBER_MEANINGS[n],'challenge':challenge_values[i]} for i,(n,(start,finish)) in enumerate(zip(pinnacle_values,ranges))]
    debt=set()
    for item in core.values():
        total=item['compound']
        while total is not None:
            if total in (13,14,16,19): debt.add(total)
            if total<=9 or total in (11,22,33): break
            total=sum(map(int,str(total)))
    highest=max(counts.values(),default=0)
    return {'core':core,'letter_breakdown':[{'letter':c,'pythagorean':v,'chaldean':CHALDEAN[c],'vowel':c in vowels} for c,v in zip(chars,values)],'word_breakdown':word_breakdown(name),'business_word_breakdown':word_breakdown(business),'target_date':target.isoformat(),'life_path_method':method,'y_vowel':y_vowel,
      'hidden_passions':[n for n,count in sorted(counts.items()) if count==highest],
      'karmic_lessons':[n for n in range(1,10) if n not in counts] if chars else [],
      'karmic_debts':sorted(debt),'periods':periods,
      'lo_shu':{'layout':[[4,9,2],[3,5,7],[8,1,6]],'counts':{str(n):digits[n] for n in range(1,10)},'missing':[n for n in range(1,10) if not digits[n]],'repeated':[n for n in range(1,10) if digits[n]>1],'method':'Count nonzero birth-date digits; place repeats in the traditional 4-9-2 / 3-5-7 / 8-1-6 square. Zero is omitted.'},
      'notice':NOTICE,'storage':'These calculator inputs are processed on this server for the response and are not saved to your account or database.'}

def number_pair(a,b):
    allowed=set(range(1,10))|{11,22,33}
    if type(a) is not int or type(b) is not int or a not in allowed or b not in allowed: raise ValueError('Choose numbers 1–9, 11, 22 or 33.')
    x,y=root(a),root(b)
    shared=x==y; score=90 if shared else 60
    return {'first':a,'second':b,'score':score,'first_meaning':NUMBER_MEANINGS[a],'second_meaning':NUMBER_MEANINGS[b],'theme':'Shared root themes can offer common language.' if shared else 'Different themes invite a discussion of your individual needs.', 'conversation':'Ask how each person prefers to show care, handle responsibilities and resolve disagreement.', 'method':'Reduce master numbers to single-digit roots for this standalone pair guide: equal roots 90, otherwise 60. Profile ranking retains its existing exact life-path equality rule. Scores are entertainment rules, not measured probabilities.'}

def angel(sequence):
    if not isinstance(sequence,str) or not sequence.isascii() or not sequence.isdigit() or not 1<=len(sequence)<=12: raise ValueError('Enter 1–12 digits.')
    n=root(sum(map(int,sequence)))
    return {'sequence':sequence,'root':n,'meaning':NUMBER_MEANINGS.get(n,'Zero: a prompt to pause and consider a fresh starting point.'),'reflection':'What were you thinking about when you noticed this sequence? Use it as a reminder to reflect, without treating it as a message or prediction.','method':'Sum the sequence digits and reduce to a single digit; repeating digits remain visible in the original sequence. This is an original reflection tool, not a claim about supernatural messages.'}

def name_chart(data):
    name=data.get('name',''); business=data.get('business_name',''); y=data.get('y_vowel',False)
    if type(y) is not bool: raise ValueError('Invalid Y option.')
    chars=letters(name); bc=letters(business)
    if not chars and not bc: raise ValueError('Provide a birth date or a name with supported Latin letters.')
    values=[(ord(c)-65)%9+1 for c in chars]; vowels='AEIOUY' if y else 'AEIOU'
    vs=[v for c,v in zip(chars,values) if c in vowels]; cs=[v for c,v in zip(chars,values) if c not in vowels]
    counts=Counter(values); highest=max(counts.values(),default=0)
    return {'core':{
        'expression':reading(sum(values),'All Pythagorean name letters.',bool(chars)),
        'soul_urge':reading(sum(vs),'Vowels; Y is '+('a vowel.' if y else 'a consonant.'),bool(vs)),
        'personality':reading(sum(cs),'Consonants.',bool(cs)),
        'chaldean':reading(sum(CHALDEAN[c] for c in chars),'Chaldean compound and single-digit root.',bool(chars),False),
        'business_pythagorean':reading(sum((ord(c)-65)%9+1 for c in bc),'Business-name Pythagorean letter sum.',bool(bc)),
        'business_chaldean':reading(sum(CHALDEAN[c] for c in bc),'Business-name Chaldean letter sum.',bool(bc),False)},
        'letter_breakdown':[{'letter':c,'pythagorean':v,'chaldean':CHALDEAN[c],'vowel':c in vowels} for c,v in zip(chars,values)],
        'word_breakdown':word_breakdown(name),'business_word_breakdown':word_breakdown(business),
        'hidden_passions':[n for n,count in sorted(counts.items()) if count==highest],
        'karmic_lessons':[n for n in range(1,10) if n not in counts] if chars else [],
        'karmic_debts':[], 'periods':[], 'lo_shu':None,'notice':NOTICE,
        'storage':'Processed on this server for this response; not saved to the database.'}
