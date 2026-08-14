import pytest
from packages.brokerage.ibkr_readonly import IbkrReadonlyClient

def test_rejects_remote_or_http_gateway():
 for url in ('http://localhost:5000','https://example.com'):
  with pytest.raises(ValueError):IbkrReadonlyClient(url)
def test_only_readonly_endpoints_are_exposed():
 calls=[]
 def tx(path,params):
  calls.append((path,params))
  if path.endswith('status'):return {'authenticated':True,'connected':True}
  if path.endswith('search'):return [{'conid':123,'symbol':'SXR8','companyName':'iShares','sections':[]}]
  return [{'conid':123,'currency':'EUR','exchange':'IBIS2'}]
 c=IbkrReadonlyClient(transport=tx);assert c.auth_status()['authenticated'];assert c.search('SXR8')[0].conid==123;assert c.contract_info(123)[0]['currency']=='EUR';assert all(x[0] in c._ALLOWED_PATHS for x in calls)
def test_contract_validation_is_fail_closed():
 c=IbkrReadonlyClient(transport=lambda *_:[])
 with pytest.raises(ValueError):c.contract_info(-1)
 with pytest.raises(ValueError):c.contract_info(1,'FUT')
