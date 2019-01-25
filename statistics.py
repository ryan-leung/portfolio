from collections import OrderedDict
import pandas as pd
import numpy as np
from copy import copy

########################################################################
#### Statistics
#### Initilize with strategy config and dict of ``positions`` of trading pairs (from trade.py)
####
#### Usage:
#### stat = Statistics(config, positions)
#### stat.calculate()
#### stat.trade_summary()
#### stat.nav_summary()
#### stat.report()
########################################################################


class Statistics(object):
    def __init__(self, config, positions, fixed_cash=0):
        self.config = config
        self.positions = positions
        self.balance_log = None
        self.equity = None
        self.trade_profit = None
        self.fixed_cash = fixed_cash

    def calculate(self):
        symbols = list(self.positions.keys())
        self.equity = pd.concat([self.positions[s].get_balance_log()['nav'] for s in symbols], keys=symbols, axis=1).sum(axis=1) + self.fixed_cash
        self.gav = pd.concat([self.positions[s].get_balance_log()['gav'] for s in symbols], keys=symbols, axis=1).sum(axis=1) + self.fixed_cash
        self.balance_log = pd.concat([self.positions[s].get_balance_log() for s in symbols], keys=symbols, axis=1)
        self.trade_profit = pd.concat([self.positions[s].get_trade_profit() for s in symbols], keys=symbols)
        self.trade_profit.reset_index(inplace=True)
        self.trade_profit = self.trade_profit.set_index('timestamp').sort_index()

    def get_long_trades(self):
        return self.trade_profit[self.trade_profit['trade'] == 'LONG']

    def get_short_trades(self):
        return self.trade_profit[self.trade_profit['trade'] == 'SHORT']

    def nav_summary(self, raw=False):
        results = OrderedDict([
            ["Initial Capital", self.config.fund],
            ["Ending Capital", self.equity[-1]],
            ["Trade Start", self.config.start_time],
            ["Trade End", self.config.end_time],
            ["Trade Days", self.config.end_time - self.config.start_time],
            ["Gross Profit", self.gav[-1] - self.config.fund],
            ["Gross Profit %", (self.gav[-1] - self.config.fund) / self.config.fund * 100],
            ["Net Profit", self.equity[-1] - self.config.fund],
            ["Net Profit %", (self.equity[-1] - self.config.fund) / self.config.fund * 100],
            ["Maximum Drawdown %", max_drawdown(self.equity) * 100],
            ["Annual Return %", annualized_return(self.equity, self.config.fund) * 100],
            ["Sharpe Ratio", sharpe_ratio(self.equity)],
            ["Trading Fee", self.balance_log.swaplevel(axis=1)['fee'].values.sum()],
        ])
        if raw:
            return results
        else:
            return pd.DataFrame([results], columns=results.keys()).T

    def monthly_return(self):
        df = copy(self.equity)
        df.index = pd.to_datetime(df.index)
        df['year'] = df.index.year
        df['month'] = df.index.month
        end_date_of_month = df.asfreq('BM').set_index(['year', 'month'])
        first_date_of_month = df.asfreq('BMS').set_index(['year', 'month'])
        pct = end_date_of_month.pct_change()
        if pd.isna(pct[0][0]):
            pct[0][0] = end_date_of_month[0][0] / first_date_of_month[0][0] - 1
        return pct

    def trade_summary(self, raw=False):
        columns = ['All', 'Long', 'Short']
        long_trades = self.get_long_trades()
        short_trades = self.get_short_trades()
        def cal_trades(trades):
            winning_mask = trades['realized_pnl']>0
            lossing_mask = trades['realized_pnl']<=0
            return OrderedDict([
                ["Total Trades", len(trades)],
                ["Avg. Profit/Loss", trades['realized_gross_profit'].mean()],
                ["Avg. Profit/Loss %", trades['realized_pnl'].mean()],
                ["Winning Trades", winning_mask.sum()],
                ["Winning Trades %", winning_mask.sum()/len(trades)*100],
                ["Winning Trades Avg. Profit", trades[winning_mask]['realized_gross_profit'].mean()],
                ["Winning Trades Avg. Profit %", trades[winning_mask]['realized_pnl'].mean()],
                ["Lossing Trades", lossing_mask.sum()],
                ["Lossing Trades %", lossing_mask.sum()/len(trades)*100],
                ["Lossing Trades Avg. Profit", trades[lossing_mask]['realized_gross_profit'].mean()],
                ["Lossing Trades Avg. Profit %", trades[lossing_mask]['realized_pnl'].mean()],
            ])
        results = [
            cal_trades(self.trade_profit),
            cal_trades(long_trades),
            cal_trades(short_trades),
        ]
        if raw:
            return results
        else:
            return pd.DataFrame(results, index=columns, columns=results[0].keys()).T

    def report(self):
        pass

########################################################################
#### Metrics
#### Functions used to compute metrics of portfolios
####
########################################################################

def drawdowns(ser):
    """A drawdown is the peak-to-trough decline during a specific recorded period
    https://stackoverflow.com/questions/22607324/start-end-and-duration-of-maximum-drawdown-in-python
    """
    vec = ser.values
    maximums = np.maximum.accumulate(vec)
    return 1 - vec / maximums

def max_drawdown(ser):
    return np.max(drawdowns(ser))

def annualized_return(ts, initial_fund=None):
    '''An annualized total return is the geometric average amount of money earned by an investment 
    each year over a given time period. It is calculated as a geometric average to show what an 
    investor would earn over a period of time if the annual return was compounded. 
    An annualized total return provides only a snapshot of an investment's performance 
    and does not give investors any indication of its volatility.
    https://www.investopedia.com/terms/a/annualized-total-return.asp
    '''
    if initial_fund is None:
        initial_fund = ts[0]
    ar = (ts[-1] - initial_fund) / initial_fund
    ar = (1 + ar) ** (365 / len(ts)) - 1
    return ar

def sharpe_ratio(ts, rff=0.03):
    #Rolling profit
    r = ts.pct_change(1)
    #Annualized return
    ar = annualized_return(ts)
    #Sharpe ratio
    return (ar - rff)/(r.std()*np.sqrt(365))
