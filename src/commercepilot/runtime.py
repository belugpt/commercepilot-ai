"""Local runtime: private dashboard, isolated webhook listener and durable worker."""
import asyncio
import os
from contextlib import asynccontextmanager, nullcontext
import uvicorn
from commercepilot.api import create_app
from commercepilot.gateway import webhook_app
from commercepilot.secrets import load_environment


async def serve(db_path, host="127.0.0.1", port=8000, webhook_port=8002):
    load_environment(os.getenv("COMMERCEPILOT_SECRET_FILE", ".local/secrets.dpapi"))
    app = create_app(db_path)
    stopping = asyncio.Event()

    async def work():
        while not stopping.is_set():
            try:
                inbound = await asyncio.to_thread(app.state.whatsapp.process_one)
                outbound = await asyncio.to_thread(app.state.delivery.process_one)
                if inbound is None and outbound is None:
                    await asyncio.sleep(1)
            except Exception:
                # Never log credentials, message text or raw provider failures.
                print("Worker needs attention; inspect inbox/delivery status.", flush=True)
                await asyncio.sleep(3)

    @asynccontextmanager
    async def lifespan(application):
        worker = asyncio.create_task(work())
        yield
        stopping.set()
        await worker

    app.router.lifespan_context = lifespan
    private = uvicorn.Server(uvicorn.Config(app, host=host, port=port, access_log=False))
    public = uvicorn.Server(uvicorn.Config(webhook_app(app.state.whatsapp), host="127.0.0.1", port=webhook_port, access_log=False))
    print(f"Private dashboard: http://{host}:{port}", flush=True)
    print(f"Tunnel target: http://127.0.0.1:{webhook_port} (webhook only)", flush=True)
    # Both listeners stop together when either exits. Signals are handled once.
    public.capture_signals = nullcontext
    tasks = [asyncio.create_task(private.serve()), asyncio.create_task(public.serve())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        private.should_exit = public.should_exit = True
        stopping.set()
        await asyncio.gather(*tasks, return_exceptions=True)


def main(db_path, port=8000, webhook_port=8002):
    asyncio.run(serve(db_path, host=os.getenv("COMMERCEPILOT_BIND_HOST", "127.0.0.1"), port=port, webhook_port=webhook_port))
