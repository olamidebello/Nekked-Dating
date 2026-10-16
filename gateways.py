"""Hosted checkout adapters. Secrets and card data never enter browser responses."""
import base64,json,urllib.request,urllib.parse,urllib.error
from decimal import Decimal
HOSTS={'stripe':['checkout.stripe.com'],'paypal':['www.paypal.com','www.sandbox.paypal.com','paypal.com','sandbox.paypal.com'],'paystack':['checkout.paystack.com'],'flutterwave':['checkout.flutterwave.com']}
class GatewayError(Exception): pass

def request(url,data=None,headers=None,form=False,method=None):
    raw=(urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()) if data is not None else None
    req=urllib.request.Request(url,data=raw,headers={'Content-Type':'application/x-www-form-urlencoded' if form else 'application/json',**(headers or {})},method=method)
    try:
        with urllib.request.urlopen(req,timeout=20) as response:return json.loads(response.read(1000000))
    except (OSError,ValueError):raise GatewayError('Payment service could not complete the request. No payment has been confirmed.')

def bearer(secret):return {'Authorization':'Bearer '+secret}
def pp_base(config):return 'https://api-m.paypal.com' if config['mode']=='live' else 'https://api-m.sandbox.paypal.com'
def pp_token(config,keys):
    auth=base64.b64encode((keys['client_id']+':'+keys['secret']).encode()).decode()
    return request(pp_base(config)+'/v1/oauth2/token',{'grant_type':'client_credentials'},{'Authorization':'Basic '+auth},True)['access_token']

def checkout(name,config,keys,order,origin):
    oid=order['id']; amount=order['amount_minor'];currency=order['currency'];title=order['title'];ref=order['reference'];callback=origin+'/marketplace?order='+oid
    if name=='stripe':
        r=request('https://api.stripe.com/v1/checkout/sessions',{'mode':'payment','success_url':callback,'cancel_url':callback+'&cancelled=1','client_reference_id':oid,'metadata[order_id]':oid,'line_items[0][price_data][currency]':currency.lower(),'line_items[0][price_data][unit_amount]':amount,'line_items[0][price_data][product_data][name]':title,'line_items[0][quantity]':1,'customer_email':order['email']},{**bearer(keys['secret']),'Idempotency-Key':oid},True)
        return r['id'],r['url']
    if name=='paystack':
        r=request('https://api.paystack.co/transaction/initialize',{'email':order['email'],'amount':amount,'currency':currency,'reference':ref,'callback_url':callback,'metadata':{'order_id':oid}},bearer(keys['secret']))
        return ref,r['data']['authorization_url']
    if name=='flutterwave':
        r=request('https://api.flutterwave.com/v3/payments',{'tx_ref':ref,'amount':str(Decimal(amount)/100),'currency':currency,'redirect_url':callback,'customer':{'email':order['email']},'customizations':{'title':title}},bearer(keys['secret']))
        return ref,r['data']['link']
    if name=='paypal':
        token=pp_token(config,keys);r=request(pp_base(config)+'/v2/checkout/orders',{'intent':'CAPTURE','purchase_units':[{'reference_id':oid,'custom_id':oid,'amount':{'currency_code':currency,'value':f'{Decimal(amount)/100:.2f}'}}],'payment_source':{'paypal':{'experience_context':{'return_url':callback,'cancel_url':callback+'&cancelled=1','user_action':'PAY_NOW'}}}},{**bearer(token),'PayPal-Request-Id':oid})
        link=next(x['href'] for x in r['links'] if x['rel'] in ('payer-action','approve'))
        return r['id'],link
    raise GatewayError('Gateway adapter is not available.')

def safe_checkout_url(name,url):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in HOSTS[name] or parsed.username or parsed.password:raise GatewayError('Payment service returned an unexpected checkout address.')
    return url

def verify(name,config,keys,order):
    provider=urllib.parse.quote(order['provider_id'],safe='')
    if name=='stripe':
        r=request('https://api.stripe.com/v1/checkout/sessions/'+provider,headers=bearer(keys['secret']))
        return {'paid':r.get('payment_status')=='paid','amount_minor':r.get('amount_total'),'currency':str(r.get('currency','')).upper(),'reference':r.get('client_reference_id'),'transaction':r.get('payment_intent'),'mode':'live' if r.get('livemode') is True else 'test'}
    if name=='paystack':
        r=request('https://api.paystack.co/transaction/verify/'+provider,headers=bearer(keys['secret']))['data']
        return {'paid':r.get('status')=='success','amount_minor':r.get('amount'),'currency':r.get('currency'),'reference':r.get('reference'),'transaction':str(r.get('id','')),'mode':r.get('domain')}
    if name=='flutterwave':
        r=request('https://api.flutterwave.com/v3/transactions/verify_by_reference?tx_ref='+provider,headers=bearer(keys['secret']))['data']
        return {'paid':r.get('status')=='successful','amount_minor':int(Decimal(str(r.get('amount',0)))*100),'currency':r.get('currency'),'reference':r.get('tx_ref'),'transaction':str(r.get('id','')),'mode':'test' if 'TEST' in keys['secret'].upper() else 'live'}
    if name=='paypal':
        token=pp_token(config,keys)
        try:request(pp_base(config)+'/v2/checkout/orders/'+provider+'/capture',{}, {**bearer(token),'PayPal-Request-Id':order['id']+'-capture'})
        except GatewayError:pass
        r=request(pp_base(config)+'/v2/checkout/orders/'+provider,headers=bearer(token));unit=r['purchase_units'][0];captures=unit.get('payments',{}).get('captures',[])
        capture=next((x for x in captures if x.get('status')=='COMPLETED'),{})
        return {'paid':bool(capture),'amount_minor':int(Decimal(capture.get('amount',{}).get('value','0'))*100),'currency':capture.get('amount',{}).get('currency_code'),'reference':unit.get('custom_id'),'transaction':capture.get('id'),'mode':config['mode']}
    raise GatewayError('Gateway adapter is not available.')
