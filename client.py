# client.py
from ndn.app import NDNApp
from ndn.encoding import Name
from Crypto.Cipher import AES
import asyncio
import json
import base64
import uuid

app = NDNApp()
MY_PREFIX = "/client/A/notify"
SERVER_TARGET_COMPUTE = "/server/compute"
SECRET_KEY = b'16bytesecretkey!'

#通知を受け取ったときの処理
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

#メインシナリオ
async def main():
    await asyncio.sleep(5) # NFDとルータの起動待ち
    session_id = str(uuid.uuid4())[:8] # ランダムな8文字の文字列をセッションIDとして作成
    
    # 1. 事前登録Interestの送信 (ルータが経路を追記していく)
    print(f"[Client] 事前登録Interestを送信 (Session ID: {session_id})", flush=True)
    reg_params = json.dumps({"session_id": session_id, "path": []}).encode('utf-8') ## IDと空の経路リストをJSON化
    try:
        # ↓↓↓ 本来のNDNの姿: プロキシを直接指定する ↓↓↓
        await app.express_interest('/proxy/register', app_param=reg_params, must_be_fresh=True, can_be_prefix=True, lifetime=2000)
    except Exception as e:
        print(f"[Client] 事前登録エラー: {e}", flush=True)

    await asyncio.sleep(1)

    # 2. 計算リクエストの送信
    print(f"[Client] 計算要求interestを送信 (Session ID: {session_id})", flush=True)
    cipher = AES.new(SECRET_KEY, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(b"client/A")
    token = base64.urlsafe_b64encode(cipher.nonce + tag + ciphertext).decode().rstrip('=')

    req_params = json.dumps({"proxy": "/proxy/notify", "token": token, "id": session_id}).encode('utf-8')
    try:
        _, _, content = await app.express_interest(SERVER_TARGET_COMPUTE, app_param=req_params, must_be_fresh=True, can_be_prefix=True, lifetime=2000)
        print(f"[Client] サーバからAck受信: {bytes(content).decode('utf-8')}", flush=True)
    except:
        print("[Client] 計算リクエストタイムアウト", flush=True)

if __name__ == '__main__':
    app.run_forever(after_start=main())