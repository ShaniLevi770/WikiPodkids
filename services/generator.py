# services/generator.py
# New approach: generate only opening+body (no closing), then append a fixed closing.
# This prevents mid-script "סיום/תודה" and avoids stitched endings.

import re
from services.config import (
    oai,
    OPENAI_MODEL,
    CHARS_PER_MIN,
    AVG_CHARS_PER_TOKEN,
    MAXTOK_BUFFER,
    MIN_TOKENS_FLOOR,
    MIN_CHARS_FLOOR,
)


def _token_cap(for_chars: int) -> int:
    """Convert desired characters into a safe token cap with headroom."""
    t = max(1, int(for_chars / AVG_CHARS_PER_TOKEN))
    return max(MIN_TOKENS_FLOOR, int(t * (1 + MAXTOK_BUFFER)))


def _trim_to_sentence(text: str, cap: int) -> str:
    """Trim at a sentence boundary before the hard cap."""
    slice_ = text[:cap]
    matches = list(re.finditer(r"[.!?](?=\s|$)", slice_))
    if matches:
        return slice_[:matches[-1].end()].rstrip()
    cut = slice_.rfind(" ")
    out = (slice_[:cut] if cut != -1 else slice_).rstrip()
    if not out.endswith((".", "!", "?")):
        out += "..."
    return out


def generate_kids_podcast_script(
    summary: str,
    topic: str,
    minutes: float = 5.0,
    age_label: str = "7-12",
) -> str:
    """
    Generate a Hebrew kids-podcast script sized to the requested minutes.
    Strategy:
    - Ask the model for opening+body ONLY (no סיום/תודה/סיכום headings).
    - If short, one continuation adds more body (no closing).
    - Append a fixed closing paragraph ourselves.
    """

    target_chars = max(MIN_CHARS_FLOOR, int(round(minutes * CHARS_PER_MIN)))
    min_chars = int(target_chars * 1.10)  # push above target to avoid under-length
    max_chars = int(target_chars * 1.25)  # generous headroom; trimmed if exceeded
    body_goal = min_chars - 180  # leave room for closing paragraph

    if age_label == "3-6":
        age_tone = (
            "שפה פשוטה, חמה ורגועה לילדים בגילאי 3-6. "
            "משפטים קצרים, רגעי צחוק, והזמנות לשיתוף."
        )
    else:
        age_tone = (
            "דבר לילדים בגילאי 7-12; הוסף 1-2 עובדות מפתיעות שמתאימות לגיל."
        )

    system_msg = (
        "אתה כותב תסריט לפודקאסט ילדים בעברית. "
        "אל תכתוב כותרת או פסקה בשם סיום/סיכום/תודה/להתראות. "
        "אין אמירות סיום בכלל; שמור אותן לסוף שנוסיף אחרי הגוף."
    )

    user_prompt = f"""
כתוב פתיחה קצרה וגוף בלבד לפודקאסט ילדים בעברית לפי הנושא והתקציר.
אין לכלול סיום, סיכום, תודה או להתראות.
{age_tone}
נושא: {topic}
תקציר בסיסי:
\"\"\"{summary}\"\"\"

מבנה:
1) פתיחה קצרה ומזמינה.
2) גוף עם 4-6 חלקים, כל אחד מוסיף רעיון/דוגמה חדשה ללא חזרה על הקודם.

הנחיות:
- ללא כותרת או פסקה בשם "סיום"/"סיכום"/"תודה"/"להתראות".
- אל תחזור על פסקאות; כל חלק חדש ומתקדם.
- שמור על רצף טבעי, אפשר כותרות קצרות בין חלקים.
- אורך מטרה לגוף בלבד: לפחות {body_goal} תווים, לא לעבור את {max_chars} כולל סיום שנוסיף.
""".strip()

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_prompt},
    ]

    resp = oai.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.82,
        max_tokens=_token_cap(max_chars),
        presence_penalty=0.6,
        frequency_penalty=0.35,
        stop=["\nסיום", "\nסיכום", "\nתודה", "\nלהתראות"],
    )

    body = (resp.choices[0].message.content or "").strip()

    # If body is short, extend once (body-only)
    if len(body) < body_goal:
        need = max(0, body_goal - len(body))
        cont_prompt = (
            f"הרחב את גוף התסריט בלבד. ללא פתיחה חדשה וללא סיום/סיכום/תודה. "
            f"הוסף תוכן חדש (רעיונות/דוגמאות) עד כ-{need} תווים נוספים, "
            f"בלי לחזור על פסקאות קודמות."
        )
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "assistant", "content": body},
            {"role": "user", "content": cont_prompt},
        ]
        resp2 = oai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.78,
            max_tokens=_token_cap(max_chars - len(body)),
            presence_penalty=0.6,
            frequency_penalty=0.35,
            stop=["\nסיום", "\nסיכום", "\nתודה", "\nלהתראות"],
        )
        addition = (resp2.choices[0].message.content or "").strip()
        if addition:
            body = body + "\n\n" + addition

    # Compose final script with a fixed closing paragraph
    closing = "תודה שהייתם איתנו במסע הזה! נתראה בפרק הבא עם עוד נושאים מעניינים ומסקרנים."
    script = body.rstrip() + "\n\n" + closing

    if len(script) > max_chars:
        script = _trim_to_sentence(script, max_chars)

    return script
