#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime
import TransactionFee
from numpy import floor, abs

def NotExchFund(ticker):
    return ticker.startswith('16')

class ABFundPos(object):
    
    def __init__(self, *args, **kwargs):
        # basic info
        self.ticker             = {}
        self.ticker['Ticker']   = kwargs['Ticker']
        self.ticker['ATicker']  = kwargs['ATicker']
        self.ticker['BTicker']  = kwargs['BTicker']
        self.weight             = {}
        self.weight['AWeight']  = kwargs['AWeight']
        self.weight['BWeight']  = kwargs['BWeight']
        self.weight['UpFold']   = kwargs['UpFold']
        self.weight['DownFold'] = kwargs['DownFold']
        # initial px info
        self.sttpx              = {}
        self.sttpx['FundPrice'] = kwargs['FundPrice']
        self.sttpx['APrice']    = kwargs['APrice']
        self.sttpx['BPrice']    = kwargs['BPrice']
        self.sttpx['FundValue'] = kwargs['FundValue']
        self.sttpx['AValue']    = kwargs['AValue']
        self.sttpx['BValue']    = kwargs['BValue']
        self.sttpx['FundAmount']= kwargs['FundAmount']
        self.sttpx['AAmount']   = kwargs['AAmount']
        self.sttpx['BAmount']   = kwargs['BAmount']
        # px status
        self.lastpx             = dict(self.sttpx)
        self.startDate          = kwargs['StartDate']
        self.endDate            = datetime.date(9999, 12, 31)
        self.lastDate           = self.startDate
        self.evolveCounter      = 0
        # flags
        self.unwinded           = False
        self.upfolded           = False
        self.downfolded         = False
        self.isAlloced          = False
        self.unitshare          = 1000
        self.notExchTraded      = NotExchFund(self.ticker['Ticker'])
        # upfold/downfold
        assert kwargs['UpFold'] > kwargs['DownFold'], "upfold barrier smaller than downfold barrier for %s" % kwargs['Ticker']
        if self.sttpx['BValue'] > kwargs['UpFold']:
            # upfold happens at init date
            self.upfolded = True
        elif self.sttpx['BValue'] < kwargs['DownFold']:
            # downfold happens at init date
            self.downfolded = True
        
    def evolve(self, latestpx):
        raise NotImplementedError
        
    def setupAllocAmount(self, cashAmount):
        raise NotImplementedError   
        
    @staticmethod
    def getArbMargin(Ticker):
        raise NotImplementedError

    @staticmethod
    def validate(px):
        # always need BValue to check whether it is in normal status
        validvalue = px['AValue'] > 0.01 and px['BValue'] > 0.01 and px['FundValue'] > 0.01
        validprice = px['APrice'] > 0.01 and px['BPrice'] > 0.01 and px['FundPrice'] > 0.01 and abs(px['FundPrice']-1.0) > 1.e-8
        return validvalue and validprice
    
    def getTicker(self):
        return self.ticker['Ticker']

    def getStartDate(self):
        raise self.startDate
    
    def isLive(self):
        return not self.unwinded
    
    def getEndDate(self):
        return self.endDate
    
    def getFundPos(self):
        return self.lastPos
    
    def getSummary(self):
        outdict   = {}
        outdict.update(self.ticker)
        outdict.update(self.sttpx)
        outdict.update(self.sttPos)
        for key in self.lastpx:
            outdict['last'+key] = self.lastpx[key]
        for key in self.lastPos:
            outdict['last'+key] = self.lastPos[key]
            
        outdict['startDate']  = self.startDate.strftime("%Y%m%d")
        outdict['endDate']    = self.endDate.strftime("%Y%m%d")
        outdict['upfolded']   = str(self.upfolded)
        outdict['downfolded'] = str(self.downfolded)
        outdict['totalPnL']   = str(self.totalpnl)
        outdict['estPnL']     = str(self.estpnl)
        outdict['mktPnL']     = str(self.mktpnl)
        outdict['sttCost']    = str(self.sttCost)
        outdict['lastMTM']    = str(self.lastMTM)
        outdict['type']       = self.type
        
        for key in self.sttpx:
            outdict[key]        = str(outdict[key])
            outdict['last'+key] = str(outdict['last'+key])
        for key in self.sttPos:
            outdict[key]        = str(outdict[key])
            outdict['last'+key] = str(outdict['last'+key])
            
        return outdict  
        
