''' This trade modules provides classes to keep track portfolios

'''
from pydantic import BaseModel
from typing import List, Dict, Set, Tuple
import datetime
import pandas as pd
import math
PRECISION = 1e-6

########################################################################
#### TradePercentage (Commision)
####
#### Usage:
#### commision = TradePercentage(0.01)
#### commision.calculate(price, amount)
########################################################################
class Commission(object):
    pass

class TradePercentage(Commission):
    def __init__(self, percentage):
        assert (percentage < 1)
        self.__percentage = percentage

    def calculate(self, price, amount):
        return price * abs(amount) * self.__percentage

########################################################################
#### Inventory
####
#### Usage:
#### inv = Inventory()
#### long: inv.long(<amount>, <price>)
#### short: inv.short(<amount>, <price>)
#### close: inv.close(<amount>, <price>)
#### cover: inv.cover(<amount>, <price>)
########################################################################
class Inventory(BaseModel):
    inventory: List = []
    islong: bool = True

    def go_short(self):
        assert len(self.inventory) == 0
        self.islong = False

    def go_long(self):
        assert len(self.inventory) == 0
        self.islong = True

    def get_amount(self):
        if len(self.inventory) > 0:
            sign = 1 if self.islong else -1
            return sign * self.inventory[0][0]
        else:
            return 0

    def get_price(self):
        if len(self.inventory) > 0:
            return self.inventory[0][1]
        else:
            return 0

    def _entry(self, amount:float, price:float):
        ''' Entry amount must be positive'''
        assert amount > 0
        assert price > 0
        if len(self.inventory) == 0:
            self.inventory.append((amount, price))
        else:
            new_amount = self.inventory[0][0] + amount
            new_avg_price = (self.inventory[0][0] * self.inventory[0][1] + amount * price) / new_amount
            self.inventory[0] = (new_amount, new_avg_price)
        return amount * price

    def _exit(self, amount:float, price:float):
        ''' Exit amount must be positive'''
        assert amount > 0
        assert price > 0
        if len(self.inventory) > 0:
            inventory_amount = abs(self.get_amount())
            avg_price = self.get_price()
            if self.islong:
                realized_profit_pct = (price - avg_price) / avg_price * 100
            else:
                realized_profit_pct = (avg_price - price) / avg_price * 100
            realized_profit_pt = amount * realized_profit_pct / 100
            if math.isclose(inventory_amount, amount):
                self.inventory = []
            else:
                self.inventory[0] = (inventory_amount - amount, avg_price)
            return (realized_profit_pt, realized_profit_pct, avg_price, amount * price)

    def long(self, amount:float, price:float):
        assert self.islong
        return self._entry(abs(amount), price)

    def close(self, amount:float, price:float):
        assert self.islong
        return self._exit(abs(amount), price)

    def short(self, amount:float, price:float):
        assert not self.islong
        return self._entry(abs(amount), price)

    def cover(self, amount:float, price:float):
        assert not self.islong
        return self._exit(abs(amount), price)

########################################################################
#### Position
########################################################################

