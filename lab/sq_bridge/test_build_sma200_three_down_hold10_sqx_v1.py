import zipfile
from xml.etree import ElementTree as ET
from lab.sq_bridge.build_sma200_three_down_hold10_sqx_v1 import build

def test_builder_freezes_four_conditions_and_time_exit(tmp_path):
 source=tmp_path/'source.sqx';strategy=b'''<StrategyFile><Strategy name="old"><Rules><Events><Event><Rule type="Signal"><signals><signal variable="33333333-1111-1111-3333-333333333333"><Item key="Boolean"/></signal></signals></Rule><Rule name="Long entry"><Then><Item><Param key="#ExitAfterBars.ExitAfterBars#">0</Param><Param key="#StopLoss.StopLoss#"/><Param key="#ProfitTarget.ProfitTarget#"/></Item></Then></Rule></Event></Events></Rules></Strategy></StrategyFile>''';settings=b'<Settings ResultName="old"><StrategyName>old</StrategyName></Settings>'
 with zipfile.ZipFile(source,'w') as archive:archive.writestr('strategy_Portfolio.xml',strategy);archive.writestr('settings.xml',settings)
 output=tmp_path/'out.sqx';build(source,output)
 with zipfile.ZipFile(output) as archive:root=ET.fromstring(archive.read('strategy_Portfolio.xml'))
 assert len(root.findall('.//signal//Item[@key="IsLower"]'))==3
 assert len(root.findall('.//signal//Item[@key="IsGreater"]'))==1
 assert root.find(".//Item[@key='SMA']/Param[@key='#Period#']").text=='200'
 assert root.find(".//Rule[@name='Long entry']//Param[@key='#ExitAfterBars.ExitAfterBars#']").text=='10'
