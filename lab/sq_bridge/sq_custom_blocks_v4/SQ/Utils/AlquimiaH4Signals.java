package SQ.Utils;

import com.strategyquant.datalib.TradingException;
import com.strategyquant.tradinglib.ChartData;

import java.util.Arrays;

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

    private static boolean compressed(ChartData chart, int lookback,
                                      double percentile, int shift)
            throws TradingException {
        if (lookback < 1 || percentile < 0.0 || percentile > 100.0 ||
                !AlquimiaGapSafeATR.isContinuous(chart, shift, lookback + 13)) {
            return false;
        }
        double endpointClose = chart.Close.get(shift);
        double endpointAtr = AlquimiaGapSafeATR.calculate(
            chart, 14, shift, Integer.MAX_VALUE);
        if (!(endpointClose > 0.0) || !Double.isFinite(endpointAtr)) return false;
        double[] prior = new double[lookback];
        for (int offset = 1; offset <= lookback; offset++) {
            double close = chart.Close.get(shift + offset);
            double atr = AlquimiaGapSafeATR.calculate(
                chart, 14, shift + offset, Integer.MAX_VALUE);
            if (!(close > 0.0) || !Double.isFinite(atr)) return false;
            prior[offset - 1] = atr / close;
        }
        Arrays.sort(prior);
        double position = (prior.length - 1) * percentile / 100.0;
        int lower = (int)Math.floor(position), upper = (int)Math.ceil(position);
        double weight = position - lower;
        double threshold = prior[lower] + weight * (prior[upper] - prior[lower]);
        return endpointAtr / endpointClose <= threshold;
    }

    public static boolean compressionChannelAbove(ChartData chart, int period,
            int lookback, double percentile, int shift) throws TradingException {
        return valid(chart, period, shift) && compressed(chart, lookback, percentile, shift)
            && channelAbove(chart, period, shift);
    }

    public static boolean compressionChannelBelow(ChartData chart, int period,
            int lookback, double percentile, int shift) throws TradingException {
        return valid(chart, period, shift) && compressed(chart, lookback, percentile, shift)
            && channelBelow(chart, period, shift);
    }
}
