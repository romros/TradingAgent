from lab.sq_bridge.nflx_train_representatives_v1 import select
def test_selection_never_duplicates_structural_or_entry_family():
 rows=[]
 for i in range(7):rows.append({'strategy':f'S{i}','file':f'S{i}.sqx','sqx_sha256':str(i),'structural_family_sha256':f'f{i//2}','entry_indicator_archetype_sha256':f'e{i//2}','trades':40,'profit':100-i,'drawdown':20,'profit_drawdown_ratio':5-i/10,'fitness':1,'complexity':2,'entry_indicator_types':[]})
 r=select({'pareto_candidates':[x['strategy'] for x in rows],'candidates':rows,'source_inventory_sha256':'x'});assert r['selected_count']==4;assert len({x['structural_family_sha256'] for x in r['selected']})==4
