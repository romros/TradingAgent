import json
from pathlib import Path
from packages.strategy.nflx_04681 import atr, bracket, exit_on_bar
from apps import shadow_control_panel as panel

def test_sq_atr_and_frozen_bracket():
    rows=[{'high':11,'low':9,'close':10},{'high':13,'low':10,'close':12}]
    assert atr(rows,15)==[2,2.5]
    assert bracket(100,4)==(90,111.2)

def test_exit_priority_is_gap_then_stop_then_target():
    assert exit_on_bar({'open':89,'high':120,'low':80},90,110)==('SL_GAP',89,True)
    assert exit_on_bar({'open':100,'high':120,'low':80},90,110)==('SL',90,False)

def test_panel_exposes_nflx_without_authorizing_orders(monkeypatch):
    values={panel.STATE:{'status':'PASS','orders_sent':0},panel.NFLX_PIPELINE:{'status':'PASS','scan':{'action':'NONE'}},panel.NFLX_RISK:{'selected_overlay':{'cagr_pct':20.6}},panel.NFLX_MTM:{'strategy_daily_mtm_drawdown_pct':15.24},panel.SXR8_SCHEDULE:{'actions':[]}}
    monkeypatch.setattr(panel,'read',lambda path,default=None:values.get(path,default or {}))
    monkeypatch.setattr(panel,'position',lambda path,symbol:{'quantity':0,'intents':0,'last_intent':None})
    value=panel.snapshot()
    assert any(x['name'].startswith('NFLX') for x in value['strategies'])
    assert value['nflx']['selected']['cagr_pct']==20.6
    assert value['safety']['orders_sent']==0 and value['safety']['live_authorized'] is False

def test_board_has_dedicated_nflx_tab():
    root=Path(__file__).resolve().parents[2]
    html=(root/'apps/shadow_panel_web/index.html').read_text()
    js=(root/'apps/shadow_panel_web/app.js').read_text()
    assert 'data-tab="nflx"' in html and 'nflxmetrics' in html
    assert "d.nflx" in js and 'Buy & hold' in js
