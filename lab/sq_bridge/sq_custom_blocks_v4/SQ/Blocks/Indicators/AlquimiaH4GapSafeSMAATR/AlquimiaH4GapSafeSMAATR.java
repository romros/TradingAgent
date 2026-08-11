package SQ.Blocks.Indicators.AlquimiaH4GapSafeSMAATR;

import SQ.Internal.IndicatorBlock;
import SQ.Utils.AlquimiaGapSafeATR;
import com.strategyquant.datalib.DataSeries;
import com.strategyquant.datalib.TradingException;
import com.strategyquant.tradinglib.*;

@BuildingBlock(name="(Alquimia) H4 gap-safe SMA ATR",
    display="AlquimiaH4GapSafeSMAATR(@Chart@#Period#)[#Shift#]",
    returnType=ReturnTypes.PriceRange)
@Indicator(min=0, max=5000, step=0.001)
@ParameterSet(set="Period=14")
public class AlquimiaH4GapSafeSMAATR extends IndicatorBlock {
    @Parameter(defaultChartIndex=0)
    public ChartData Chart;

    @Parameter(category="Default", name="Period", minValue=2, maxValue=100,
        defaultValue="14", step=1)
    public int Period;

    @Output(name="ATR", color=Colors.Green)
    public DataSeries Value;

    @Override
    protected void OnBarUpdate() throws TradingException {
        Value.set(0, AlquimiaGapSafeATR.calculate(Chart, Period, 0,
                                                  getCurrentBar()));
    }
}
