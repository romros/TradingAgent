package SQ.Blocks.Alquimia;

import SQ.Internal.ConditionBlock;
import SQ.Utils.AlquimiaH4Signals;
import com.strategyquant.datalib.TradingException;
import com.strategyquant.tradinglib.*;

@BuildingBlock(name="(Alquimia) H4 compressed channel breakout below",
    display="Alquimia H4 Close[@Chart@#Shift#] < prior #Period# lows after ATR compression #CompressionLookback#/#CompressionPercentile#",
    returnType=ReturnTypes.Boolean)
@OppositeBlock("AlquimiaH4CompressionChannelAbove")
@ForEngine("*,-SP,-SA")
public class AlquimiaH4CompressionChannelBelow extends ConditionBlock {
    @Parameter public ChartData Chart;
    @Parameter(defaultValue="24", minValue=2, maxValue=500, step=1) public int Period;
    @Parameter(defaultValue="24", minValue=2, maxValue=500, step=1) public int CompressionLookback;
    @Parameter(defaultValue="25", minValue=0, maxValue=100, step=5) public double CompressionPercentile;
    @Parameter public int Shift;

    @Override public boolean OnBlockEvaluate() throws TradingException {
        return AlquimiaH4Signals.compressionChannelBelow(
            Chart, Period, CompressionLookback, CompressionPercentile, Shift);
    }
}
