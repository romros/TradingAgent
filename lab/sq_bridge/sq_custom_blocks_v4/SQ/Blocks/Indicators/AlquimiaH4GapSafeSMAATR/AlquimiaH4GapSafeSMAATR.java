package SQ.Blocks.Indicators.AlquimiaH4GapSafeSMAATR;

import SQ.Internal.IndicatorBlock;
import com.strategyquant.datalib.DataSeries;
import com.strategyquant.datalib.TradingException;
import com.strategyquant.tradinglib.*;

@BuildingBlock(name="(Alquimia) H4 gap-safe SMA ATR",
    display="AlquimiaH4GapSafeSMAATR(@Chart@#Period#)[#Shift#]",
    returnType=ReturnTypes.PriceRange)
@Indicator(min=0, max=5000, step=0.001)
@ParameterSet(set="Period=14")
public class AlquimiaH4GapSafeSMAATR extends IndicatorBlock {
    private static final long H4_MILLISECONDS = 4L * 60L * 60L * 1000L;

    @Parameter(defaultChartIndex=0)
    public ChartData Chart;

    @Parameter(category="Default", name="Period", minValue=2, maxValue=100,
        defaultValue="14", step=1)
    public int Period;

    @Output(name="ATR", color=Colors.Green)
    public DataSeries Value;

    @Override
    protected void OnBarUpdate() throws TradingException {
        if (getCurrentBar() < Period - 1) {
            Value.set(0, Double.NaN);
            return;
        }
        for (int shift = 0; shift < Period - 1; shift++) {
            if (Chart.Time(shift) - Chart.Time(shift + 1) != H4_MILLISECONDS) {
                Value.set(0, Double.NaN);
                return;
            }
        }
        double sum = 0.0;
        for (int shift = 0; shift < Period; shift++) {
            double high = Chart.High.get(shift);
            double low = Chart.Low.get(shift);
            double range = high - low;
            if (getCurrentBar() > shift &&
                    Chart.Time(shift) - Chart.Time(shift + 1) == H4_MILLISECONDS) {
                double previousClose = Chart.Close.get(shift + 1);
                range = Math.max(range, Math.max(Math.abs(high - previousClose),
                                                 Math.abs(low - previousClose)));
            }
            sum += range;
        }
        Value.set(0, sum / Period);
    }
}
