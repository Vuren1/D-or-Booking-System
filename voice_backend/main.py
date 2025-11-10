from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from voice_backend.providers.zadarma import router as zadarma_router
from database import init_db

app = FastAPI()

# Zorg dat de SQLite-tabellen bestaan (companies, services, etc.)
init_db()

# Koppel Zadarma router
app.include_router(zadarma_router)


@app.get("/health", response_class=PlainTextResponse)
async def health():
    return "OK - voice backend draait"

