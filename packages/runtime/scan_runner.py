"""
Execució del cicle diari de scan. Reutilitzat per POST /scan i scheduler.
"""
from packages.shared import config
from packages.strategy.capitulation_d1 import CapitulationD1Strategy
from packages.market.data_feed import YFinanceD1Feed
from packages.execution.paper import PaperExecutor
from packages.portfolio.tracker import PortfolioTracker
from packages.runtime.engine import DailyEngine


def run_daily_scan() -> dict:
    """
    Executa el cicle diari: fetch candles, detecta senyals, tanca/obre trades.
    Retorna el resultat de engine.run().
    """
    strategy = CapitulationD1Strategy(
        body_thresh=config.BODY_THRESH,
        bb_period=config.BB_PERIOD,
        bb_std=config.BB_STD,
    )
    feed = YFinanceD1Feed()
    executor = PaperExecutor(
        leverage=config.LEVERAGE,
        col_pct=config.COL_PCT,
        col_max=config.COL_MAX,
        col_min=config.COL_MIN,
        fee=config.FEE,
    )
    tracker = PortfolioTracker(db_path=config.DB_PATH)
    engine = DailyEngine(
        assets=config.ASSETS,
        strategy=strategy,
        feed=feed,
        executor=executor,
        tracker=tracker,
        db_path=config.DB_PATH,
    )
    return engine.run()