class Position(BaseModel):
    '''
    Keep records of a position of trading pairs

    Attributes:
        strategy_exposure (float): strategy_exposure is the nominal ratio for exposures in markets from -1 to 1
        base_rate (float): base_rate is the ratio that transfer the fund to the base trading pairs (can be changed over time)
        fund (float): Fund in USD
        amount (float): Assets amounts
        target_exposure (float): Target exposure
        fee (float): Total fee incurred
        trade_log (List): trade log
        trade_profit (List): trade profit log
        balance_log (List): balance log
    '''
    strategy_exposure: float = 0
    base_rate: float = 1.0
    fund: float = 0
    fee: float = 0
    leverage: float = 1
    inv: Inventory = Inventory()
    commision: Commission = TradePercentage(0.001)
    trade_log: List = []
    trade_profit: List = []
    balance_log: List = []
    timestamp_log: List = []

    class Config:
        arbitrary_types_allowed=True

    def enough_amount(self, amount:float):
        return abs(amount) <= abs(self.get_amount()) + PRECISION

    def enough_cash(self, cash:float):
        return cash <= self.fund + PRECISION

    @staticmethod
    def cal_nav(cash, amount, price):
        return cash + amount * price # Should be +ve

    @staticmethod
    def cal_exposure(cash, amount, price):
        """ Since the exposure can be exceeds (-1,1) based on the price of the assets, 
        the real exposure shall be calculated at the time of trade
        """
        if amount == 0:
            return 0
        nav = Position.cal_nav(cash, amount, price)
        if nav <= 0:
            return 0
        else:
            return 1 - cash / nav

    def get_amount(self):
        return self.inv.get_amount()

    def get_gav(self, price):
        return Position.cal_nav(self.fund, self.get_amount(), price)

    def get_nav(self, price):
        return self.get_gav(price) - self.fee

    def long(self, amount:float, price:float, timestamp:datetime.datetime=None, notes:str=""):
        if self.inv.get_amount() == 0:
            self.inv.go_long()
        amount = abs(amount)
        cash_changed = self.inv.long(abs(amount), price)
        fee_to_pay = self.commision.calculate(price, amount)
        # Updates records
        self.fund += -1 * abs(cash_changed)
        self.fee += fee_to_pay
        self.trade_log.append({
            'timestamp':timestamp,
            'amount':amount,
            'fee':fee_to_pay,
            'price':price,
            'trade':'LONG',
            'notes':notes})
        return

    def short(self, amount:float, price:float, timestamp:datetime.datetime=None, notes:str=""):
        if self.inv.get_amount() == 0:
            self.inv.go_short()
        amount = abs(amount)
        cash_changed = self.inv.short(abs(amount), price)
        cash_changed = abs(cash_changed)
        fee_to_pay = self.commision.calculate(price, amount)
        # Updates records
        self.fund += cash_changed
        self.fee += fee_to_pay
        self.trade_log.append({
            'timestamp':timestamp,
            'amount':-amount,
            'fee':fee_to_pay,
            'price':price,
            'trade':'SHORT',
            'notes':notes})

    def close(self, amount:float, price:float, timestamp:datetime.datetime=None, notes:str=""):
        amount = abs(amount)
        realized_profit_pt, realized_profit_pct, avg_price, cash_changed = self.inv.close(abs(amount), price)
        realized_profit = realized_profit_pt * self.base_rate * price
        fee_to_pay = self.commision.calculate(price, amount)
        cash_changed = abs(cash_changed)
        # Updates records
        self.fund += cash_changed
        self.fee += fee_to_pay
        self.trade_log.append({
            'timestamp':timestamp,
            'amount':-abs(amount),
            'fee':fee_to_pay,
            'price':price,
            'trade':'CLOSE',
            'notes':notes})
        self.trade_profit.append({
            'timestamp':timestamp,
            'amount':abs(amount),
            'exit_price':price,
            'enter_price':avg_price,
            'realized_profit':realized_profit,
            'realized_profit_pt':realized_profit_pt,
            'realized_profit_pct':realized_profit_pct,
            'trade':'LONG'})

    def cover(self, amount:float, price:float, timestamp:datetime.datetime=None, notes:str=""):
        amount = abs(amount)
        realized_profit_pt, realized_profit_pct, avg_price, cash_changed = self.inv.cover(abs(amount), price)
        realized_profit = realized_profit_pt * self.base_rate * price
        fee_to_pay = self.commision.calculate(price, amount)
        cash_changed = -1 * abs(cash_changed)
        # Updates records
        self.fund += cash_changed
        self.fee += fee_to_pay
        self.trade_log.append({
            'timestamp':timestamp,
            'amount':abs(amount),
            'fee':fee_to_pay,
            'price':price,
            'trade':'COVER',
            'notes':notes})
        self.trade_profit.append({
            'timestamp':timestamp,
            'amount':-abs(amount),
            'exit_price':price,
            'enter_price':avg_price,
            'realized_profit':realized_profit,
            'realized_profit_pt':realized_profit_pt,
            'realized_profit_pct':realized_profit_pct,
            'trade':'SHORT'})

    def update_base_rate(self, rate):
        self.base_rate = rate

    def set_commision(self, commision: Commission):
        self.commision = commision

    def extract_fund(self):
        fund = self.fund
        self.fund = 0
        return fund

    def deposit_fund(self, fund):
        self.fund = fund

    def summary(self):
        return {'fund':self.fund, 'amount':self.get_amount(), 'strategy_exposure':self.strategy_exposure, 'fee':self.fee, 'base_rate':self.base_rate}

    def allocate(self, new_exposure: float, price: float, timestamp=None, notes=""):
        ''' To allocate the fund into specific exposure amount for the following case:
| old_exposure | new_exposure | conditions                                                            | amount_changed                            |
|--------------|--------------|-----------------------------------------------------------------------|-------------------------------------------|
| +ve          | 0            | old_exposure > 0 and new_exposure == 0                                | amount                                    |
| +ve          | more +ve     | old_exposure > 0 and new_exposure > 0 and new_exposure > old_exposure | nav * (new_exposure - exposure) / price   |
| +ve          | less +ve     | old_exposure > 0 and new_exposure > 0 and new_exposure < old_exposure | nav * (new_exposure - exposure) / price   |
| +ve          | -ve          | old_exposure > 0 and new_exposure < 0                                 | amount then nav * (new_exposure) / price  |
| 0            | +ve          | old_exposure == 0 and new_exposure > 0                                | nav * (new_exposure) / price              |
| 0            | -ve          | old_exposure == 0 and new_exposure < 0                                | nav * (new_exposure) / price              |
| -ve          | 0            | old_exposure < 0 and new_exposure == 0                                | amount                                    |
| -ve          | more -ve     | old_exposure < 0 and new_exposure < 0 and new_exposure < old_exposure | nav * (exposure - new_exposure) / price   |
| -ve          | less -ve     | old_exposure < 0 and new_exposure < 0 and new_exposure > old_exposure | nav * (exposure -  new_exposure ) / price |
| -ve          | +ve          | old_exposure < 0 and new_exposure > 0                                 | amount then nav * (new_exposure) / price  |
        '''
        old_exposure = self.strategy_exposure
        amount = self.inv.get_amount()
        exposure = Position.cal_exposure(self.fund, amount, price)
        nav = Position.cal_nav(self.fund, amount, price)

        # Return if old_exposure is very close to new_exposure
        if math.isclose(old_exposure, new_exposure):
            return None

        # Different case
        if old_exposure > 0:
            if  math.isclose(new_exposure, 0):
                amount_changed = amount
                self.close(amount_changed, price, timestamp=timestamp, notes=notes)
            elif new_exposure > 0 and new_exposure > old_exposure:
                amount_changed = nav * (new_exposure - exposure) / price
                self.long(amount_changed, price, timestamp=timestamp, notes=notes)
            elif new_exposure > 0 and new_exposure < old_exposure:
                amount_changed = nav * (new_exposure - exposure) / price
                self.close(amount_changed, price, timestamp=timestamp, notes=notes)
            elif new_exposure < 0:
                # Close 
                amount_changed = amount
                self.close(amount_changed, price, timestamp=timestamp, notes=notes)
                # Short
                amount_changed = nav * new_exposure / price
                self.short(amount_changed, price, timestamp=timestamp, notes=notes)
        elif math.isclose(old_exposure, 0):
            if new_exposure > 0:
                amount_changed = nav * (new_exposure) / price
                self.long(amount_changed, price, timestamp=timestamp, notes=notes)
            elif new_exposure < 0:
                amount_changed = nav * (new_exposure) / price
                self.short(amount_changed, price, timestamp=timestamp, notes=notes)
        elif old_exposure < 0:
            if math.isclose(new_exposure, 0):
                amount_changed = amount
                self.cover(amount_changed, price, timestamp=timestamp, notes=notes)
            elif new_exposure < 0 and new_exposure > old_exposure:
                amount_changed = nav * (exposure - new_exposure) / price 
                self.cover(amount_changed, price, timestamp=timestamp, notes=notes)
            elif new_exposure < 0 and new_exposure < old_exposure:
                amount_changed = nav * (exposure - new_exposure) / price 
                self.short(amount_changed, price, timestamp=timestamp, notes=notes)
            elif new_exposure > 0:
                # Cover
                amount_changed = amount
                self.cover(amount_changed, price, timestamp=timestamp, notes=notes)
                # Long
                amount_changed = nav * (new_exposure) / price
                self.long(amount_changed, price, timestamp=timestamp, notes=notes)
        # Update the strategy exposure
        self.strategy_exposure = new_exposure
        return

    def end_date(self, timestamp, price):
        summary = self.summary()
        summary.update({'timestamp':timestamp})
        summary.update({'price':price})
        summary.update({'gav': self.get_gav(price)})
        summary.update({'nav': self.get_nav(price)})
        summary.update({'exposure': Position.cal_exposure(summary['fund'], summary['amount'], price)})
        self.balance_log.append(summary)
        self.timestamp_log.append(timestamp)

    def get_trade_profit(self):
        return pd.DataFrame(self.trade_profit)

    def get_trade_log(self):
        return pd.DataFrame(self.trade_log)

    def get_balance_log(self):
        return pd.DataFrame(self.balance_log, index=self.timestamp_log)