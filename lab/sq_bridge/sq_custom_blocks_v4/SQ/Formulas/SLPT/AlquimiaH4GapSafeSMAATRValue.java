package SQ.Formulas.SLPT;

import SQ.Internal.FormulaBlock;
import SQ.Utils.AlquimiaGapSafeATR;
import com.strategyquant.datalib.*;
import com.strategyquant.tradinglib.*;

@Formula(order=401, name="Alquimia H4 gap-safe SMA ATR value", formula="SLPT")
public class AlquimiaH4GapSafeSMAATRValue extends FormulaBlock {
    @Parameter(defaultValue="1", minValue=0.01, builderMinValue=1,
        builderMaxValue=4, maxValue=100, step=0.25, postfix="* Alquimia ATR(")
    @SLPTValue(SLPTValues.ATRMultiple)
    public double Value;

    @Parameter(defaultValue="14", minValue=14, maxValue=14, step=1, postfix=")")
    @SLPTValue(SLPTValues.ATRPeriod)
    public int AtrPeriod;

    @Override
    public double evaluateFormula(StrategyBase strategy, String symbol,
                                  double price, int direction) throws TradingException {
        ChartData chart = strategy.MarketData.Chart(symbol);
        int currentBar = chart.Time.size() - 1;
        double stop = AlquimiaGapSafeATR.stopPrice(
            chart, AtrPeriod, 1, currentBar, price, direction > 0 ? 1 : -1, Value);
        return Double.isFinite(stop) ? stop : Order.NOT_DEFINED;
    }
}