class ABMergePos(ABFundPos):
    
    def __init__(self, *args, **kwargs):
        # basic fact
        super(ABMergePos, self).__init__(*args, **kwargs)
        self.type = 'MERGE'
    
    @staticmethod
    def getArbMargin(Ticker, px, wt):
        if not ABFundPos.validate(px):
            return 0.0
            
        apx     = px['APrice']
        bpx     = px['BPrice']
        buyFee  = 0.
        sellFee = 0. 
        fval    = 0.     
        if NotExchFund(Ticker):
            buyFee  = TransactionFee.TxFeeFundExchTrade().getTxFeeRate()
            sellFee = TransactionFee.TxFeeFundRedemp().getTxFeeRate()
            fval    = px['FundValue']
        else:
            buyFee  = TransactionFee.TxFeeFundExchTrade().getTxFeeRate()
            sellFee = buyFee
            fval    = px['FundPrice']
        margin = fval / (apx * wt['AWeight'] + bpx * wt['BWeight']) - 1. - buyFee - sellFee
        return max([margin, 0.0])
    
    def setupAllocAmount(self, cashAmount):
        if self.notExchTraded:
            self.buyFeeRate  = TransactionFee.TxFeeFundExchTrade().getTxFeeRate()
            self.sellFeeRate = TransactionFee.TxFeeFundRedemp().getTxFeeRate()
            self.unwindRate  = self.buyFeeRate 
        else:
            self.buyFeeRate  = TransactionFee.TxFeeFundExchTrade().getTxFeeRate()
            self.sellFeeRate = self.buyFeeRate            
            self.unwindRate  = self.buyFeeRate 
        
        unitapx        = self.unitshare * self.weight['AWeight'] * self.sttpx['APrice']
        unitbpx        = self.unitshare * self.weight['BWeight'] * self.sttpx['BPrice']
        unitpx         = unitapx + unitbpx
        unitpxwfee     = unitpx * (1 + self.buyFeeRate)
        nbunits        = floor(cashAmount / unitpxwfee)
        self.sttCost   = unitpxwfee * nbunits
        self.sttFee    = (unitpxwfee - unitpx) * nbunits
        nbshare        = nbunits * self.unitshare
        self.sttPos    = {'Fund': 0., 'A': self.weight['AWeight'] * nbshare, 'B': self.weight['BWeight'] * nbshare}
        self.lastPos   = dict(self.sttPos)
        self.lastMTM   = (self.sttCost - self.sttFee) * (1 - self.unwindRate)
        if self.upfolded:
            ashare       = self.lastPos['A']
            bshare       = self.lastPos['B']
            fshare       = ashare * self.lastpx['AValue'] + bshare * self.lastpx['BValue'] - ashare - bshare
            self.lastPos = {'Fund': fshare, 'A': ashare, 'B': bshare}
        elif self.downfolded:
            ashare       = self.lastPos['A']
            bshare       = self.lastPos['B']
            fshare       = ashare * (self.lastpx['AValue'] - self.lastpx['BValue'])
            self.lastPos = {'Fund': fshare, 'A': ashare * self.lastpx['BValue'], 'B': bshare * self.lastpx['BValue']}       
        self.isAlloced = True
        # return the cash flow
        return self.sttCost

    def evolve(self, date, px):
        if not self.isAlloced:
            raise "No cash alloced, need to call setupAllocAmount to init"
        if date <= self.lastDate:
            raise "Should not evolve to past date %s while evolve date is %s" % (date.strftime("%Y%m%d"), self.lastDate.strftime("%Y%m%d"))
        if self.unwinded:
            return (0., 0.) # only return zero MTM/Cashflow, do nothing
        if self.validate(px):
            self.evolveCounter += 1
            self.lastpx   = dict(px)
            self.lastDate = date
            # T+1 we will merge position
            if self.evolveCounter == 1:
                self.lastPos  = {'Fund': self.lastPos['Fund']+self.lastPos['A']+self.lastPos['B'], 'A': 0., 'B': 0.}
                fval          = px['FundValue'] if self.notExchTraded else px['FundPrice']
                self.lastMTM  = self.lastPos['Fund'] * fval * (1 - self.sellFeeRate)                
                if (px['BValue'] > self.weight['UpFold'] or px['BValue'] < self.weight['DownFold']):
                    if self.downfolded or self.upfolded:
                        raise "ticker %s, pos stt %s, date %s, multiple fold happen" % ('/'.join(self.Ticker), self.startDate.strftime("%Y%m%d"), date.strftime("%Y%m%d"))
                    self.upfolded   = True if px['BValue'] > self.weight['UpFold'] else False
                    self.downfolded = False if px['BValue'] > self.weight['UpFold'] else True
                    self.lastPos    = {'Fund': self.lastPos['Fund']*self.lastpx['FundValue'], 'A': 0., 'B': 0.}
                return (self.lastMTM, 0.)                
            # T+2 we will be able to unwind the position
            elif self.evolveCounter == 2:
                self.unwinded = True
                self.endDate  = date
                fval          = px['FundValue'] if self.notExchTraded else px['FundPrice']
                self.lastMTM  = self.lastPos['Fund'] * fval * (1 - self.sellFeeRate)                
                return (0., self.lastMTM)            
        else:
            return (self.lastMTM, 0.)
            
    def getSummary(self):
        self.totalpnl  = self.lastMTM - self.sttCost
        fval           = self.sttpx['FundValue'] if self.notExchTraded else self.sttpx['FundPrice']
        self.estpnl    = (self.sttPos['A'] + self.sttPos['B']) * fval * (1 - self.sellFeeRate) - self.sttCost
        self.mktpnl    = self.totalpnl - self.estpnl
        return super(ABMergePos, self).getSummary()
        
