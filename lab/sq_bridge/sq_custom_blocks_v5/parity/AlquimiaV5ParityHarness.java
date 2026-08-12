package alquimia.parity;

import SQ.Utils.AlquimiaV5Signals;
import com.strategyquant.datalib.DataSeries;
import com.strategyquant.datalib.dataseries.TimeDataSeries;
import com.strategyquant.tradinglib.ChartData;
import java.io.BufferedReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

public final class AlquimiaV5ParityHarness {
    private record Row(long time, double open, double high, double low, double close) {}
    private static DataSeries series(String name, List<Row> rows,
            java.util.function.ToDoubleFunction<Row> field) throws Exception {
        DataSeries result = new DataSeries(name);
        for (Row row : rows) result.add(field.applyAsDouble(row));
        return result;
    }
    private static void cursor(ChartData chart, int total, int bar) {
        int hidden = total - 1 - bar;
        chart.Time.setShift(hidden); chart.Open.setShift(hidden); chart.High.setShift(hidden);
        chart.Low.setShift(hidden); chart.Close.setShift(hidden); chart.setCurrentBar(bar, bar);
    }
    public static void main(String[] args) throws Exception {
        List<Row> rows = new ArrayList<>(); List<String[]> expected = new ArrayList<>();
        try (BufferedReader input = Files.newBufferedReader(Path.of(args[0]))) {
            input.readLine();
            for (String line; (line = input.readLine()) != null;) {
                String[] f = line.split(";", -1);
                rows.add(new Row(Long.parseLong(f[0]), Double.parseDouble(f[1]),
                    Double.parseDouble(f[2]), Double.parseDouble(f[3]), Double.parseDouble(f[4])));
                expected.add(f);
            }
        }
        ChartData c = new ChartData(); TimeDataSeries times = new TimeDataSeries("Time");
        for (Row row : rows) times.add(row.time); c.Time = times;
        c.Open = series("Open", rows, Row::open); c.High = series("High", rows, Row::high);
        c.Low = series("Low", rows, Row::low); c.Close = series("Close", rows, Row::close);
        int checked = 0, differences = 0;
        for (int bar = 120; bar < rows.size(); bar++) {
            cursor(c, rows.size(), bar); String[] f = expected.get(bar);
            int[] actual = {
                AlquimiaV5Signals.xauCompressionBreakout(c, 0, 8, .15),
                AlquimiaV5Signals.xauFailedShock(c, 0, 1.5, 2),
                AlquimiaV5Signals.usdjpySessionBreakout(c, 0, 20, 8),
                AlquimiaV5Signals.usdjpyFailedBreak(c, 0, 2, .1),
                AlquimiaV5Signals.us500ShockRebound(c, 0, 1.5, .7),
                AlquimiaV5Signals.eurusdShortTrend(c, 0, 10, 20)};
            for (int index = 0; index < actual.length; index++) {
                int wanted = Integer.parseInt(f[5 + index]);
                if (actual[index] != wanted) { differences++; if (differences < 10)
                    System.err.printf("bar=%d signal=%d expected=%d actual=%d%n", bar, index, wanted, actual[index]); }
                checked++;
            }
        }
        if (differences != 0) throw new AssertionError("differences=" + differences);
        System.out.printf("PASS_ALQUIMIA_V5_EXACT_SIGNAL_PARITY comparisons=%d differences=0%n", checked);
    }
}
