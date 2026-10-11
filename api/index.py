import json,hashlib,re,os
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse,Response
app=FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])
@app.get('/effective-config')
@app.get('/api/effective-config')
def config(request:Request):
    c=dict(port=8075,workers=13,debug=False,log_level='debug',api_key='****')
    for arg in request.query_params.getlist('set'):
        if '=' not in arg:continue
        k,v=arg.split('=',1)
        if k in ['port','workers']:v=int(v)
        elif k=='debug':v=v.lower() in ['true','1','yes','on']
        c[k]=v
    c['api_key']='****'
    return c
@app.options('/mcp')
def mcp_options():return Response(status_code=204)
@app.post('/mcp')
@app.post('/api/mcp')
async def mcp(request:Request):
    b=await request.json();method=b.get('method');i=b.get('id')
    if method=='initialize':r={'protocolVersion':b.get('params',{}).get('protocolVersion','2025-03-26'),'capabilities':{'tools':{}},'serverInfo':{'name':'tds-challenge','version':'1.0.0'}}
    elif method=='tools/list':r={'tools':[{'name':'solve_challenge','description':'Solve the current request-header challenge','inputSchema':{'type':'object','properties':{}}}]}
    elif method=='tools/call':
        challenge=request.headers.get('x-exam-challenge','');text=hashlib.sha256((challenge+':25f2003426@ds.study.iitm.ac.in').encode()).hexdigest()[:16];r={'content':[{'type':'text','text':text}]}
    elif method=='ping':r={}
    elif i is None:return Response(status_code=202)
    else:return JSONResponse({'jsonrpc':'2.0','id':i,'error':{'code':-32601,'message':'Method not found'}})
    return {'jsonrpc':'2.0','id':i,'result':r}
ORDERS=json.load(open(os.path.join(os.path.dirname(__file__),'orders.json')))
RATES={'USD':1,'EUR':1.13,'INR':0.01185}
MONTHS=['january','february','march','april','may','june','july','august','september','october','november','december']
@app.post('/answer')
@app.post('/api/answer')
async def answer(request:Request):
    q=(await request.json()).get('question','');s=q.lower();rows=ORDERS
    region=next((x for x in ['North','South','East','West','Central'] if re.search(r'\b'+x.lower()+r'\b',s)),None)
    if region:rows=[r for r in rows if r['region']==region]
    products=sorted(set(r['product'] for r in rows),key=lambda x:-len(x))
    product=next((x for x in products if x.lower() in s),None)
    if product:rows=[r for r in rows if r['product']==product]
    customer=re.search(r'\bc\d+\b',s)
    if customer:rows=[r for r in rows if r['customer'].lower()==customer[0]]
    month=next((i+1 for i,x in enumerate(MONTHS) if x in s or re.search(r'\b'+x[:3]+r'\b',s)),None)
    if month:rows=[r for r in rows if datetime.fromisoformat(r['created_at'].replace('Z','+00:00')).astimezone(timezone(timedelta(hours=5,minutes=30))).month==month]
    def money(r):return r['amount']*RATES[r['currency']]
    refunds=any(x in s for x in ['refund','refunded'])
    if 'refund rate' in s or ('percentage' in s and refunds):
        denominator=len(rows);return {'answer':round(100*sum(r['status']=='refunded' for r in rows)/denominator,2) if denominator else 0}
    if 'net revenue' in s:
        return {'answer':round(sum(money(r)*(1 if r['status']=='paid' else -1 if r['status']=='refunded' else 0) for r in rows),2)}
    status='refunded' if refunds else 'paid'
    if not any(x in s for x in ['all orders','total orders','number of orders']) or any(x in s for x in ['paid','revenue','refund']):rows=[r for r in rows if r['status']==status]
    if any(x in s for x in ['highest','top','most','best','largest','leading']):
        key='customer' if 'customer' in s else 'product';g=defaultdict(float)
        for r in rows:g[r[key]]+=r['qty'] if any(x in s for x in ['units','quantity']) else money(r)
        result=sorted(g,key=lambda k:(-g[k],k));return {'answer':result[0] if result else ''}
    if 'customer' in s and any(x in s for x in ['unique','distinct','how many','number']):return {'answer':len(set(r['customer'] for r in rows))}
    if any(x in s for x in ['units','quantity']):return {'answer':sum(r['qty'] for r in rows)}
    is_average=any(x in s for x in ['average','mean','aov'])
    if not is_average and any(x in s for x in ['how many','count','number of','total orders']):return {'answer':len(rows)}
    value=sum(money(r) for r in rows)
    if is_average:value=value/len(rows) if rows else 0
    return {'answer':round(value,2)}
