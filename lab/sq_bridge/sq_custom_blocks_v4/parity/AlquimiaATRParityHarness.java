package alquimia.parity;

import SQ.Utils.AlquimiaGapSafeATR;
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

/** Fail-closed, exact SQ ChartData parity check for the Python ATR oracle. */
public final class AlquimiaATRParityHarness {
    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("yyyy.MM.dd HH:mm:ss");

    private record Row(long time, double open, double high, double low,
                       double close, double volume, double expected) {}

    private static List<Row> read(Path path) throws Exception {
        List<Row> rows = new ArrayList<>();
        try (BufferedReader input = Files.newBufferedReader(path)) {
            for (String line; (line = input.readLine()) != null;) {
                String[] fields = line.split(";", -1);
                if (fields.length != 7) throw new IllegalArgumentException("seven fields required");
                rows.add(new Row(
                    LocalDateTime.parse(fields[0], STAMP).toInstant(ZoneOffset.UTC).toEpochMilli(),
                    Double.parseDouble(fields[1]), Double.parseDouble(fields[2]),
                    Double.parseDouble(fields[3]), Double.parseDouble(fields[4]),
                    Double.parseDouble(fields[5]), Double.parseDouble(fields[6])));
            }
        }
        if (rows.size() < 15) throw new IllegalArgumentException("oracle too short");
        return rows;
    }

    private static DataSeries numbers(String name, List<Row> rows,
                                      java.util.function.ToDoubleFunction<Row> field) throws Exception {
        DataSeries result = new DataSeries(name);
        for (Row row : rows) result.add(field.applyAsDouble(row));
        return result;
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("oracle path required");
        List<Row> rows = read(Path.of(args[0]));
        TimeDataSeries times = new TimeDataSeries("Time");
        for (Row row : rows) times.add(row.time());
        ChartData chart = new ChartData();
        chart.Time = times;
        chart.Open = numbers("Open", rows, Row::open);
        chart.High = numbers("High", rows, Row::high);
        chart.Low = numbers("Low", rows, Row::low);
        chart.Close = numbers("Close", rows, Row::close);
        chart.Volume = numbers("Volume", rows, Row::volume);

        int differences = 0, stopComparisons = 0;
        for (int bar = 0; bar < rows.size(); bar++) {
            int hiddenFutureBars = rows.size() - 1 - bar;
            chart.Time.setShift(hiddenFutureBars);
            chart.Open.setShift(hiddenFutureBars);
            chart.High.setShift(hiddenFutureBars);
            chart.Low.setShift(hiddenFutureBars);
            chart.Close.setShift(hiddenFutureBars);
            chart.Volume.setShift(hiddenFutureBars);
            chart.setCurrentBar(bar, bar);
            if (Double.doubleToLongBits(chart.Close.get(0)) !=
                    Double.doubleToLongBits(rows.get(bar).close())) {
                throw new AssertionError("ChartData cursor mismatch at bar=" + bar);
            }
            double actual = AlquimiaGapSafeATR.calculate(chart, 14, 0, bar);
            double expected = rows.get(bar).expected();
            boolean equal = Double.isNaN(actual) && Double.isNaN(expected)
                || Double.doubleToLongBits(actual) == Double.doubleToLongBits(expected);
            if (!equal) {
                differences++;
                if (differences <= 10) {
                    System.err.printf("bar=%d expected=%s actual=%s%n", bar, expected, actual);
                }
            }
            if (bar > 0 && !Double.isNaN(rows.get(bar - 1).expected())) {
                for (double multiple : new double[] {1.0, 1.75, 2.25, 4.0}) {
                    for (int direction : new int[] {-1, 1}) {
                        double stop = AlquimiaGapSafeATR.stopPrice(
                            chart, 14, 1, bar, rows.get(bar).open(), direction, multiple);
                        double expectedStop = rows.get(bar).open() + direction * multiple *
                                              rows.get(bar - 1).expected();
                        if (Double.doubleToLongBits(stop) != Double.doubleToLongBits(expectedStop)) {
                            differences++;
                            if (differences <= 10) System.err.printf(
                                "stop bar=%d direction=%d multiple=%s expected=%s actual=%s%n",
                                bar, direction, multiple, expectedStop, stop);
                        }
                        stopComparisons++;
                    }
                }
            }
        }
        if (differences != 0) throw new AssertionError("ATR parity differences=" + differences);
        System.out.printf("PASS_EXACT_ATR_STOP_PARITY rows=%d stop_comparisons=%d differences=0%n",
                          rows.size(), stopComparisons);
    }
}
