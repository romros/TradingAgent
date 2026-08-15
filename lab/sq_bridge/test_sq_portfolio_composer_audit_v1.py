import zipfile
from lab.sq_bridge.sq_portfolio_composer_audit_v1 import audit

def test_fixed_budget_order_audit(tmp_path):
    path=tmp_path/'portfolio.sqx'
    log="""Order ACCEPTED 'A/X|OpenPrice=$313.15|MM=[Alquimia fixed budget floor,Weight=25.0%]=1.0|Margin=$313.15'\nOrder ACCEPTED 'B/X|OpenPrice=$27.73|MM=[Alquimia fixed budget floor,Weight=25.0%]=18.0|Margin=$499.14'"""
    with zipfile.ZipFile(path,'w') as z:z.writestr('settings.xml',f'<R><PortfolioComposerLog>{log}</PortfolioComposerLog></R>')
    result=audit(path)
    assert result['decision']=='PASS_FIXED_BUDGET_ORDER_AUDIT'
    assert result['accepted_orders']==2
    assert result['maximum_notional']==499.14

def test_rejects_overspend(tmp_path):
    path=tmp_path/'portfolio.sqx';log="Order ACCEPTED 'A/X|OpenPrice=$313.15|MM=[Built in,Weight=25.0%]=2.0|Margin=$626.30'"
    with zipfile.ZipFile(path,'w') as z:z.writestr('settings.xml',f'<R><PortfolioComposerLog>{log}</PortfolioComposerLog></R>')
    assert audit(path)['decision']=='FAIL_FIXED_BUDGET_ORDER_AUDIT'
