package SQ.Utils;

import com.strategyquant.datalib.TradingException;
import com.strategyquant.tradinglib.ChartData;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.Arrays;

/** Canonical, price-only Alquimia v5 signals. Entry occurs at next bar open. */
public final class AlquimiaV5Signals {
    private AlquimiaV5Signals() {}

    private static double tr(ChartData c, int s) throws TradingException {
        double value = c.High.get(s) - c.Low.get(s);
        double previous = c.Close.get(s + 1);
        return Math.max(value, Math.max(Math.abs(c.High.get(s) - previous),
                                       Math.abs(c.Low.get(s) - previous)));
    }

    public static double atr(ChartData c, int shift, int period) throws TradingException {
        if (period < 1 || shift < 0) return Double.NaN;
        double sum = 0.0;
        try {
            for (int offset = 0; offset < period; offset++) sum += tr(c, shift + offset);
        } catch (Exception error) {
            return Double.NaN;
        }
        double value = sum / period;
        return value > 0.0 && Double.isFinite(value) ? value : Double.NaN;
    }

    private static double quantile(double[] values, double fraction) {
        if (values.length == 0 || fraction < 0 || fraction > 1) return Double.NaN;
        Arrays.sort(values);
        double position = (values.length - 1) * fraction;
        int lower = (int)Math.floor(position), upper = Math.min(lower + 1, values.length - 1);
        return values[lower] + (position - lower) * (values[upper] - values[lower]);
    }

    public static int xauCompressionBreakout(ChartData c, int shift, int channelBars,
                                              double compressionQuantile)
            throws TradingException {
        if (channelBars < 2) return 0;
        double[] normalized = new double[96];
        for (int old = 96; old >= 1; old--) {
            double value = atr(c, shift + old, 14), close = c.Close.get(shift + old);
            if (!Double.isFinite(value) || !(close > 0)) return 0;
            normalized[96 - old] = value / close;
        }
        double last = normalized[95];
        if (last > quantile(Arrays.copyOf(normalized, 95), compressionQuantile)) return 0;
        double high = Double.NEGATIVE_INFINITY, low = Double.POSITIVE_INFINITY;
        for (int old = 1; old <= channelBars; old++) {
            high = Math.max(high, c.High.get(shift + old));
            low = Math.min(low, c.Low.get(shift + old));
        }
        return c.Close.get(shift) > high ? 1 : c.Close.get(shift) < low ? -1 : 0;
    }

    public static int xauFailedShock(ChartData c, int shift, double shockAtr,
                                     int reentryBars) throws TradingException {
        if (!(shockAtr > 0) || reentryBars < 1) return 0;
        for (int old = 1; old <= reentryBars; old++) {
            double value = atr(c, shift + old + 1, 14);
            if (!Double.isFinite(value)) continue;
            double displacement = c.Close.get(shift + old) - c.Close.get(shift + old + 1);
            if (displacement >= shockAtr * value && c.Close.get(shift) < c.Open.get(shift + old)) return -1;
            if (displacement <= -shockAtr * value && c.Close.get(shift) > c.Open.get(shift + old)) return 1;
        }
        return 0;
    }

    private static int hour(ChartData c, int shift) throws TradingException {
        return Instant.ofEpochMilli(c.Time(shift)).atZone(ZoneOffset.UTC).getHour();
    }

    private static LocalDate day(ChartData c, int shift) throws TradingException {
        return Instant.ofEpochMilli(c.Time(shift)).atZone(ZoneOffset.UTC).toLocalDate();
    }

    private static double[] asiaRange(ChartData c, int shift) throws TradingException {
        LocalDate current = day(c, shift);
        double high = Double.NEGATIVE_INFINITY, low = Double.POSITIVE_INFINITY;
        int count = 0;
        for (int old = 1; old <= 64; old++) {
            if (!day(c, shift + old).equals(current)) break;
            int h = hour(c, shift + old);
            if (h < 7) {
                high = Math.max(high, c.High.get(shift + old));
                low = Math.min(low, c.Low.get(shift + old)); count++;
            }
        }
        return count == 28 ? new double[] {high, low} : null;
    }

    public static int usdjpySessionBreakout(ChartData c, int shift, double maxRangeAtrRatio,
                                             int trendLookback) throws TradingException {
        if (hour(c, shift) < 7 || hour(c, shift) >= 12 || trendLookback < 2) return 0;
        double[] range = asiaRange(c, shift); double value = atr(c, shift + 1, 14);
        if (range == null || !Double.isFinite(value) || range[0] - range[1] > maxRangeAtrRatio * value
                || !day(c, shift + trendLookback).equals(day(c, shift))) return 0;
        double trend = c.Close.get(shift + 1) - c.Close.get(shift + trendLookback);
        return c.Close.get(shift) > range[0] && trend > 0 ? 1
             : c.Close.get(shift) < range[1] && trend < 0 ? -1 : 0;
    }

    public static int usdjpyFailedBreak(ChartData c, int shift, int failureWindow,
                                        double bufferAtr) throws TradingException {
        if (hour(c, shift) < 7 || hour(c, shift) >= 12 || failureWindow < 1 || bufferAtr < 0) return 0;
        double[] range = asiaRange(c, shift); double value = atr(c, shift + 1, 14);
        if (range == null || !Double.isFinite(value) || !(c.Close.get(shift) > range[1]
                && c.Close.get(shift) < range[0])) return 0;
        for (int old = 1; old <= failureWindow; old++) {
            if (!day(c, shift + old).equals(day(c, shift))) continue;
            if (c.High.get(shift + old) > range[0] + bufferAtr * value) return -1;
            if (c.Low.get(shift + old) < range[1] - bufferAtr * value) return 1;
        }
        return 0;
    }

    public static int us500ShockRebound(ChartData c, int shift, double shockAtr,
                                        double reclaimFraction) throws TradingException {
        if (!(shockAtr > 0) || reclaimFraction < 0 || reclaimFraction > 1) return 0;
        double value = atr(c, shift + 1, 14);
        if (!Double.isFinite(value) || c.Close.get(shift + 1) - c.Low.get(shift) < shockAtr * value) return 0;
        double range = c.High.get(shift) - c.Low.get(shift);
        if (!(range > 0) || c.Close.get(shift) < c.Low.get(shift) + reclaimFraction * range) return 0;
        double fast = 0, slow = 0;
        for (int old = 1; old <= 20; old++) {
            double valueTr = tr(c, shift + old); slow += valueTr;
            if (old <= 5) fast += valueTr;
        }
        return fast / 5 <= slow / 20 ? 1 : 0;
    }

    public static int eurusdShortTrend(ChartData c, int shift, int channelDays,
                                       int trendLookback) throws TradingException {
        if (channelDays < 2 || trendLookback < 2) return 0;
        double high = Double.NEGATIVE_INFINITY, low = Double.POSITIVE_INFINITY;
        for (int old = 1; old <= channelDays; old++) {
            high = Math.max(high, c.High.get(shift + old));
            low = Math.min(low, c.Low.get(shift + old));
        }
        double trend = c.Close.get(shift + 1) - c.Close.get(shift + trendLookback);
        return c.Close.get(shift) > high && trend > 0 ? 1
             : c.Close.get(shift) < low && trend < 0 ? -1 : 0;
    }
}
