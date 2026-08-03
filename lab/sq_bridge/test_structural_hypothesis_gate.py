from copy import deepcopy
from lab.sq_bridge.structural_hypothesis_gate import sweep_reclaim

def rng(op,computed,period=20):return {'op':op,'params':{'#ComputedFrom#':computed,'#Period#':period,'#Shift#':2}}
def price(op,shift=1):return {'op':op,'params':{'#Chart#':0,'#Shift#':shift}}
def cmp(op,a,b):return {'op':op,'children':[a if isinstance(a,dict) else {'op':a},b if isinstance(b,dict) else {'op':b}]}
def contract():
 return {'strategy_name':'s1','supported':True,'translation_status':'SUPPORTED_SUBSET','entries':{
  'long':{'signal':{'op':'AND','children':[cmp('IsLower',price('Low'),rng('Lowest',3)),cmp('IsGreater',price('Close'),rng('Lowest',3))]}},
  'short':{'signal':{'op':'AND','children':[cmp('IsGreater',price('High'),rng('Highest',2)),cmp('IsLower',price('Close'),rng('Highest',2))]}}}}

def test_exact_sweep_reclaim_passes():assert sweep_reclaim(contract())['passed']
def test_breakout_without_reclaim_fails():
 c=contract();c['entries']['long']['signal']['children'][1]=cmp('IsGreater','Close',rng('Highest',2))
 r=sweep_reclaim(c);assert not r['passed'];assert 'LONG_RECLAIM_SHAPE' in r['reasons']
def test_extra_condition_fails():
 c=contract();c['entries']['short']['signal']['children'].append(cmp('IsGreater','ATR','Number'))
 assert 'SHORT_NOT_EXACTLY_TWO_CONDITIONS' in sweep_reclaim(c)['reasons']
def test_unsupported_translation_fails():
 c=contract();c['supported']=False
 assert 'TRANSLATION_UNSUPPORTED' in sweep_reclaim(c)['reasons']
def test_different_periods_fail_even_with_same_operators():
 c=contract();c['entries']['long']['signal']['children'][1]=cmp('IsGreater','Close',rng('Lowest',3,40))
 assert 'LONG_RANGE_MISMATCH' in sweep_reclaim(c)['reasons']
def test_current_bar_or_wrong_price_series_fails():
 c=contract();c['entries']['short']['signal']['children'][0]['children'][1]['params']['#Shift#']=1
 assert 'SHORT_RANGE_NOT_PRIOR_EXTREME' in sweep_reclaim(c)['reasons']
def test_signal_must_be_last_closed_bar():
 c=contract();c['entries']['long']['signal']['children'][0]['children'][0]['params']['#Shift#']=2
 assert 'LONG_BREAK_NOT_CLOSED_SIGNAL_BAR' in sweep_reclaim(c)['reasons']
