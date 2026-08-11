package SQ.Utils;

import com.strategyquant.datalib.TradingException;
import com.strategyquant.tradinglib.ChartData;

/** Canonical, gap-safe H4 signals shared by generated SQ condition blocks. */
public final class AlquimiaH4Signals {
    private AlquimiaH4Signals() {}

    private static boolean valid(ChartData chart, int period, int shift)
            throws TradingException {
        return period > 0 && shift >= 0 &&
            AlquimiaGapSafeATR.isContinuous(chart, shift, Math.max(period, 13));
    }

    public static boolean momentumAbove(ChartData chart, int period, double level,
                                        int shift) throws TradingException {
        if (!valid(chart, period, shift)) return false;
        double first = chart.Close.get(shift + period);
        if (!(first > 0.0)) return false;
        double rocPct = 100.0 * (chart.Close.get(shift) / first - 1.0);
        return rocPct > level;
    }

    public static boolean momentumBelow(ChartData chart, int period, double level,
                                        int shift) throws TradingException {
        if (!valid(chart, period, shift)) return false;
        double first = chart.Close.get(shift + period);
        if (!(first > 0.0)) return false;
        double rocPct = 100.0 * (chart.Close.get(shift) / first - 1.0);
        return rocPct < -level;
    }

    public static boolean channelAbove(ChartData chart, int period, int shift)
            throws TradingException {
        if (!valid(chart, period, shift)) return false;
        double priorHigh = Double.NEGATIVE_INFINITY;
        for (int offset = 1; offset <= period; offset++) {
            priorHigh = Math.max(priorHigh, chart.High.get(shift + offset));
        }
        return chart.Close.get(shift) > priorHigh;
    }

    public static boolean channelBelow(ChartData chart, int period, int shift)
            throws TradingException {
        if (!valid(chart, period, shift)) return false;
        double priorLow = Double.POSITIVE_INFINITY;
        for (int offset = 1; offset <= period; offset++) {
            priorLow = Math.min(priorLow, chart.Low.get(shift + offset));
        }
        return chart.Close.get(shift) < priorLow;
    }
}
