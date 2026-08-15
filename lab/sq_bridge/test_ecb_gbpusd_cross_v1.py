import csv
from lab.sq_bridge.ecb_gbpusd_cross_v1 import build

def test_build_cross(tmp_path):
    fields=['TIME_PERIOD','OBS_VALUE']
    inputs=[]
    for name,value in [('gbp',.8),('usd',1.2)]:
        path=tmp_path/f'{name}.csv';inputs.append(path)
        with path.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerow({'TIME_PERIOD':'2024-01-02','OBS_VALUE':value})
    output=tmp_path/'cross.csv';result=build(inputs[0],inputs[1],output)
    assert result['rows']==1
    assert list(csv.DictReader(output.open()))[0]['usd_per_gbp']=='1.5000000000'
