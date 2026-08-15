package SQ.Utils;

import com.strategyquant.datalib.TradingException;
import com.strategyquant.tradinglib.ChartData;

import java.time.Instant;
import java.time.YearMonth;
import java.time.ZoneOffset;

/** Exact calendar-month momentum helpers; no fixed trading-day approximation. */
public final class AlquimiaMonthlyMomentum {
    private AlquimiaMonthlyMomentum() {}

    private static YearMonth month(long epochMillis) {
        return YearMonth.from(Instant.ofEpochMilli(epochMillis).atZone(ZoneOffset.UTC));
    }

    private static boolean isFirstTradingBarOfMonth(ChartData chart, int shift)
            throws TradingException {
        return !month(chart.Time(shift)).equals(month(chart.Time(shift + 1)));
    }

    private static double monthEndClose(ChartData chart, YearMonth wanted, int fromShift)
            throws TradingException {
        for (int offset = fromShift; offset < fromShift + 400; offset++) {
            YearMonth observed = month(chart.Time(offset));
            if (observed.equals(wanted)) return chart.Close.get(offset);
            if (observed.isBefore(wanted)) break;
        }
        return Double.NaN;
    }

    public static int direction(ChartData chart, int months, int shift)
            throws TradingException {
        if (months < 1 || shift < 0 || !isFirstTradingBarOfMonth(chart, shift)) return 0;
        int signalShift = shift + 1;
        YearMonth signalMonth = month(chart.Time(signalShift));
        double current = chart.Close.get(signalShift);
        double prior = monthEndClose(chart, signalMonth.minusMonths(months), signalShift + 1);
        if (!(current > 0.0) || !(prior > 0.0)) return 0;
        return current > prior ? 1 : -1;
    }
}
