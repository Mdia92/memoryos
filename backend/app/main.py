"""MemoryOS backend entrypoint.

    uvicorn app.main:app --reload --port 8000

On startup: ensure schema (pgvector + tables), hydrate the in-memory state
from PostgreSQL, and serve. The same image runs locally and on Alibaba
Cloud ECS with only environment-variable changes.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import get_settings
from .db import get_sessionmaker, init_db
from .store import load_state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("memoryos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with get_sessionmaker()() as session:
        app.state.memory = await load_state(session)
    app.state.lock = asyncio.Lock()
    logger.info(
        "memory hydrated: %d events, %d facts",
        len(app.state.memory.events),
        len(app.state.memory.facts),
    )
    yield


app = FastAPI(
    title="MemoryOS",
    description=(
        "Evidence-based memory agent — AI shouldn't remember more, "
        "it should remember correctly."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
