package SQ.MoneyManagement;

import com.strategyquant.lib.*;
import com.strategyquant.tradinglib.*;

@ClassConfig(name="Alquimia fixed budget floor", display="Alquimia fixed budget floor")
@Help("Whole-share size=floor((initial balance / price) * Composer weight). Never exceeds the fixed sleeve budget.")
@Description("Alquimia fixed budget floor, max #MaxSize# shares")
@SortOrder(501)
@ForEngine("*,-SP,-SA")
public class AlquimiaFixedBudgetFloor extends MoneyManagementMethod {
    @Parameter(name="Maximum size", defaultValue="100", minValue=1, maxValue=1000000000, step=1)
    public double MaxSize;

    @Override
    public double computeTradeSize(StrategyBase strategy, String symbol, byte orderType,
            double price, double sl, double tickSize, double pointValue, double sizeStep) throws Exception {
        if (MaxSize < 0) throw new Exception("Money management not initialized");
        double openPrice = price > 0 ? price : (OrderTypes.isLongOrder(orderType)
                ? strategy.MarketData.Chart(symbol).Ask() : strategy.MarketData.Chart(symbol).Bid());
        if (!(openPrice > 0)) return 0;
        // This method is intentionally stock-only: one unit is one share.
        // Portfolio Composer can pass a synthetic sizeStep that is unsuitable
        // for share rounding, so never use it to quantize this calculation.
        double units = Math.floor((strategy.getInitialBalance() / openPrice) * weight);
        if (units < 0) units = 0;
        return Math.min(units, MaxSize);
    }
}
