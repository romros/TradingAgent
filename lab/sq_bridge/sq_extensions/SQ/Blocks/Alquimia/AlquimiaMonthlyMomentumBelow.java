package SQ.Blocks.Alquimia;

import SQ.Internal.ConditionBlock;
import SQ.Utils.AlquimiaMonthlyMomentum;
import com.strategyquant.datalib.TradingException;
import com.strategyquant.tradinglib.*;

@BuildingBlock(name="(Alquimia) exact monthly momentum below",
    display="Alquimia month-end close @Chart@ #Months# months momentum [#Shift#] is below or equal zero",
    returnType=ReturnTypes.Boolean)
@OppositeBlock(value="AlquimiaMonthlyMomentumAbove", oscillator=true, middleValue=0)
@ForEngine("*,-SP,-SA")
public class AlquimiaMonthlyMomentumBelow extends ConditionBlock {
    @Parameter public ChartData Chart;
    @Parameter(defaultValue="12", minValue=1, maxValue=36, step=1) public int Months;
    @Parameter public int Shift;

    @Override public boolean OnBlockEvaluate() throws TradingException {
        return AlquimiaMonthlyMomentum.direction(Chart, Months, Shift) < 0;
    }
}
