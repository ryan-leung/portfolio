from pydantic import BaseModel
from portfolio import trade
import json
from google.cloud import datastore

import structlog
logger = structlog.getLogger()

class Portfolio(object):
    def __init__(self, fund, allocations):
        self.symbols = list(allocations.keys())
        self.fund = fund
        self.allocations = allocations
        self.positions = {symbol: trade.Position(fund=fund * allo) for symbol, allo in allocations.items()}
        self.client = None
        self.datastore_key = ('Positions', 10000)
    
    def connect(self, project_id):
        self.client = datastore.Client(project_id)
    
    #def __repr__(self):
        #return json.dumps({symbol: item.dict() for symbol, item in self.positions.items()})
    
    @staticmethod
    def serialize(p):
        result = {'positions':{}}
        for symbol, pos in p.positions.items():
            result['positions'][symbol] = pos.dict()
            del result['positions'][symbol]['commision']
        result['symbols'] = p.symbols
        result['fund'] = p.fund
        result['allocations'] = p.allocations
        return result
    
    def load(self, kind, key_name):
        key = self.client.key(kind, key_name)
        result = self.client.get(key)
        logger.log("load", kind=kind, key=key, result=result)
        if result:
            self.symbols = result['symbols']
            self.fund = result['fund']
            self.allocations = result['allocations']
            self.positions = {symbol: trade.Position(**pos) for symbol, pos in result['positions'].items()}
            self.datastore_key = (kind, key_name)
            return result
        else:
            self.datastore_key = (kind, key_name)
            return None
        
    def save(self):
        print(self.datastore_key[0], self.datastore_key[1])
        key = self.client.key(self.datastore_key[0], self.datastore_key[1])
        entity = datastore.Entity(key=key)
        entity.update(Portfolio.serialize(self))
        result = self.client.put(entity)
        logger.log("save", kind=self.datastore_key[0], key=self.datastore_key[1], result=result)
        return result