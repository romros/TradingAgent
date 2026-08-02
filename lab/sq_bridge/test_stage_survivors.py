#!/usr/bin/env python3
import json, tempfile
from pathlib import Path
from stage_survivors import stage
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp); src=root/'src'; dst=root/'dst'; src.mkdir()
    (src/'A.sqx').write_bytes(b'a'); (src/'B.sqx').write_bytes(b'b')
    gate=root/'gate.json'; gate.write_text(json.dumps({'survivors':['B'],'survivor_count':1}))
    result=stage(gate,src,dst); assert result['copied']==['B'] and not (dst/'A.sqx').exists()
print('PASS: exact survivor staging')
