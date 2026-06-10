import os, json, time, math, random
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
import pandas as pd
from flask import Flask, request, jsonify

BOT_TOKEN = os.getenv('BOT_TOKEN','')
ADMIN_ID = int(os.getenv('ADMIN_ID','0'))
PUBLIC_URL = os.getenv('PUBLIC_URL','').rstrip('/')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET','change-me')
TWELVE_DATA_API_KEY = os.getenv('TWELVE_DATA_API_KEY','')
PREMIUM_DAYS = int(os.getenv('DEFAULT_PREMIUM_DAYS','30'))

BASE = f'https://api.telegram.org/bot{BOT_TOKEN}'
ROOT = Path(__file__).parent
USERS_FILE = ROOT/'users.json'
TRADES_FILE = ROOT/'trades.json'
SIGNALS_FILE = ROOT/'signals.json'

CRYPTO_SYMBOLS = ['BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT','DOGEUSDT','ADAUSDT','AVAXUSDT','LINKUSDT','PEPEUSDT']
FOREX_SYMBOLS = ['EUR/USD','GBP/USD','USD/JPY','USD/CHF','AUD/USD','USD/CAD','NZD/USD','XAU/USD','XAG/USD']
STOCK_SYMBOLS = ['AAPL','TSLA','NVDA','MSFT','AMZN','META','GOOGL']

app = Flask(__name__)

def load(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default

def save(path, data):
    path.write_text(json.dumps(data, indent=2, default=str))

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def send(chat_id, text, keyboard=None, parse_mode='HTML'):
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode, 'disable_web_page_preview': True}
    if keyboard:
        payload['reply_markup'] = keyboard
    try:
        return requests.post(f'{BASE}/sendMessage', json=payload, timeout=15).json()
    except Exception as e:
        print('send error', e)

def copy_message(to_chat, from_chat, message_id):
    try:
        return requests.post(f'{BASE}/copyMessage', json={'chat_id':to_chat,'from_chat_id':from_chat,'message_id':message_id}, timeout=20).json()
    except Exception as e:
        print('copy error', e)

def answer_callback(callback_id, text='Done'):
    try:
        requests.post(f'{BASE}/answerCallbackQuery', json={'callback_query_id':callback_id,'text':text}, timeout=10)
    except Exception: pass

def menu():
    return {'inline_keyboard':[
        [{'text':'📊 Crypto Signal','callback_data':'signal_crypto'}, {'text':'💱 Forex/Metals','callback_data':'signal_forex'}],
        [{'text':'📈 Stocks','callback_data':'signal_stock'}, {'text':'⭐ Get Premium','callback_data':'premium'}],
        [{'text':'🎁 Referral','callback_data':'referral'}, {'text':'👤 My Account','callback_data':'account'}]
    ]}

def grade(conf):
    if conf >= 90: return 'A+'
    if conf >= 85: return 'A'
    if conf >= 79: return 'B'
    return 'C'

def get_user(user_id, username=''):
    users = load(USERS_FILE, {})
    uid = str(user_id)
    if uid not in users:
        users[uid] = {'id':user_id,'username':username or '', 'premium_until':'', 'referred_by':'', 'referrals':[], 'premium_referrals':0, 'created_at':now_iso()}
        save(USERS_FILE, users)
    return users[uid]

def is_premium(uid):
    u = load(USERS_FILE, {}).get(str(uid), {})
    try:
        return datetime.fromisoformat(u.get('premium_until','').replace('Z','+00:00')) > datetime.now(timezone.utc)
    except Exception:
        return False

def activate_premium(uid, days=PREMIUM_DAYS, by_admin=False):
    users = load(USERS_FILE, {})
    uid = str(uid)
    u = users.setdefault(uid, {'id':int(uid),'referrals':[]})
    base = datetime.now(timezone.utc)
    try:
        current = datetime.fromisoformat(u.get('premium_until','').replace('Z','+00:00'))
        if current > base: base = current
    except Exception: pass
    u['premium_until'] = (base + timedelta(days=days)).isoformat()
    u['premium_activated_at'] = now_iso()
    ref = str(u.get('referred_by',''))
    if ref and ref in users and not u.get('referrer_rewarded'):
        activate_premium(ref, 1, True)
        users = load(USERS_FILE, {})
        users[uid]['referrer_rewarded'] = True
        users[ref]['premium_referrals'] = users[ref].get('premium_referrals',0) + 1
        send(ref, '🎉 Your referral activated premium. You received <b>+1 premium day</b>.')
    save(USERS_FILE, users)
    send(uid, f'✅ Premium activated for <b>{days} day(s)</b>.')

