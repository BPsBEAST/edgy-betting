#!/usr/bin/env python3
"""Exploratory historical markets from actual Football-Data CSV statistics.

One single data source; distributions are assumptions, not backtested tips.
Never promote output beyond OBSERVAR without independent information.
"""
from datetime import datetime, timezone
from math import exp, factorial, sqrt, ceil, isfinite

NOW=datetime.now(timezone.utc)

def parse_date(raw):
    for fmt in ("%d/%m/%Y","%d/%m/%y","%Y-%m-%d"):
        try:return datetime.strptime(str(raw),fmt).replace(tzinfo=timezone.utc)
        except ValueError:pass
    return None

def poisson(rate,n):
    return exp(-rate)*rate**n/factorial(n)

def over_prob(rate,threshold):
    if rate<0:return None
    p=exp(-rate)
    total=p
    for j in range(1,threshold+1):
        p*=rate/j
        total+=p
    return max(0.,min(1.,1-total))

def recents(team,rows):
    fields=(("HT","HTHG","HTAG"),("C","HC","AC"),
            ("S","HS","AS"),("ST","HST","AST"))
    matches=[]
    for r in rows:
        at_home=r.get("HomeTeam")==team
        at_away=r.get("AwayTeam")==team
        if not at_home and not at_away:continue
        date=parse_date(r.get("Date"))
        if date is None or date>=NOW:continue
        match={"date":date.isoformat(),"side":"home" if at_home else "away"}
        for metric,home,away in fields:
            for label,key in (("for",home if at_home else away),
                              ("against",away if at_home else home)):
                txt=str(r.get(key) or "").strip()
                val=int(txt) if txt.isdigit() else None
                if val is not None and 0<=val<=85:
                    match[metric+"_"+label]=val
        matches.append(match)
    matches.sort(key=lambda r:r["date"],reverse=True)
    return matches[:12]

def metric_rate(home,away,key):
    home_games=[r for r in home if r["side"]=="home"]
    away_games=[r for r in away if r["side"]=="away"]
    hf=[r[key+"_for"] for r in home_games if key+"_for" in r]
    ha=[r[key+"_against"] for r in home_games if key+"_against" in r]
    af=[r[key+"_for"] for r in away_games if key+"_for" in r]
    aa=[r[key+"_against"] for r in away_games if key+"_against" in r]
    n=min(len(hf),len(ha),len(af),len(aa))
    if n<3:return None
    # Attack and opponent defence independently inform match-up rates, but
    # originate in the SAME underlying Football-Data CSV sample.
    home_rate=(sum(hf)/len(hf)+sum(aa)/len(aa))/2
    away_rate=(sum(af)/len(af)+sum(ha)/len(ha))/2
    return home_rate,away_rate,n

def enrich(result,home,away,rows,division=1):
    h=recents(home,rows)
    a=recents(away,rows)
    additions=[]
    evidence={}
    def emit(key,group,label,p,source_unc,method,n):
        if p is None or not isfinite(p) or not 0<=p<=1:return
        unc=min(.32,(source_unc+.025+max(0,6-n)*.008)*(1.10 if division==2 else 1))
        need=p-unc-.03
        minimum=ceil(100/need)/100 if need>.01 else None
        additions.append({
          "key":key,"group":group,"label":label,"probability":round(p,5),
          "uncertainty":round(unc,5),"minimumOdd":minimum,"sample":n,
          "source":"Football-Data.co.uk — uma única fonte",
          "method":method,"status":"OBSERVAR",
          "reason":"Projeção histórica, não comprovada por duas fontes independentes nem pelo boletim Betano."})
    halftime=metric_rate(h,a,"HT")
    if halftime:
        lh,la,n=halftime
        evidence["halftime"]={"expectedHome":round(lh,3),"expectedAway":round(la,3),"samplePerVenue":n}
        cap=max(7,int(max(lh,la)+7))
        grid=[(x,y,poisson(lh,x)*poisson(la,y)) for x in range(cap+1) for y in range(cap+1)]
        divisor=sum(z for x,y,z in grid)
        if divisor>0:
            def pcheck(fn):return sum(z for x,y,z in grid if fn(x,y))/divisor
            for key,label,predicate in [
                ("HT_H","Casa vence ao intervalo",lambda x,y:x>y),
                ("HT_D","Empate ao intervalo",lambda x,y:x==y),
                ("HT_A","Fora vence ao intervalo",lambda x,y:x<y),
                ("HT_O05","Intervalo: mais de 0,5 golos",lambda x,y:x+y>=1),
                ("HT_U05","Intervalo: menos de 0,5 golos",lambda x,y:x+y==0),
                ("HT_O15","Intervalo: mais de 1,5 golos",lambda x,y:x+y>=2),
                ("HT_U15","Intervalo: menos de 1,5 golos",lambda x,y:x+y<2)]:
                emit(key,"Intervalo",label,pcheck(predicate),.075,"Poisson aproximado, resultados reais ao intervalo",n)
    for metric,group,prefix,lines,unc,name in [
        ("C","Cantos","C",(7,8,9,10),.10,"cantos"),
        ("S","Remates","S",(17,19,21),.12,"remates"),
        ("ST","Remates","ST",(5,6,7),.13,"remates à baliza")]:
        rate=metric_rate(h,a,metric)
        if not rate:continue
        lh,la,n=rate
        if lh+la<.05:continue
        evidence[metric]={"expectedHome":round(lh,3),"expectedAway":round(la,3),
                          "expectedTotal":round(lh+la,3),"samplePerVenue":n}
        for count in lines:
            over=over_prob(lh+la,count)
            part=str(count)+"5"
            name_line=str(count)+",5"
            method="Poisson exploratório de estatísticas de uma única origem; dispersão não calibrada"
            emit(prefix+"_O"+part,group,"Mais de "+name_line+" "+name,over,unc,method,n)
            emit(prefix+"_U"+part,group,"Menos de "+name_line+" "+name,1-over,unc,method,n)
    # Correlated combinations from a JOINT score matrix, not multiplication
    # of two independent probabilities.
    lh=result.get("lambdaHome");la=result.get("lambdaAway")
    if isinstance(lh,(int,float)) and isinstance(la,(int,float)) and lh>=0 and la>=0:
        matrix=[(x,y,poisson(lh,x)*poisson(la,y)) for x in range(13) for y in range(13)]
        norm=sum(z for x,y,z in matrix)
        n=min(result["home"]["homeGames"],result["away"]["awayGames"])
        if norm>.99:
            for key,label,predicate in [
                ("CMB_1O15","Casa ganha e mais de 1,5 golos",lambda x,y:x>y and x+y>=2),
                ("CMB_2O15","Fora ganha e mais de 1,5 golos",lambda x,y:x<y and x+y>=2),
                ("CMB_1XU35","Casa ou empate e menos de 3,5 golos",lambda x,y:x>=y and x+y<=3),
                ("CMB_X2U35","Empate ou fora e menos de 3,5 golos",lambda x,y:x<=y and x+y<=3)]:
                p=sum(z for x,y,z in matrix if predicate(x,y))/norm
                emit(key,"Combinadas",label,p,.11,"Probabilidade conjunta de resultados; mercados correlacionados",n)
    result.setdefault("markets",[]).extend(additions)
    result["extraStats"]=evidence
    result["unmodelledMarkets"]=["Eventos por minuto: sem contagem temporal histórica validada",
       "Linhas asiáticas de quarto e outras combinadas: modelo adicional necessário"]
    return result
