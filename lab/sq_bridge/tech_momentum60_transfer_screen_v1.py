#!/usr/bin/env python3
from pathlib import Path
import lab.sq_bridge.etf_momentum60_transfer_screen_v1 as base
base.SPEC=Path(__file__).with_name('tech_momentum60_transfer_preregistration_v1.json')
base.LOCK=Path(__file__).with_name('tech_momentum60_transfer_preregistration_v1.lock.json')
if __name__=='__main__':base.main()
