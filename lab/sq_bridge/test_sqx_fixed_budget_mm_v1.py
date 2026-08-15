import zipfile
from xml.etree import ElementTree as ET
from lab.sq_bridge.sqx_fixed_budget_mm_v1 import derive
def test_only_mm_changes(tmp_path):
 source=tmp_path/'a.sqx';output=tmp_path/'b.sqx';xml=b'<StrategyFile><Strategy name="A"><MoneyManagement type="FixedSize"><Params/></MoneyManagement><Rules><X/></Rules></Strategy></StrategyFile>'
 last=b'<Settings><RiskMoneyManagement><MoneyManagement><Method type="FixedSize" use="true"><Params/></Method><InitialCapital>10000</InitialCapital><Method type="StocksSizeByPrice" use="false"><Params><Param key="UseAccountBalance">true</Param><Param key="MaxSize">50</Param></Params></Method></MoneyManagement></RiskMoneyManagement></Settings>'
 settings=b'<Results><SettingsMap><MoneyManagement.InitialCapital>10000</MoneyManagement.InitialCapital></SettingsMap></Results>'
 with zipfile.ZipFile(source,'w') as z:z.writestr('strategy_Portfolio.xml',xml);z.writestr('lastSettings.xml',last);z.writestr('settings.xml',settings);z.writestr('keep.bin',b'abc')
 result=derive(source,output,500)
 with zipfile.ZipFile(output) as z:
  root=ET.fromstring(z.read('strategy_Portfolio.xml'));assert z.read('keep.bin')==b'abc'
  mm=root.find('.//MoneyManagement');assert mm.get('type')=='AlquimiaFixedBudgetFloor';assert mm.find(".//Param[@key='MaxSize']").text=='1000000000';assert root.find('.//Rules/X') is not None
  last_root=ET.fromstring(z.read('lastSettings.xml'));assert last_root.find(".//Method[@type='AlquimiaFixedBudgetFloor']").get('use')=='true';assert last_root.find('.//InitialCapital').text=='500'
  assert ET.fromstring(z.read('settings.xml')).find('.//MoneyManagement.InitialCapital').text=='500'
 assert result['logic_changed'] is False
