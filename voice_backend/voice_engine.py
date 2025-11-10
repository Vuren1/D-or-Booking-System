from typing import Dict, Any
from database import get_company_by_ai_number


def handle_turn(
    provider: str,
    to_number: str,
    from_number: str,
    call_id: str,
    user_text: str | None,
) -> Dict[str, Any]:
    company = get_company_by_ai_number(to_number)

    if not company:
        return {
            "say": "Dit nummer is nog niet geconfigureerd. Tot ziens.",
            "expect_input": False,
            "hangup": True,
        }

    # Eerste beurt
    if not user_text:
        return {
            "say": f"Welkom bij {company['name']}. Waarmee kan ik u helpen?",
            "expect_input": True,
            "hangup": False,
        }

    text = user_text.lower()

    if "afspraak" in text:
        return {
            "say": "Natuurlijk. Voor welke dag en welk tijdstip wenst u een afspraak?",
            "expect_input": True,
            "hangup": False,
        }

    if "dank" in text:
        return {
            "say": "Graag gedaan. Fijne dag verder.",
            "expect_input": False,
            "hangup": True,
        }

    return {
        "say": "Ik heb u niet helemaal begrepen. Kunt u kort zeggen waarvoor u belt?",
        "expect_input": True,
        "hangup": False,
    }

