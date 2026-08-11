package SQ.Utils;

import com.strategyquant.datalib.TradingException;
import com.strategyquant.tradinglib.ChartData;

public final class AlquimiaGapSafeATR {
    public static final long H4_MILLISECONDS = 4L * 60L * 60L * 1000L;

    private AlquimiaGapSafeATR() {}

    public static boolean isContinuous(ChartData chart, int shift,
                                       int transitions) throws TradingException {
        for (int offset = 0; offset < transitions; offset++) {
            if (chart.Time(shift + offset) - chart.Time(shift + offset + 1)
                    != H4_MILLISECONDS) return false;
        }
        return true;
    }

    public static double calculate(ChartData chart, int period, int shift,
                                   int currentBar) throws TradingException {
        if (period < 1 || shift < 0 || currentBar < shift + period - 1 ||
                !isContinuous(chart, shift, period - 1)) return Double.NaN;
        double sum = 0.0;
        for (int offset = 0; offset < period; offset++) {
            int at = shift + offset;
            double high = chart.High.get(at);
            double low = chart.Low.get(at);
            double range = high - low;
            if (currentBar > at &&
                    chart.Time(at) - chart.Time(at + 1) == H4_MILLISECONDS) {
                double previousClose = chart.Close.get(at + 1);
                range = Math.max(range, Math.max(Math.abs(high - previousClose),
                                                 Math.abs(low - previousClose)));
            }
            sum += range;
        }
        return sum / period;
    }

    public static double stopPrice(ChartData chart, int period, int shift,
                                   int currentBar, double entryPrice,
                                   int offsetDirection, double multiple)
            throws TradingException {
        double atr = calculate(chart, period, shift, currentBar);
        if (!Double.isFinite(atr) || !Double.isFinite(entryPrice)
                || !Double.isFinite(multiple) || multiple <= 0
                || (offsetDirection != -1 && offsetDirection != 1)) {
            return Double.NaN;
        }
        return entryPrice + offsetDirection * multiple * atr;
    }
}
