from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from voice_backend.voice_engine import handle_turn

router = APIRouter()


@router.post("/zadarma/ivr")
async def zadarma_ivr(request: Request):
    """
    Test-endpoint voor Zadarma integratie.
    - Leest form-data (caller_id, called_did, pbx_call_id, enz.).
    - Roept de centrale voice_engine aan.
    - Geeft een simpele tekst terug zodat we kunnen zien dat alles werkt.
    """

    # 1) Form proberen in te lezen
    try:
        form = await request.form()
    except Exception as e:
        # Als dit fout gaat, laten we dat expliciet zien
        return PlainTextResponse(
            f"ERROR: kon form-data niet lezen: {e}",
            status_code=400,
        )

    # 2) Data eruit halen (met veilige defaults)
    from_number = form.get("caller_id", "")
    to_number = form.get("called_did", "")
    call_id = form.get("pbx_call_id", "")

    # Voor nu: optionele speech of digits
    user_text = form.get("speech_result") or form.get("digits") or None

    # 3) Centrale logica aanroepen
    try:
        result = handle_turn(
            provider="zadarma",
            to_number=to_number,
            from_number=from_number,
            call_id=call_id,
            user_text=user_text,
        )
    except Exception as e:
        # Als hier iets crasht, tonen we het ook expliciet
        return PlainTextResponse(
            f"ERROR in handle_turn: {e}",
            status_code=500,
        )

    say = result.get("say", "")
    expect_input = result.get("expect_input", False)
    hangup = result.get("hangup", False)

    # 4) Simpele debug output (later vervangen door echt Zadarma JSON/XML)
    text = f"SAY: {say}\nEXPECT_INPUT: {expect_input}\nHANGUP: {hangup}"
    return PlainTextResponse(text)
