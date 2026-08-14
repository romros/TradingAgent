from three_strategy_portfolio_v1 import signals
def test_signal_uses_population_std_and_enters_next_bar():
 rows=[{'open':100.,'high':101.,'low':99.,'close':100.} for _ in range(20)]
 rows[-1]={'open':100.,'high':100.,'low':94.,'close':95.};rows.append({'open':96.,'high':97.,'low':95.,'close':97.})
 assert signals(rows)==[20]
