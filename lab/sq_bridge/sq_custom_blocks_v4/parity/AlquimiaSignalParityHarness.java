package alquimia.parity;

import SQ.Utils.AlquimiaH4Signals;
import com.strategyquant.datalib.DataSeries;
import com.strategyquant.datalib.dataseries.TimeDataSeries;
import com.strategyquant.tradinglib.ChartData;

import java.io.BufferedReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

/** Exact comparison of Python signal expectations through SQ's real series API. */
public final class AlquimiaSignalParityHarness {
    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("yyyy.MM.dd HH:mm:ss");
    private record Bar(long time, double open, double high, double low, double close, double volume) {}

    private static List<Bar> bars(Path path) throws Exception {
        List<Bar> result = new ArrayList<>();
        try (BufferedReader input = Files.newBufferedReader(path)) {
            for (String line; (line = input.readLine()) != null;) {
                String[] f = line.split(";", -1);
                result.add(new Bar(LocalDateTime.parse(f[0], STAMP).toInstant(ZoneOffset.UTC).toEpochMilli(),
                    Double.parseDouble(f[1]), Double.parseDouble(f[2]), Double.parseDouble(f[3]),
                    Double.parseDouble(f[4]), Double.parseDouble(f[5])));
            }
        }
        return result;
    }

    private static DataSeries series(String name, List<Bar> rows,
                                     java.util.function.ToDoubleFunction<Bar> field) throws Exception {
        DataSeries result = new DataSeries(name);
        for (Bar row : rows) result.add(field.applyAsDouble(row));
        return result;
    }

    private static void cursor(ChartData chart, int total, int bar) {
        int hidden = total - 1 - bar;
        chart.Time.setShift(hidden); chart.Open.setShift(hidden); chart.High.setShift(hidden);
        chart.Low.setShift(hidden); chart.Close.setShift(hidden); chart.Volume.setShift(hidden);
        chart.setCurrentBar(bar, bar);
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("price and signal oracle required");
        List<Bar> rows = bars(Path.of(args[0]));
        TimeDataSeries time = new TimeDataSeries("Time");
        for (Bar row : rows) time.add(row.time());
        ChartData chart = new ChartData(); chart.Time = time;
        chart.Open = series("Open", rows, Bar::open); chart.High = series("High", rows, Bar::high);
        chart.Low = series("Low", rows, Bar::low); chart.Close = series("Close", rows, Bar::close);
        chart.Volume = series("Volume", rows, Bar::volume);
        int checked = 0, differences = 0;
        try (BufferedReader input = Files.newBufferedReader(Path.of(args[1]))) {
            input.readLine();
            for (String line; (line = input.readLine()) != null;) {
                String[] f = line.split(";", -1);
                int decision = Integer.parseInt(f[0]), period = Integer.parseInt(f[1]);
                int shift = Integer.parseInt(f[2]); double level = Double.parseDouble(f[3]);
                cursor(chart, rows.size(), decision + 1);
                boolean[] actual = {
                    AlquimiaH4Signals.momentumAbove(chart, period, level, shift),
                    AlquimiaH4Signals.momentumBelow(chart, period, level, shift),
                    AlquimiaH4Signals.channelAbove(chart, period, shift),
                    AlquimiaH4Signals.channelBelow(chart, period, shift)};
                for (int index = 0; index < actual.length; index++) {
                    boolean expected = Integer.parseInt(f[4 + index]) == 1;
                    if (actual[index] != expected) {
                        differences++;
                        if (differences <= 10) System.err.printf(
                            "decision=%d period=%d shift=%d kind=%d expected=%s actual=%s%n",
                            decision, period, shift, index, expected, actual[index]);
                    }
                    checked++;
                }
            }
        }
        if (differences != 0) throw new AssertionError("signal parity differences=" + differences);
        System.out.printf("PASS_EXACT_SIGNAL_PARITY comparisons=%d differences=0%n", checked);
    }
}
