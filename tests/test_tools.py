import unittest
from datetime import date
from numerology import chart, number_pair, angel, CHALDEAN
from astrology_tools import zodiac_pair

class CalculatorTests(unittest.TestCase):
    def test_name_arithmetic_and_chaldean(self):
        r=chart({'name':'John','birth_date':'1989-12-17','target_date':'2026-10-16'})
        self.assertEqual(r['core']['expression']['number'],2)
        self.assertEqual(r['core']['soul_urge']['number'],6)
        self.assertEqual(r['core']['personality']['number'],5)
        self.assertEqual(r['core']['chaldean']['compound'],18)
        self.assertEqual(r['core']['chaldean']['number'],9)
        self.assertEqual(r['core']['life_path']['number'],2)
        self.assertEqual(r['core']['birthday']['number'],8)
        self.assertEqual(r['core']['personal_year']['number'],3)
        self.assertEqual(r['core']['personal_month']['number'],4)
        self.assertEqual(r['core']['personal_day']['number'],2)
        self.assertEqual(set(CHALDEAN),set('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
    def test_y_choice_and_unsupported_names(self):
        consonant=chart({'name':'Amy','birth_date':'1990-04-15'})
        vowel=chart({'name':'Amy','birth_date':'1990-04-15','y_vowel':True})
        self.assertEqual(consonant['core']['expression'],vowel['core']['expression'])
        self.assertNotEqual(consonant['core']['soul_urge']['number'],vowel['core']['soul_urge']['number'])
        r=chart({'name':'中文','birth_date':'1990-04-15'})
        self.assertIsNone(r['core']['expression']['number'])
        self.assertEqual(r['hidden_passions'],[])
        self.assertEqual(r['karmic_lessons'],[])
    def test_business_and_name_only(self):
        r=chart({'business_name':'John'})
        self.assertEqual(r['core']['business_pythagorean']['number'],2)
        self.assertEqual(r['core']['business_chaldean']['number'],9)
        self.assertNotIn('life_path',r['core'])
        self.assertIsNone(r['lo_shu'])
        with self.assertRaises(ValueError): chart({'name':'中文'})
    def test_grid_periods_and_master_methods(self):
        r=chart({'birth_date':'1990-04-15','life_path_method':'all_digits'})
        self.assertEqual(r['core']['life_path']['number'],11)
        self.assertEqual(r['lo_shu']['counts']['1'],2)
        self.assertEqual(r['lo_shu']['counts']['9'],2)
        self.assertEqual(r['lo_shu']['missing'],[2,3,6,7,8])
        self.assertEqual(r['periods'][0]['pinnacle'],1)
        self.assertEqual([p['challenge'] for p in r['periods']],[2,5,3,3])
        self.assertEqual(r['periods'][0]['ages'],'0–34')
        for p in r['periods']: self.assertTrue(0<=p['challenge']<=8)
    def test_pair_symmetry_and_invalid_requests(self):
        for a in [1,2,3,4,5,6,7,8,9,11,22,33]:
            for b in [1,2,3,4,5,6,7,8,9,11,22,33]:
                self.assertEqual(number_pair(a,b)['score'],number_pair(b,a)['score'])
        for invalid in [0,10,True,'1',None]:
            with self.assertRaises(ValueError): number_pair(invalid,1)
        for invalid in ['','abc','١١١','1'*13]:
            with self.assertRaises(ValueError): angel(invalid)
        self.assertEqual(angel('111')['root'],3)
        for data in [{'birth_date':'2999-01-01'},{'birth_date':'bad'},{'name':'x'*201},{'name':'John','y_vowel':'yes'},{'birth_date':'1990-01-01','life_path_method':'unknown'}]:
            with self.assertRaises(ValueError): chart(data)
    def test_zodiac_comparison_rules(self):
        self.assertEqual(zodiac_pair('Aries','Leo')['score'],90)
        self.assertEqual(zodiac_pair('Aries','Gemini')['score'],80)
        self.assertEqual(zodiac_pair('Aries','Taurus')['score'],55)
        self.assertEqual(zodiac_pair('Rat','Dragon','chinese')['score'],90)
        self.assertEqual(zodiac_pair('Rat','Horse','chinese')['score'],45)
        self.assertEqual(zodiac_pair('Aries','Leo','work')['kind'],'work')
        for args in [('wrong','Leo'),('Aries','Leo','bad'),('Rat','wrong','chinese')]:
            with self.assertRaises(ValueError): zodiac_pair(*args)
