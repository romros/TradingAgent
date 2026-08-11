package SQ.Blocks.Alquimia;

import SQ.Internal.ConditionBlock;
import SQ.Utils.AlquimiaH4Signals;
import com.strategyquant.datalib.TradingException;
import com.strategyquant.tradinglib.*;

@BuildingBlock(name="(Alquimia) H4 continuous momentum above",
    display="Alquimia H4 ROC(@Chart@#Period#)[#Shift#] > #Level#%",
    returnType=ReturnTypes.Boolean)
@OppositeBlock(value="AlquimiaH4MomentumBelow", oscillator=true, middleValue=0, field="Level")
@ForEngine("*,-SP,-SA")
public class AlquimiaH4MomentumAbove extends ConditionBlock {
    @Parameter public ChartData Chart;
    @Parameter(defaultValue="24", minValue=2, maxValue=500, step=1) public int Period;
    @Parameter(defaultValue="0", minValue=0, maxValue=15, step=0.5) public double Level;
    @Parameter public int Shift;

    @Override public boolean OnBlockEvaluate() throws TradingException {
        return AlquimiaH4Signals.momentumAbove(Chart, Period, Level, Shift);
    }
}