def binance_klines(symbol, interval='1h', limit=120):
    url = 'https://api.binance.com/api/v3/klines'
    r = requests.get(url, params={'symbol':symbol,'interval':interval,'limit':limit}, timeout=20)
    r.raise_for_status()
    data = r.json()
    df = pd.DataFrame(data, columns=['t','o','h','l','c','v','ct','qv','n','tb','tq','i'])
    for col in ['o','h','l','c','v']:
        df[col] = pd.to_numeric(df[col])
    return df

def twelve_time_series(symbol, interval='1h', outputsize=120):
    if not TWELVE_DATA_API_KEY:
        raise RuntimeError('Twelve Data API key missing')
    r = requests.get('https://api.twelvedata.com/time_series', params={'symbol':symbol,'interval':interval,'outputsize':outputsize,'apikey':TWELVE_DATA_API_KEY}, timeout=20)
    j = r.json()
    if 'values' not in j:
        raise RuntimeError(j.get('message','No Twelve Data values'))
    df = pd.DataFrame(j['values']).iloc[::-1].reset_index(drop=True)
    for col in ['open','high','low','close']:
        df[col[0]] = pd.to_numeric(df[col])
    df['v'] = pd.to_numeric(df.get('volume', pd.Series([0]*len(df))), errors='coerce').fillna(0)
    return df[['o','h','l','c','v']]

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))

