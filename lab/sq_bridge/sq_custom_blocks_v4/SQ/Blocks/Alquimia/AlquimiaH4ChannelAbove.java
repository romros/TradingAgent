package SQ.Blocks.Alquimia;

import SQ.Internal.ConditionBlock;
import SQ.Utils.AlquimiaH4Signals;
import com.strategyquant.datalib.TradingException;
import com.strategyquant.tradinglib.*;

@BuildingBlock(name="(Alquimia) H4 continuous channel breakout above",
    display="Alquimia H4 Close[@Chart@#Shift#] > prior #Period# highs",
    returnType=ReturnTypes.Boolean)
@OppositeBlock("AlquimiaH4ChannelBelow")
@ForEngine("*,-SP,-SA")
public class AlquimiaH4ChannelAbove extends ConditionBlock {
    @Parameter public ChartData Chart;
    @Parameter(defaultValue="24", minValue=2, maxValue=500, step=1) public int Period;
    @Parameter public int Shift;

    @Override public boolean OnBlockEvaluate() throws TradingException {
        return AlquimiaH4Signals.channelAbove(Chart, Period, Shift);
    }
}
