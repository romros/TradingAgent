import importlib.util,math
from pathlib import Path
P=Path(__file__).with_name('turn_of_month_ucits_transfer_screen_v2.py')
def test_corr_identical():
 text=P.read_text().split("ap=argparse.ArgumentParser()")[0];ns={'__file__':str(P)};exec(text,ns);assert math.isclose(ns['corr']({1:.1,2:.2},{1:.2,2:.4})['correlation'],1)
