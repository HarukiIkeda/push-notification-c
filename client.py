# client.py
from ndn.app import NDNApp
from ndn.encoding import Name
import asyncio
import json
import uuid
import hmac
import hashlib

app = NDNApp()
MY_PREFIX = "/client/A/notify"
SERVER_TARGET_COMPUTE = "/server/compute"
SECRET_KEY = b'16bytesecretkey!'

# 通知を受け取ったときの処理
@app.route(MY_PREFIX)
def on_notification(name, param, app_param):
    print(f"\n[Client] 完了通知を受信: {Name.to_str(name)}", flush=True)
    if app_param:
        try:
            msg_json = json.loads(bytes(app_param).decode('utf-8'))
            tx_id = msg_json.get("id")
            fetch_target = msg_json.get("fetch_name")
            print(f"[Client] 通知内容: ID={tx_id}, 場所={fetch_target}", flush=True)
            if msg_json.get("status") == "Complete" and fetch_target:
                asyncio.create_task(fetch_result(fetch_target))
            app.put_data(name, content=b'ACK', freshness_period=1000)
        except Exception as e:
            print(f"[Client] 解析エラー: {e}", flush=True)

# 結果を取得する処理
async def fetch_result(target_name):
    print(f"[Client] 結果取得interest送信: {target_name}", flush=True)
    try:
        _, _, content = await app.express_interest(target_name, must_be_fresh=True, can_be_prefix=False, lifetime=2000)
        print(f"[Client] 計算結果受信: {bytes(content).decode('utf-8')}", flush=True)
    except:
        print("[Client] 結果取得タイムアウト", flush=True)

# メインシナリオ
async def main():
    await asyncio.sleep(5) # NFDとルータの起動待ち
    temp_id = str(uuid.uuid4())[:8] # 要求管理用の一時IDを作成
    
    # 1. 事前登録Interestの送信
    print(f"[Client] 事前登録Interestを送信 (Temp ID: {temp_id})", flush=True)
    reg_params = json.dumps({"temp_id": temp_id, "path": []}).encode('utf-8')
    
    session_id = None
    try:
        _, _, content = await app.express_interest('/proxy/register', app_param=reg_params, must_be_fresh=True, can_be_prefix=True, lifetime=2000)
        resp_data = json.loads(bytes(content).decode('utf-8'))
        session_id = resp_data.get("session_id")
        print(f"[Client] 登録成功！ Serverから発行された Session ID: {session_id}", flush=True)
    except Exception as e:
        print(f"[Client] 事前登録エラー: {e}", flush=True)
        return

    await asyncio.sleep(1)

    if not session_id:
        print("[Client] 有効なセッションIDが取得できませんでした。", flush=True)
        return

    # 2. 計算リクエストの送信
    print(f"[Client] 計算要求interestを送信 (Session ID: {session_id})", flush=True)
    
    # 【変更点】HMAC-SHA256によるToken（署名）の生成
    token = hmac.new(SECRET_KEY, session_id.encode('utf-8'), hashlib.sha256).hexdigest()
    print(f"[Client] 生成したHMAC Token: {token[:16]}...", flush=True)

    req_params = json.dumps({"proxy": "/proxy/notify", "token": token, "id": session_id}).encode('utf-8')
    try:
        _, _, content = await app.express_interest(SERVER_TARGET_COMPUTE, app_param=req_params, must_be_fresh=True, can_be_prefix=True, lifetime=2000)
        print(f"[Client] サーバからAck受信: {bytes(content).decode('utf-8')}", flush=True)
    except:
        print("[Client] 計算リクエストタイムアウト", flush=True)

if __name__ == '__main__':
    app.run_forever(after_start=main())