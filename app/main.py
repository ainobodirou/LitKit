import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.router import api_router
from app.bootstrap import create_runtime
from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s |"
        "%(name)s | %(message)s"
    ),
)

@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncGenerator[None, None]:
    settings = get_settings()
    runtime = create_runtime(settings)
    app.state.runtime = runtime

    try:
        await runtime.telegram_transport.start()
        yield
    finally:
        await runtime.close()

app = FastAPI(
    title = "LitKit",
    vesrion = "0.1.0",
    lifespan = lifespan,
)

@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
    }
