"""Original sign-based compatibility, independent of external publishers."""
from matching import SIGNS, ANIMALS, SIGN_MEANINGS, ANIMAL_MEANINGS, overview, compatibility
from symbol_details import ELEMENTS
from numerology import number_pair
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
    return {'first':first,'second':second,'kind':kind,'score':score,'themes':themes,'overview':overview_text,'basis':basis,'communication':'Ask directly whether each person wants listening, reassurance or practical solutions.','living':'Agree on routines, personal space and shared responsibilities.','money':'Discuss saving, spending and financial boundaries using real information.','notice':'Original simplified symbolic rules, not Astrology.com scores or a full birth-chart synastry reading. Not a prediction of relationship success.'}

def match_report(a,b):
    x,y=overview(a),overview(b)
    return {'western_love':zodiac_pair(x['sun_sign'],y['sun_sign']),'western_work':zodiac_pair(x['sun_sign'],y['sun_sign'],'work'),'chinese':zodiac_pair(x['chinese_zodiac'],y['chinese_zodiac'],'chinese'),'numerology':number_pair(x['life_path'],y['life_path']),'preferences':compatibility(a,b)['domains'],'privacy':'Birth dates, names used in calculation and reflection answers are excluded.'}