class FundSplitPos(ABFundPos):
    
    def __init__(self, *args, **kwargs):
        # basic fact
        super(FundSplitPos, self).__init__(*args, **kwargs)
        self.type = 'SPLIT'
    
    @staticmethod
    def getArbMargin(Ticker, px, wt):
        if not ABFundPos.validate(px):
            return 0.0
            
        apx     = px['APrice']
        bpx     = px['BPrice']  
        buyFee  = 0.
        sellFee = 0. 
        fval    = 0.     
        if NotExchFund(Ticker):
            buyFee  = TransactionFee.TxFeeFundSub().getTxFeeRate()
            sellFee = TransactionFee.TxFeeFundExchTrade().getTxFeeRate()
            fval    = px['FundValue']
        else:
            buyFee  = TransactionFee.TxFeeFundExchTrade().getTxFeeRate()
            sellFee = buyFee
            fval    = px['FundPrice']
        margin = (apx * wt['AWeight'] + bpx * wt['BWeight']) / fval - 1. - buyFee - sellFee
        return max([margin, 0.0])
    
    def setupAllocAmount(self, cashAmount):
        unitpx = 0.0
        if self.notExchTraded:
            self.buyFeeRate  = TransactionFee.TxFeeFundSub().getTxFeeRate()
            self.sellFeeRate = TransactionFee.TxFeeFundExchTrade().getTxFeeRate()
            self.unwindRate  = TransactionFee.TxFeeFundRedemp().getTxFeeRate()
            unitpx           = self.unitshare * self.sttpx['FundValue']
        else:
            self.buyFeeRate  = TransactionFee.TxFeeFundExchTrade().getTxFeeRate()
            self.sellFeeRate = self.buyFeeRate 
            self.unwindRate  = self.buyFeeRate 
            unitpx           = self.unitshare * self.sttpx['FundPrice']
        
        unitpxwfee     = unitpx * (1 + self.buyFeeRate)
        nbunits        = floor(cashAmount / unitpxwfee)
        self.sttCost   = unitpxwfee * nbunits
        self.sttFee    = (unitpxwfee - unitpx) * nbunits
        nbshare        = nbunits * self.unitshare
        self.sttPos    = {'Fund': nbshare, 'A': 0., 'B': 0.}
        self.lastPos   = dict(self.sttPos)
        self.lastMTM   = (self.sttCost - self.sttFee) * (1 - self.unwindRate)
        if self.upfolded or self.downfolded:
            self.lastPos = {'Fund': self.lastPos['Fund']*self.lastpx['FundValue'], 'A': 0., 'B': 0.}
        self.isAlloced = True
        # return the cash flow
        return self.sttCost

    def evolve(self, date, px):
        if not self.isAlloced:
            raise "No cash alloced, need to call setupAllocAmount to init"
        if date < self.lastDate:
            raise "Should not evolve to past date %s while evolve date is %s" % (date.strftime("%Y%m%d"), self.lastDate.strftime("%Y%m%d"))
        if self.unwinded:
            return (0., 0.) # only return zero MTM/Cashflow, do nothing
        if self.validate(px):
            self.evolveCounter += 1
            self.lastpx   = dict(px)
            self.lastDate = date
            # T+1 still base fund
            if self.evolveCounter == 1:
                fval         = px['FundValue'] if self.notExchTraded else px['FundPrice']
                self.lastMTM = self.lastPos['Fund'] * fval * (1 - self.unwindRate)
                if (px['BValue'] > self.weight['UpFold'] or px['BValue'] < self.weight['DownFold']):
                    if self.downfolded or self.upfolded:
                        raise "ticker %s, pos stt %s, date %s, multiple fold happen" % ('/'.join(self.Ticker), self.startDate.strftime("%Y%m%d"), date.strftime("%Y%m%d"))
                    self.upfolded   = True if px['BValue'] > self.weight['UpFold'] else False
                    self.downfolded = False if px['BValue'] > self.weight['UpFold'] else True
                    self.lastPos    = {'Fund': self.lastPos['Fund']*self.lastpx['FundValue'], 'A': 0., 'B': 0.}
                return (self.lastMTM, 0.)
            # T+2 will split
            elif self.evolveCounter == 2:
                self.lastPos = {'Fund': 0., 'A': self.lastPos['Fund']*self.weight['AWeight'], 'B': self.lastPos['Fund']*self.weight['BWeight']}
                self.lastMTM = (self.lastPos['A'] * px['APrice'] + self.lastPos['B'] * px['BPrice']) * (1 - self.sellFeeRate)
                if (px['BValue'] > self.weight['UpFold'] or px['BValue'] < self.weight['DownFold']):
                    if self.downfolded or self.upfolded:
                        raise "ticker %s, pos stt %s, date %s, multiple fold happen" % ('/'.join(self.Ticker), self.startDate.strftime("%Y%m%d"), date.strftime("%Y%m%d"))
                    self.upfolded   = True if px['BValue'] > self.weight['UpFold'] else False
                    self.downfolded = False if px['BValue'] > self.weight['UpFold'] else True
                    if self.upfolded:
                        ashare       = self.lastPos['A']
                        bshare       = self.lastPos['B']
                        fshare       = ashare * self.lastpx['AValue'] + bshare * self.lastpx['BValue'] - ashare - bshare
                        self.lastPos = {'Fund': fshare, 'A': ashare, 'B': bshare}        
                    elif self.downfolded:
                        ashare       = self.lastPos['A']
                        bshare       = self.lastPos['B']
                        fshare       = ashare * (self.lastpx['AValue'] - self.lastpx['BValue'])
                        self.lastPos = {'Fund': fshare, 'A': ashare * self.lastpx['BValue'], 'B': bshare * self.lastpx['BValue']}
                return (self.lastMTM, 0.)
            # T+3 will unwind
            elif self.evolveCounter == 3:
                self.unwinded = True
                self.endDate  = date
                fval          = px['FundValue'] if self.notExchTraded else px['FundPrice']
                self.lastMTM  = self.lastPos['Fund'] * fval * (1 - self.unwindRate) + (self.lastPos['A'] * px['APrice'] + self.lastPos['B'] * px['BPrice']) * (1 - self.sellFeeRate)
                return (0., self.lastMTM)  
        else:
            return (self.lastMTM, 0.)
            
    def getSummary(self):
        self.totalpnl  = self.lastMTM - self.sttCost
        self.estpnl    = (self.sttPos['Fund'] * self.weight['AWeight'] * self.sttpx['APrice'] + self.sttPos['Fund'] * self.weight['BWeight'] * self.sttpx['BPrice']) * (1 - self.sellFeeRate) - self.sttCost
        self.mktpnl    = self.totalpnl - self.estpnl
        return super(FundSplitPos, self).getSummary()
        