def atr(df, period=14):
    tr = pd.concat([(df.h-df.l), (df.h-df.c.shift()).abs(), (df.l-df.c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def analyze_df(symbol, df, asset='crypto'):
    c = df.c
    df['ema20'] = c.ewm(span=20).mean(); df['ema50'] = c.ewm(span=50).mean(); df['rsi'] = rsi(c); df['atr'] = atr(df)
    last, prev = df.iloc[-1], df.iloc[-2]
    price = float(last.c); a = float(last.atr) if not math.isnan(last.atr) else price*0.01
    bull = last.ema20 > last.ema50 and last.rsi > 52 and last.c > prev.c
    bear = last.ema20 < last.ema50 and last.rsi < 48 and last.c < prev.c
    if not bull and not bear:
        direction = 'BUY' if last.ema20 >= last.ema50 else 'SELL'
    else:
        direction = 'BUY' if bull else 'SELL'
    score = 65
    reasons = []
    if last.ema20 > last.ema50: score += 9; reasons.append('EMA20 above EMA50')
    else: reasons.append('EMA20 below EMA50')
    if direction == 'BUY' and 52 <= last.rsi <= 72: score += 8; reasons.append(f'RSI bullish {last.rsi:.1f}')
    if direction == 'SELL' and 28 <= last.rsi <= 48: score += 8; reasons.append(f'RSI bearish {last.rsi:.1f}')
    if last.v > df.v.tail(30).mean() and df.v.tail(30).mean() > 0: score += 5; reasons.append('Volume above average')
    if abs(last.ema20-last.ema50)/price > 0.002: score += 5
    score = min(95, max(60, score + random.randint(-2,3)))
    if direction == 'BUY':
        sl = price - a*1.4; tp1 = price + a*1.2; tp2 = price + a*2.0; tp3 = price + a*3.0
    else:
        sl = price + a*1.4; tp1 = price - a*1.2; tp2 = price - a*2.0; tp3 = price - a*3.0
    return {'symbol':symbol,'asset':asset,'side':direction,'entry':price,'sl':sl,'tp1':tp1,'tp2':tp2,'tp3':tp3,'confidence':score,'grade':grade(score),'reasons':reasons[:4],'timeframe':'1H','time':now_iso()}

def fmt_signal(s):
    return (f"🚀 <b>{s['asset'].upper()} SIGNAL — {s['grade']}</b>\n\n"
            f"📌 Pair: <b>{s['symbol']}</b>\nDirection: <b>{s['side']}</b>\nTimeframe: <b>{s['timeframe']}</b>\n"
            f"Entry: <code>{s['entry']:.6g}</code>\nSL: <code>{s['sl']:.6g}</code>\n"
            f"TP1: <code>{s['tp1']:.6g}</code>\nTP2: <code>{s['tp2']:.6g}</code>\nTP3: <code>{s['tp3']:.6g}</code>\n"
            f"Confidence: <b>{s['confidence']}%</b>\nReason: {'; '.join(s['reasons'])}\n\n⚠️ Not financial advice. Manage risk.")

def generate_signal(asset):
    if asset == 'crypto':
        best = []
        for sym in CRYPTO_SYMBOLS:
            try: best.append(analyze_df(sym, binance_klines(sym), 'crypto'))
            except Exception as e: print(sym,e)
        return max(best, key=lambda x:x['confidence']) if best else None
    if asset == 'forex':
        best=[]
        for sym in FOREX_SYMBOLS:
            try: best.append(analyze_df(sym, twelve_time_series(sym), 'forex/metals'))
            except Exception as e: print(sym,e)
        return max(best, key=lambda x:x['confidence']) if best else None
    if asset == 'stock':
        best=[]
        for sym in STOCK_SYMBOLS:
            try: best.append(analyze_df(sym, twelve_time_series(sym), 'stocks'))
            except Exception as e: print(sym,e)
        return max(best, key=lambda x:x['confidence']) if best else None

def record_trade(signal, chat_id=None):
    trades = load(TRADES_FILE, [])
    signal['status'] = 'OPEN'; signal['chat_id'] = chat_id; signal['id'] = f"{signal['symbol']}-{int(time.time())}"
    trades.append(signal); save(TRADES_FILE, trades)

def handle_message(msg):
    chat = msg['chat']; user = msg.get('from',{}); text = msg.get('text','')
    uid = user.get('id'); get_user(uid, user.get('username',''))
    if text.startswith('/start'):
        parts = text.split(maxsplit=1)
        if len(parts)>1 and parts[1].startswith('ref_'):
            ref = parts[1].replace('ref_','')
            users = load(USERS_FILE,{})
            if str(uid) != ref and ref in users and not users[str(uid)].get('referred_by'):
                users[str(uid)]['referred_by'] = ref
                users[ref].setdefault('referrals',[])
                if str(uid) not in users[ref]['referrals']: users[ref]['referrals'].append(str(uid))
                save(USERS_FILE, users)
        send(chat['id'], '👋 Welcome to <b>Market Signal Bot</b>\nCrypto, forex, stocks and metals signals with premium grading.', menu())
    elif text.startswith('/activate') and uid == ADMIN_ID:
        p=text.split(); activate_premium(int(p[1]), int(p[2]) if len(p)>2 else PREMIUM_DAYS) if len(p)>=2 else send(uid,'Use /activate USER_ID DAYS')
    elif text.startswith('/broadcast') and uid == ADMIN_ID:
        body = text.replace('/broadcast','',1).strip()
        users=load(USERS_FILE,{})
        for k in users: send(k, body or 'Broadcast')
        send(uid, f'✅ Broadcast sent to {len(users)} users')
    elif uid == ADMIN_ID and msg.get('reply_to_message') and text.startswith('/copybroadcast'):
        users=load(USERS_FILE,{})
        mid=msg['reply_to_message']['message_id']
        for k in users: copy_message(k, chat['id'], mid)
        send(uid, f'✅ Media broadcast copied to {len(users)} users')
    else:
        send(chat['id'], 'Use the menu below:', menu())

def handle_callback(cb):
    qid=cb['id']; data=cb['data']; user=cb['from']; chat_id=cb['message']['chat']['id']; uid=user['id']
    answer_callback(qid)
    if data.startswith('signal_'):
        asset=data.split('_')[1]
        if asset in ['forex','stock'] and not is_premium(uid):
            send(chat_id, '🔒 Forex, metals and stock signals are premium. Tap ⭐ Get Premium.', menu()); return
        s=generate_signal(asset)
        if not s: send(chat_id, 'No signal found now. Check API keys/network.'); return
        record_trade(s, chat_id); send(chat_id, fmt_signal(s))
    elif data=='premium':
        send(chat_id, '⭐ <b>Premium</b> scans crypto, forex, stocks and metals for stronger A/B/A+ signals.\n\nGrades:\nB = 79–85%\nA = 85–90%\nA+ = 90%+\n\nPay admin, then admin activates using /activate USER_ID DAYS.\nYour ID: <code>%s</code>'%uid)
    elif data=='referral':
        botname = requests.get(f'{BASE}/getMe', timeout=10).json().get('result',{}).get('username','YOUR_BOT')
        link=f'https://t.me/{botname}?start=ref_{uid}'
        u=load(USERS_FILE,{}).get(str(uid),{})
        send(chat_id, f'🎁 Your referral link:\n{link}\n\nReferrals: {len(u.get("referrals",[]))}\nPremium referrals: {u.get("premium_referrals",0)}\nReward: +1 premium day when referral activates premium.')
    elif data=='account':
        u=load(USERS_FILE,{}).get(str(uid),{})
        send(chat_id, f'👤 ID: <code>{uid}</code>\nPremium until: <b>{u.get("premium_until") or "Not active"}</b>')

@app.post(f'/{WEBHOOK_SECRET}')
def webhook():
    update=request.get_json(force=True)
    if 'message' in update: handle_message(update['message'])
    if 'callback_query' in update: handle_callback(update['callback_query'])
    return jsonify(ok=True)

@app.get('/set_webhook')
def set_webhook():
    if not PUBLIC_URL or not BOT_TOKEN: return jsonify(ok=False,error='Set PUBLIC_URL and BOT_TOKEN')
    url=f'{PUBLIC_URL}/{WEBHOOK_SECRET}'
    return requests.get(f'{BASE}/setWebhook', params={'url':url}, timeout=20).json()

@app.get('/scan')
def scan():
    secret=request.args.get('secret')
    if secret != WEBHOOK_SECRET: return jsonify(ok=False,error='bad secret'), 403
    asset=request.args.get('asset','crypto')
    chat=request.args.get('chat') or os.getenv('SIGNAL_CHANNEL_ID')
    s=generate_signal(asset)
    if s and chat: record_trade(s, chat); send(chat, fmt_signal(s))
    return jsonify(ok=True, signal=s)

@app.get('/check_tp')
def check_tp():
    secret=request.args.get('secret')
    if secret != WEBHOOK_SECRET: return jsonify(ok=False,error='bad secret'), 403
    trades=load(TRADES_FILE,[]); changed=False; alerts=0
    for t in trades:
        if t.get('status')!='OPEN' or t.get('asset')!='crypto': continue
        try:
            price=float(binance_klines(t['symbol'], '5m', 2).iloc[-1].c)
            side=t['side']; hit=None
            if side=='BUY':
                if price>=t['tp3']: hit='TP3'; t['status']='TP3 HIT'
                elif price>=t['tp2'] and not t.get('tp2_hit'): hit='TP2'; t['tp2_hit']=True
                elif price>=t['tp1'] and not t.get('tp1_hit'): hit='TP1'; t['tp1_hit']=True
                elif price<=t['sl']: hit='SL'; t['status']='SL HIT'
            else:
                if price<=t['tp3']: hit='TP3'; t['status']='TP3 HIT'
                elif price<=t['tp2'] and not t.get('tp2_hit'): hit='TP2'; t['tp2_hit']=True
                elif price<=t['tp1'] and not t.get('tp1_hit'): hit='TP1'; t['tp1_hit']=True
                elif price>=t['sl']: hit='SL'; t['status']='SL HIT'
            if hit and t.get('chat_id'):
                send(t['chat_id'], f'✅ <b>{t["symbol"]}</b> {hit} hit at <code>{price:.6g}</code>')
                alerts+=1; changed=True
        except Exception as e: print('tp check',e)
    if changed: save(TRADES_FILE,trades)
    return jsonify(ok=True, alerts=alerts)

@app.get('/health')
def health(): return jsonify(ok=True, time=now_iso())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT','5000')))
