"""Transparent entertainment rules, not psychological assessments."""
from datetime import date
import unicodedata
SIGNS = ['Capricorn','Aquarius','Pisces','Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius']
ANIMALS = ['Monkey','Rooster','Dog','Pig','Rat','Ox','Tiger','Rabbit','Dragon','Snake','Horse','Goat']
def reduce_number(n):
    while n > 9 and n not in (11,22,33):
        n = sum(map(int,str(n)))
    return n

def overview(p, private=False):
    d = date.fromisoformat(p['birth_date'])
    cutoffs = [20,19,21,20,21,21,23,23,23,23,22,22]
    index = (d.month - 1 + (d.day >= cutoffs[d.month-1])) % 12
    name = unicodedata.normalize('NFKD',p.get('birth_name') or (p['first_name']+' '+p['last_name'])).upper()
    number = reduce_number(sum((ord(c)-65)%9+1 for c in name if 'A' <= c <= 'Z'))
    lunar_year = int(d.strftime('%Y'))
    result = {'sun_sign':SIGNS[index], 'chinese_zodiac':ANIMALS[lunar_year%12],
            'chinese_zodiac_note':'Gregorian birth-year approximation; January/February births may differ.',
            'life_path':reduce_number(sum(int(c) for c in p['birth_date'] if c.isdigit())),
            'name_number':number or None,'birth_chart_status':'Sun-sign approximation only; no planetary or ascendant calculation.'}

    result['meanings'] = {
        'sun_sign': SIGN_MEANINGS[result['sun_sign']],
        'chinese_zodiac': ANIMAL_MEANINGS[result['chinese_zodiac']],
        'life_path': NUMBER_MEANINGS[result['life_path']],
        'name_number': NUMBER_MEANINGS.get(number, 'Unavailable: enter a name containing Latin letters.')}
    if private:
        digits = [int(c) for c in p['birth_date'] if c.isdigit()]
        letters = [(c,(ord(c)-65)%9+1) for c in name if 'A' <= c <= 'Z']
        result['breakdown'] = {
            'life_path': ' + '.join(map(str,digits)) + ' = ' + reduction_steps(sum(digits)),
            'name_number': ' + '.join(f'{c}({v})' for c,v in letters) + ' = ' + reduction_steps(sum(v for c,v in letters)) if letters else 'No supported letters.',
            'method': 'Sum all birth-date digits, then reduce. Name number uses A=1 through I=9, repeating J=1 through Z=8. Preserve 11, 22 and 33 at each reduction. Other numerology traditions may use different methods.'}
    return result

def reduction_steps(n):
    steps=[str(n)]
    while n > 9 and n not in (11,22,33):
        n=sum(map(int,str(n))); steps.append(str(n))
    return ' → '.join(steps)

SIGN_MEANINGS = dict(zip(SIGNS, [
    'Earth: responsibility, patience and structure.', 'Air: originality, independence and community.',
    'Water: imagination, empathy and sensitivity.', 'Fire: initiative, courage and energy.',
    'Earth: steadiness, comfort and persistence.', 'Air: curiosity, adaptability and conversation.',
    'Water: care, belonging and emotional connection.', 'Fire: warmth, creativity and confidence.',
    'Earth: practicality, discernment and service.', 'Air: balance, partnership and fairness.',
    'Water: depth, intensity and transformation.', 'Fire: exploration, optimism and freedom.']))
ANIMAL_MEANINGS = dict(zip(ANIMALS, [
    'Ingenuity and playfulness.', 'Care and attention to detail.', 'Loyalty and fairness.',
    'Generosity and enjoyment.', 'Resourcefulness and adaptability.', 'Patience and reliability.',
    'Courage and independence.', 'Gentleness and diplomacy.', 'Vitality and ambition.',
    'Reflection and intuition.', 'Energy and freedom.', 'Creativity and kindness.']))
NUMBER_MEANINGS = {1:'Initiative and independence.',2:'Partnership and diplomacy.',3:'Expression and creativity.',4:'Structure and persistence.',5:'Freedom and adaptability.',6:'Care and responsibility.',7:'Inquiry and reflection.',8:'Organization and ambition.',9:'Compassion and service.',11:'Master number: inspiration and sensitivity.',22:'Master number: vision and practical building.',33:'Master number: compassion and teaching.'}

def compatibility(a,b):
    x,y = overview(a),overview(b)
    # Four classical element groups; same element or fire/air, earth/water pairing.
    elements = {'Aries':0,'Leo':0,'Sagittarius':0,'Taurus':1,'Virgo':1,'Capricorn':1,'Gemini':2,'Libra':2,'Aquarius':2,'Cancer':3,'Scorpio':3,'Pisces':3}
    e,f = elements[x['sun_sign']],elements[y['sun_sign']]
    zodiac = 90 if e==f else 80 if {e,f} in ({0,2},{1,3}) else 55
    delta = (ANIMALS.index(x['chinese_zodiac'])-ANIMALS.index(y['chinese_zodiac']))%12
    chinese = 90 if delta in (4,8) else 45 if delta==6 else 65
    numerology = 90 if x['life_path']==y['life_path'] else 60
    categories = {k:90 if a['preferences'].get(k,a['preferences']['moods'])==b['preferences'].get(k,b['preferences']['moods']) else 50 for k in set(a['preferences']) | set(b['preferences'])}
    for key in ('relationship_goal','children','smoking'):
        if a.get(key) and b.get(key) and 'prefer-not-to-say' not in (a[key],b[key]):
            categories[key]=90 if a[key]==b[key] else 50
    return {'score':round((zodiac+chinese+numerology+sum(categories.values())/len(categories))/4),
            'zodiac':zodiac,'chinese_zodiac':chinese,'numerology':numerology,'categories':categories,
            'domains': {label: {'score':round(sum(categories[k] for k in keys)/len(keys)), 'basis': 'Preference alignment: '+', '.join(keys)} for label,keys in {'Love':['emotional','intimacy'],'Living':['living'],'Money':['financial'],'Communication':['communication' if 'communication' in categories else 'moods']}.items()},
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
