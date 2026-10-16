"""Original sign-based compatibility, independent of external publishers."""
from matching import SIGNS, ANIMALS, SIGN_MEANINGS, ANIMAL_MEANINGS, overview, compatibility
from symbol_details import ELEMENTS
MODALITIES={s:mode for mode,signs in {'Cardinal':['Aries','Cancer','Libra','Capricorn'],'Fixed':['Taurus','Leo','Scorpio','Aquarius'],'Mutable':['Gemini','Virgo','Sagittarius','Pisces']}.items() for s in signs}

def zodiac_pair(first,second,kind='love'):
    if kind not in ('love','work','chinese'): raise ValueError('Invalid compatibility type.')
    if kind=='chinese':
        if first not in ANIMALS or second not in ANIMALS: raise ValueError('Choose valid birth-year animals.')
        delta=(ANIMALS.index(first)-ANIMALS.index(second))%12
        score=90 if delta in (4,8) else 45 if delta==6 else 65
        themes=[ANIMAL_MEANINGS[first],ANIMAL_MEANINGS[second]]
        basis='Animal positions four/eight apart: 90; opposite: 45; all other pairs: 65. Gregorian birth-year approximation; Lunar New Year is not calculated.'
        overview_text='Use the two animal themes as starting points for a conversation about habits, loyalty and independence.'
    else:
        if first not in SIGNS or second not in SIGNS: raise ValueError('Choose valid sun signs.')
        e,f=ELEMENTS[first],ELEMENTS[second]
        score=90 if e==f else 80 if {e,f} in ({'Fire','Air'},{'Earth','Water'}) else 55
        themes=[SIGN_MEANINGS[first],SIGN_MEANINGS[second]]
        basis=f'{first}: {e}, {MODALITIES[first]}; {second}: {f}, {MODALITIES[second]}. Same element: 90; Fire/Air or Earth/Water: 80; other pairings: 55. Modalities describe themes and do not change the score.'
        overview_text=('Discuss planning, feedback and how decisions are shared. ' if kind=='work' else 'Discuss affection, boundaries and the pace of getting to know one another. ')+('Shared elements suggest similar symbolic styles.' if e==f else 'Different symbolic styles can be a useful conversation prompt.')
    return {'first':first,'second':second,'kind':kind,'score':score,'themes':themes,'overview':overview_text,'basis':basis,'communication':'Ask directly whether each person wants listening, reassurance or practical solutions.','living':'Agree on routines, personal space and shared responsibilities.','money':'Discuss saving, spending and financial boundaries using real information.','notice':'Original simplified symbolic rules, not a full birth-chart reading. Not a prediction of relationship success.'}

def match_report(a,b):
    x,y=overview(a),overview(b); scores=compatibility(a,b)
    return {'scores':{k:scores[k] for k in ['score','zodiac','numerology','life_path','chinese_zodiac']},
      'methods':{
        'zodiac':{'title':'Zodiac','you':x['sun_sign'],'match':y['sun_sign'],'score':scores['zodiac'],'simple':'Compares the elements linked with your sun signs. Similar or paired elements receive a higher symbolic score.','detail':zodiac_pair(x['sun_sign'],y['sun_sign'])['basis']},
        'numerology':{'title':'Name numerology','you':x['name_number'],'match':y['name_number'],'score':scores['numerology'],'simple':'Turns each name into a number, then compares the two results.','detail':'Letters A–I use 1–9, repeating for the rest of the alphabet. Add and reduce, keeping 11, 22 or 33. Equal name numbers score 90; different numbers score 60. Unavailable if either name has no supported letters.'},
        'life_path':{'title':'Life path','you':x['life_path'],'match':y['life_path'],'score':scores['life_path'],'simple':'Adds the digits in each birth date and compares the final numbers.','detail':'Add all birth-date digits and repeatedly add the result’s digits, preserving 11, 22 and 33. Equal life paths score 90; different life paths score 60. Birth dates are never shared.'},
        'chinese_zodiac':{'title':'Chinese zodiac','you':x['chinese_zodiac'],'match':y['chinese_zodiac'],'score':scores['chinese_zodiac'],'simple':'Compares the animals linked with your birth years.','detail':zodiac_pair(x['chinese_zodiac'],y['chinese_zodiac'],'chinese')['basis']}},
      'preferences':scores['domains'],'explanation':scores['explanation'],
      'notice':'Symbolic scores are conversation prompts, not predictions of relationship success.'}
