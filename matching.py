"""Transparent entertainment rules, not psychological assessments."""
from datetime import date
import unicodedata
SIGNS = ['Capricorn','Aquarius','Pisces','Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius']
ANIMALS = ['Monkey','Rooster','Dog','Pig','Rat','Ox','Tiger','Rabbit','Dragon','Snake','Horse','Goat']
def reduce_number(n):
    while n > 9 and n not in (11,22,33):
        n = sum(map(int,str(n)))
    return n

def overview(p):
    d = date.fromisoformat(p['birth_date'])
    cutoffs = [20,19,21,20,21,21,23,23,23,23,22,22]
    index = (d.month - 1 + (d.day >= cutoffs[d.month-1])) % 12
    name = unicodedata.normalize('NFKD',p.get('birth_name') or (p['first_name']+' '+p['last_name'])).upper()
    number = reduce_number(sum((ord(c)-65)%9+1 for c in name if 'A' <= c <= 'Z'))
    lunar_year = int(d.strftime('%Y'))
    return {'sun_sign':SIGNS[index], 'chinese_zodiac':ANIMALS[lunar_year%12],
            'chinese_zodiac_note':'Gregorian birth-year approximation; January/February births may differ.',
            'life_path':reduce_number(sum(int(c) for c in p['birth_date'] if c.isdigit())),
            'name_number':number or None,'birth_chart_status':'Sun-sign approximation only; no planetary or ascendant calculation.'}

def compatibility(a,b):
    x,y = overview(a),overview(b)
    # Four classical element groups; same element or fire/air, earth/water pairing.
    elements = {'Aries':0,'Leo':0,'Sagittarius':0,'Taurus':1,'Virgo':1,'Capricorn':1,'Gemini':2,'Libra':2,'Aquarius':2,'Cancer':3,'Scorpio':3,'Pisces':3}
    e,f = elements[x['sun_sign']],elements[y['sun_sign']]
    zodiac = 90 if e==f else 80 if {e,f} in ({0,2},{1,3}) else 55
    delta = (ANIMALS.index(x['chinese_zodiac'])-ANIMALS.index(y['chinese_zodiac']))%12
    chinese = 90 if delta in (4,8) else 45 if delta==6 else 65
    numerology = 90 if x['life_path']==y['life_path'] else 60
    categories = {k:90 if a['preferences'][k]==b['preferences'][k] else 50 for k in a['preferences']}
    for key in ('relationship_goal','children','smoking'):
        if a.get(key) and b.get(key) and 'prefer-not-to-say' not in (a[key],b[key]):
            categories[key]=90 if a[key]==b[key] else 50
    return {'score':round((zodiac+chinese+numerology+sum(categories.values())/len(categories))/4),
            'zodiac':zodiac,'chinese_zodiac':chinese,'numerology':numerology,'categories':categories,
            'explanation':'Equal weights: sun-sign element, birth-year zodiac, life-path number, and stated preferences. Questionnaire reflections do not affect ranking.'}


def eligible(a,b):
    """Mutual age and stated gender preferences; private fields stay private."""
    today=date.today()
    def accepts(p,q):
        d=date.fromisoformat(q['birth_date'])
        age=today.year-d.year-((today.month,today.day)<(d.month,d.day))
        seeking=p.get('seeking','')
        return p.get('min_age',18)<=age<=p.get('max_age',120) and (not seeking or seeking=='any' or seeking==q.get('gender'))
    return accepts(a,b) and accepts(b,a)
