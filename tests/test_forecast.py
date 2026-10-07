from dqs.models import Candle, RangeBracket, HitLevel
from dqs.quant.features import calculate_features
from dqs.quant.forecast import simulate


def candles(n=900):
    out=[]
    price=83000.0
    for i in range(n):
        move = ((i % 13) - 6) * 0.00008
        o=price
        c=o*(1+move)
        h=max(o,c)*1.0008
        l=min(o,c)*0.9992
        out.append(Candle(i*900000,o,h,l,c,100+i%10,(i+1)*900000-1))
        price=c
    return out


def test_deterministic_forecast():
    cs=candles()
    f=calculate_features(cs)
    brackets=[RangeBracket(80000,82000,"80-82"),RangeBracket(82000,84000,"82-84"),RangeBracket(84000,86000,"84-86")]
    hits=[HitLevel(85000,"UP","up85"),HitLevel(81000,"DOWN","down81")]
    a=simulate(cs,f,10,20,brackets,hits,500,123)
    b=simulate(cs,f,10,20,brackets,hits,500,123)
    assert a["range_probabilities"] == b["range_probabilities"]
    assert a["hit_probabilities"] == b["hit_probabilities"]
