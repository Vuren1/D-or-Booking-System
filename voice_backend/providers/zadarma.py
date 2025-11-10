from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from voice_backend.voice_engine import handle_turn

router = APIRouter()


@router.post("/zadarma/ivr")
async def zadarma_ivr(request: Request):
    form = await request.form()

    from_number = form.get("caller_id", "")
    to_number = form.get("called_did", "")
    call_id = form.get("pbx_call_id", "")

    user_text = form.get("speech_result") or form.get("digits") or None

    result = handle_turn(
        provider="zadarma",
        to_number=to_number,
        from_number=from_number,
        call_id=call_id,
        user_text=user_text,
    )

    # Tijdelijke debug-output (we maken dit straks Zadarma-formaat)
    lines = [
        f"SAY: {result['say']}",
        f"EXPECT_INPUT: {result['expect_input']}",
        f"HANGUP: {result['hangup']}",
    ]
    return PlainTextResponse("\n".join(lines))

