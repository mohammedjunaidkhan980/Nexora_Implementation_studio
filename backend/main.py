from contextlib import asynccontextmanager

from fastapi import FastAPI
from database import engine, Base, migrate_existing_schema
from api.user import router as user_router
from api.organization import router as organization_router
from api.documents import router as document_router
from api.chat import router as chat_router
from services.chat_memory import close_chat_memory_client

Base.metadata.create_all(bind=engine)
migrate_existing_schema()


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        yield
    finally:
        close_chat_memory_client()


app = FastAPI(lifespan=lifespan)

app.include_router(user_router)
app.include_router(organization_router)
app.include_router(document_router)
app.include_router(chat_router)
