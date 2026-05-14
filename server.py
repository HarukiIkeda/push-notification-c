# server.py
from ndn.app import NDNApp
from ndn.encoding import Name, Component
import asyncio
import json
import uuid

app = NDNApp()
LISTEN_PREFIX_COMPUTE = "/server/compute"
LISTEN_PREFIX_FETCH = "/server/fetch"

results_store = {}
active_sessions = set() 

@app.route('/server/register_session')
def on_register_session(name, param, app_param):
    try:
        data = json.loads(bytes(app_param).decode('utf-8'))
        temp_id = data.get("temp_id")
        
        # サーバー側で正式なセッションIDを生成 (例として12文字)
        session_id = str(uuid.uuid4())[:12] 
        active_sessions.add(session_id)
        
        print(f"[Server] セッションを発行・登録しました: TempID={temp_id} -> SessionID={session_id}", flush=True)
        
        # ProxyへDataパケットとしてIDを返す
        resp_data = json.dumps({"temp_id": temp_id, "session_id": session_id}).encode('utf-8')
        app.put_data(name, content=resp_data, freshness_period=1000)
        
    except Exception as e:
        print(f"[Server] 登録エラー: {e}")

@app.route(LISTEN_PREFIX_COMPUTE)
def on_compute_request(name, param, app_param):
    print(f"[Server] 計算リクエスト受信", flush=True)
    if app_param:
        asyncio.create_task(process_compute(name, app_param))

async def process_compute(name, app_param):
    try:
        params = json.loads(bytes(app_param).decode('utf-8'))
        tx_id = params.get("id")
        target_proxy = params.get("proxy")
        token = params.get("token")
        
        if tx_id not in active_sessions:
            print(f"[Server] 警告: 未登録のSession IDからの計算要求です (ID={tx_id})", flush=True)
            
        # 受付完了のAckを返す
        app.put_data(name, content=f"Accepted: {tx_id}".encode('utf-8'), freshness_period=1000)
        
        print(f"[Server] 計算処理を開始 (ID={tx_id})", flush=True)
        await asyncio.sleep(4)
        
        results_store[tx_id] = f"Result_of_{tx_id}_is_42"
        print(f"[Server] 計算完了", flush=True)
        
        # プロキシへの通知タスクを起動
        asyncio.create_task(send_notification(target_proxy, token, tx_id))
    except Exception as e:
        print(f"[Server] 処理失敗: {e}", flush=True)

async def send_notification(proxy_name, token, tx_id):
    target = f"{proxy_name}/{token}"
    notify_payload = {
        "status": "Complete",
        "id": tx_id,
        "fetch_name": f"{LISTEN_PREFIX_FETCH}/{tx_id}"
    }
    
    try:
        print(f"[Server] プロキシ({proxy_name})へ通知を送出します...", flush=True)
        
        await app.express_interest(
            target,
            app_param=json.dumps(notify_payload).encode('utf-8'),
            must_be_fresh=True,
            can_be_prefix=True,
            lifetime=2000
        )
        
        print(f"[Server] クライアントからの通知受領Ackを確認しました (ID={tx_id})", flush=True)
    except Exception as e:
         print(f"[Server] 通知送信エラー: {e}")

@app.route(LISTEN_PREFIX_FETCH)
def on_fetch_request(name, param, app_param):
    tx_id_comp = name[-1]
    if Component.get_type(tx_id_comp) == Component.TYPE_PARAMETERS_SHA256:
        tx_id_comp = name[-2]
    tx_id = bytes(Component.get_value(tx_id_comp)).decode('utf-8')
    
    result_data = results_store.get(tx_id)
    if result_data:
        app.put_data(name, content=result_data.encode('utf-8'), freshness_period=1000)

if __name__ == '__main__':
    app.run_forever()