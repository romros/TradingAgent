package SQ.Blocks.BarAndTime;

import SQ.Internal.ConditionBlock;
import SQ.Utils.AlquimiaGapSafeATR;
import com.strategyquant.datalib.TradingException;
import com.strategyquant.tradinglib.*;

@BuildingBlock(name="(Alquimia) H4 window is continuous",
    display="Alquimia H4 window @Chart@ #Transitions# transitions [#Shift#] is continuous",
    returnType=ReturnTypes.Boolean)
@ForEngine("*,-SP,-SA")
public class AlquimiaH4WindowIsContinuous extends ConditionBlock {
    @Parameter
    public ChartData Chart;

    @Parameter(defaultValue="14", minValue=1, maxValue=500, step=1)
    public int Transitions;

    @Parameter
    public int Shift;

    @Override
    public boolean OnBlockEvaluate() throws TradingException {
        return AlquimiaGapSafeATR.isContinuous(Chart, Shift, Transitions);
    }
}

