from fastapi import FastAPI, Request
from fastapi.responses import Response, PlainTextResponse
from voice_backend.providers.twilio import handle_twilio_webhook

app = FastAPI()

@app.post("/twilio/voice")
async def twilio_voice(request: Request):
    form = await request.form()
    twiml = handle_twilio_webhook(form)
    return Response(content=twiml, media_type="text/xml")

@app.get("/health")
async def health():
    return PlainTextResponse("OK - voice backend draait")
