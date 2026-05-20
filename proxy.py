# proxy.py
from ndn.app import NDNApp
from ndn.encoding import Name, Component
import asyncio
import json
import hmac
import hashlib

app = NDNApp()
LISTEN_PREFIX = "/proxy/notify"
SECRET_KEY = b'16bytesecretkey!'
session_table = {}

@app.route('/proxy/register_fw')
def on_register_fw(name, param, app_param):
    print(f"[Proxy] ルータ経由の登録要求を受信", flush=True)
    asyncio.create_task(handle_registration(name, app_param))

async def handle_registration(name, app_param):
    try:
        data = json.loads(bytes(app_param).decode('utf-8'))
        temp_id = data.get("temp_id")
        path = data.get("path", [])
        
        print(f"[Proxy] ServerへセッションID発行を要求します (Temp ID: {temp_id})", flush=True)
        server_req_data = json.dumps({"temp_id": temp_id}).encode('utf-8')
        
        _, _, content = await app.express_interest(
            '/server/register_session', app_param=server_req_data,
            must_be_fresh=True, can_be_prefix=True, lifetime=2000
        )
        
        server_resp = json.loads(bytes(content).decode('utf-8'))
        session_id = server_resp.get("session_id")
        
        session_table[session_id] = path
        print(f"[Proxy] 経路情報を保存しました: Session ID={session_id}, Path={path}", flush=True)

        client_resp_data = json.dumps({"session_id": session_id}).encode('utf-8')
        app.put_data(name, content=client_resp_data, freshness_period=1000)
        
    except Exception as e:
        print(f"[Proxy] 登録失敗: {e}", flush=True)

@app.route(LISTEN_PREFIX)
def on_notification(name, param, app_param):
    print(f"[Proxy] サーバーから通知受信", flush=True)
    asyncio.create_task(forward_to_client_via_router(name, app_param))

async def forward_to_client_via_router(incoming_name, payload):
    try:
        notify_data = json.loads(bytes(payload).decode('utf-8'))
        session_id = notify_data.get("id")
        token = notify_data.get("token")
        
        if not token or not session_id:
            print(f"[Proxy] 警告: IDまたはTokenがありません。通知を破棄します。", flush=True)
            return

        # 1. テーブルにIDが存在するか確認（存在しない場合は即座に破棄し、重いHMAC計算を避ける）
        if session_id not in session_table:
            print(f"[Proxy] 経路情報が見つからない、または既に利用済みのセッションです (ID={session_id})。", flush=True)
            return

        # 2. 【変更点】HMACの再計算と検証
        expected_token = hmac.new(SECRET_KEY, session_id.encode('utf-8'), hashlib.sha256).hexdigest()
        
        # タイミング攻撃を防ぐため、安全な比較関数を使用
        if not hmac.compare_digest(token, expected_token):
            print(f"[Proxy] 認証失敗: Tokenの不正または改ざんを検知しました。破棄します。", flush=True)
            return
            
        print(f"[Proxy] Token検証成功: 認証された正規の通知です。(ID={session_id})", flush=True)

        # 検証に成功したので経路情報をPopする
        path = session_table.pop(session_id)
        
        if path:
            last_router = path[-1]
            target = f"/router/{last_router}/notify"
            print(f"[Proxy] ローカル経路情報を使用: {last_router} へ転送します", flush=True)
        else:
            target = "/client/A/notify"

        _, _, content = await app.express_interest(
            target, app_param=payload,
            must_be_fresh=True, can_be_prefix=True, lifetime=2000
        )
        app.put_data(incoming_name, content=content, freshness_period=1000)

    except Exception as e:
        print(f"[Proxy] 転送失敗: {e}", flush=True)

if __name__ == '__main__':
    print(f"[Proxy] 起動中...", flush=True)
    app.run_forever()