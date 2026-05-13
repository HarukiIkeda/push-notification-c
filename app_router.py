# app_router.py
from ndn.app import NDNApp
from ndn.encoding import Name
import asyncio
import json
import os

app = NDNApp()
ROUTER_NAME = os.environ.get('ROUTER_NAME', 'unknown_router')
LISTEN_REG = os.environ.get('LISTEN_REG', '/proxy/register')
NEXT_REG = os.environ.get('NEXT_REG', '/proxy/register_fw')
NEXT_NOTIFY = os.environ.get('NEXT_NOTIFY', '/client/A/notify')

@app.route(LISTEN_REG)
def on_register(name, param, app_param):
    print(f"[{ROUTER_NAME}] 事前登録を受信: {Name.to_str(name)}", flush=True)
    asyncio.create_task(process_register(name, app_param))

async def process_register(name, app_param):
    if not app_param: return
    try:
        params = json.loads(bytes(app_param).decode('utf-8'))
        params.setdefault("path", []).append(ROUTER_NAME) # 自分の名前を追記
        
        print(f"[{ROUTER_NAME}] 経路を追記して次({NEXT_REG})へ転送: {params['path']}", flush=True)
        params_bytes = json.dumps(params).encode('utf-8')

        _, _, content = await app.express_interest(
            NEXT_REG, 
            app_param=params_bytes,
            must_be_fresh=True, can_be_prefix=True, lifetime=2000
        )
        app.put_data(name, content=content, freshness_period=1000)
    except Exception as e:
        print(f"[{ROUTER_NAME}] 転送エラー: {e}", flush=True)

@app.route(f'/router/{ROUTER_NAME}/notify')
def on_notify(name, param, app_param):
    print(f"[{ROUTER_NAME}] 通知を受信。次({NEXT_NOTIFY})へ転送します。", flush=True)
    asyncio.create_task(forward_notify_to_client(name, app_param))

async def forward_notify_to_client(name, app_param):
    try:
        _, _, content = await app.express_interest(
            NEXT_NOTIFY,
            app_param=app_param,
            must_be_fresh=True, can_be_prefix=True, lifetime=2000
        )
        app.put_data(name, content=content, freshness_period=1000)
    except Exception as e:
         print(f"[{ROUTER_NAME}] 通知転送エラー: {e}", flush=True)

if __name__ == '__main__':
    print(f"[{ROUTER_NAME}] アプリケーションルータ起動", flush=True)
    app.run_forever()