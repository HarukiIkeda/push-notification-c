# proxy.py
from ndn.app import NDNApp
from ndn.encoding import Name, Component
import asyncio
import json

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
        
        # Serverに登録を依頼し、セッションIDを発行してもらう
        _, _, content = await app.express_interest(
            '/server/register_session',
            app_param=server_req_data,
            must_be_fresh=True,
            can_be_prefix=True,
            lifetime=2000
        )
        
        # Serverからの応答(Data)からセッションIDを抽出
        server_resp = json.loads(bytes(content).decode('utf-8'))
        session_id = server_resp.get("session_id")
        
        # 経路情報をプロキシ内に留める
        session_table[session_id] = path
        print(f"[Proxy] 経路情報を保存しました: Session ID={session_id}, Path={path}", flush=True)

        # 戻りの経路(PIT)を使って、Client（ルータ経由）へ発行されたセッションIDをDataとして返す
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
        
        path = session_table.get(session_id, [])
        
        if path:
            last_router = path[-1]
            target = f"/router/{last_router}/notify"
            print(f"[Proxy] ローカルに保存された経路情報を使用: {last_router} へ転送", flush=True)
        else:
            target = "/client/A/notify"

        _, _, content = await app.express_interest(
            target,
            app_param=payload,
            must_be_fresh=True,
            can_be_prefix=True,
            lifetime=2000
        )
        app.put_data(incoming_name, content=content, freshness_period=1000)
    except Exception as e:
        print(f"[Proxy] 転送失敗: {e}", flush=True)

if __name__ == '__main__':
    print(f"[Proxy] 起動中...", flush=True)
    app.run_forever()