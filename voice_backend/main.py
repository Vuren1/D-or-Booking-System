from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from voice_backend.providers.zadarma import router as zadarma_router

app = FastAPI()

# Provider routes
app.include_router(zadarma_router)


@app.get("/health", response_class=PlainTextResponse)
async def health():
    return "OK - voice backend draait"
