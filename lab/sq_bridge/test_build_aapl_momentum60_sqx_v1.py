import zipfile
from xml.etree import ElementTree as ET
from lab.sq_bridge.build_aapl_momentum60_sqx_v1 import build

def test_builds_exact_frozen_rule(tmp_path):
 source=tmp_path/'t.sqx';xml=b'''<StrategyFile><Strategy name=""><Rules><Events><Event><Rule type="Signal"><signals><signal variable="33333333-1111-1111-3333-333333333333"/></signals></Rule><Rule name="Long entry"><Then><Item><Param key="#ExitAfterBars.ExitAfterBars#">0</Param><Param key="#StopLoss.StopLoss#"/><Param key="#ProfitTarget.ProfitTarget#"/></Item></Then></Rule></Event></Events></Rules></Strategy></StrategyFile>'''
 with zipfile.ZipFile(source,'w') as z:z.writestr('strategy_Portfolio.xml',xml);z.writestr('settings.xml',b'<Settings ResultName=""><StrategyName/></Settings>')
 output=tmp_path/'o.sqx';result=build(source,output)
 with zipfile.ZipFile(output) as z:root=ET.fromstring(z.read('strategy_Portfolio.xml'))
 assert root.find(".//Param[@key='#ExitAfterBars.ExitAfterBars#']").text=='20'
 assert [(x.get('key'),x.find("./Param[@key='#Shift#']").text) for x in root.findall('.//Rule[@type="Signal"]//Item') if x.get('key') in {'BarDayOfMonth','Close'}]==[('BarDayOfMonth','0'),('BarDayOfMonth','1'),('Close','1'),('Close','61')]
 assert result['performance_accessed'] is False

def test_build_accepts_reusable_strategy_name(tmp_path):
 source=tmp_path/'t.sqx';xml=b'''<StrategyFile><Strategy name=""><Rules><Events><Event><Rule type="Signal"><signals><signal variable="33333333-1111-1111-3333-333333333333"/></signals></Rule><Rule name="Long entry"><Then><Item><Param key="#ExitAfterBars.ExitAfterBars#">0</Param><Param key="#StopLoss.StopLoss#"/><Param key="#ProfitTarget.ProfitTarget#"/></Item></Then></Rule></Event></Events></Rules></Strategy></StrategyFile>'''
 with zipfile.ZipFile(source,'w') as z:z.writestr('strategy_Portfolio.xml',xml);z.writestr('settings.xml',b'<Settings ResultName=""><StrategyName/></Settings>')
 output=tmp_path/'o.sqx';result=build(source,output,'JPM_MOMENTUM60_MONTH_END_V1')
 with zipfile.ZipFile(output) as z:
  strategy=ET.fromstring(z.read('strategy_Portfolio.xml')).find('.//Strategy')
  settings=ET.fromstring(z.read('settings.xml'))
 assert strategy.get('name')=='JPM_MOMENTUM60_MONTH_END_V1'
 assert settings.get('ResultName')=='JPM_MOMENTUM60_MONTH_END_V1'
 assert result['strategy']=='JPM_MOMENTUM60_MONTH_END_V1'
