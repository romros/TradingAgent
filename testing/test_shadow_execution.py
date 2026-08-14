import json
from pathlib import Path
from packages.execution.shadow import ShadowIntent,append_many_once,append_once,hypothetical_position,load_ledger,whole_share_size
def test_whole_share_sizing_keeps_reserve_and_commission():
 assert whole_share_size(1000,100,1.25,.05)==9
 assert whole_share_size(100,100,1.25,.05)==0
def test_append_is_atomic_and_idempotent(tmp_path):
 p=tmp_path/'ledger.json';i=ShadowIntent('k','s','SXR8','BUY','2024-01-31',100,9,900,1.25);assert append_once(p,i);assert not append_once(p,i);assert len(load_ledger(p)['intents'])==1
 assert hypothetical_position(load_ledger(p),'SXR8')==9
def test_ledger_rejects_non_shadow(tmp_path):
 p=tmp_path/'x.json';p.write_text(json.dumps({'mode':'live'}))
 try:load_ledger(p)
 except ValueError:return
 assert False
def test_group_append_is_atomic_and_idempotent(tmp_path):
 p=tmp_path/'pair.json'; buy=ShadowIntent('b','s','MSFT','BUY','2024-01-02',100,2,200,1); sell=ShadowIntent('s','s','MSFT','SELL','2024-01-02',101,2,202,1)
 assert append_many_once(p,[buy,sell])==2
 assert append_many_once(p,[buy,sell])==0
 assert hypothetical_position(load_ledger(p),'MSFT')==0
