# services/generator.py
from services.config import (
    oai, OPENAI_MODEL, CHARS_PER_MIN,
    AVG_CHARS_PER_TOKEN, MAXTOK_BUFFER, MIN_TOKENS_FLOOR, MIN_CHARS_FLOOR
)
import re


def _token_cap(for_chars: int) -> int:
    """
    Convert a desired number of characters into a safe token cap,
    with a small configurable headroom.
    """
    t = max(1, int(for_chars / AVG_CHARS_PER_TOKEN))
    return max(MIN_TOKENS_FLOOR, int(t * (1 + MAXTOK_BUFFER)))


def _trim_to_sentence(text: str, cap: int) -> str:
    """
    If we ran long, trim at the last sentence-ending punctuation
    before the hard cap. Fallback: last space; add ellipsis if needed.
    """
    slice_ = text[:cap]
    matches = list(re.finditer(r'[.!?…](?=\s|$)', slice_))
    if matches:
        return slice_[:matches[-1].end()].rstrip()
    cut = slice_.rfind(" ")
    out = (slice_[:cut] if cut != -1 else slice_).rstrip()
    if not out.endswith((".", "!", "?", "…")):
        out += "…"
    return out


def generate_kids_podcast_script(
    summary: str,
    topic: str,
    minutes: float = 5.0,
    age_label: str = "7-12",
) -> str:
    """
    Generate a Hebrew kids-podcast script sized to the requested minutes.
    - First call aims for target length.
    - If short, ask the model to continue (up to 2 times).
    - If long, trim at a sentence boundary to a tight max.
    """

    # 1) Target size (characters) scales with requested minutes
    target_chars = max(MIN_CHARS_FLOOR, int(round(minutes * CHARS_PER_MIN)))
    # Tight window: must reach ~95% of target, never exceed ~105%
    min_chars = int(target_chars * 0.95)
    max_chars = int(target_chars * 1.05)

    # 2) Tone by age
    if age_label == "3-6":
        age_tone = "הקהל: ילדים צעירים בגילי 3–6. משפטים קצרים מאוד, מילים פשוטות וחזרות עדינות."
    else:
        age_tone = "הקהל: ילדים בגילי 7–12; שלבו 1–2 עובדות וואו."

    system_msg = "אתה מלמד ילדים בצורה מעניינת בעברית פשוטה."

    # 3) First prompt asks for at least target_chars and to keep sentences whole
    user_prompt = f"""
אתה כותב תסריט לפודקאסט כיפי לילדים בעברית פשוטה וברורה.
{age_tone}
הנושא: {topic}
מידע אמין לשימוש (אל תמציא עובדות):
\"\"\"{summary}\"\"\"

הוראות:
- פתח ב"היי ילדים!".
- כלול עובדות מעניינות על הנושא.
- הוסף בדיחה קלילה או אנקדוטה מצחיקה.
- שאל שאלות פתוחות לא ילדותיות כדי לעודד חשיבה.
- שלב משחק "ענו איתי" עם עד 2 שאלות קצרות בהקשר של מה שאתה עומד להגיד (כן/לא, ניחוש קטן).
- בלי אימוג'ים ובלי רשימות — רק פסקאות זורמות.
- כתוב לפחות {target_chars} תווים (לא פחות), וסיים משפט מלא.
- הימנע מתכנים מפחידים/עצובים.
כתוב רק את הטקסט עצמו, בלי כותרות.
""".strip()

    text = ""
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": user_prompt},
    ]

    # 4) Initial call + up to 2 continuations until we hit the minimum
    for _ in range(3):
        remaining = max_chars - len(text)
        if remaining <= 0:
            break  # already at/over the hard cap

        resp = oai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.9,
            max_tokens=_token_cap(remaining),  # strictly budget by what's left
            presence_penalty=0.2,
            frequency_penalty=0.1,
        )

        part = (resp.choices[0].message.content or "").strip()
        if not part:
            break

        text += (("\n\n" if text else "") + part)

        # If we overshot the cap, trim neatly and stop
        if len(text) > max_chars:
            text = _trim_to_sentence(text, max_chars)
            break

        # Stop once we reached the minimum
        if len(text) >= min_chars:
            break

        # Ask to continue with at most what we still need (and never beyond max)
        need = max(0, min(min_chars - len(text), max_chars - len(text)))
        messages = [
            {"role": "system",    "content": system_msg},
            {"role": "assistant", "content": part},
            {"role": "user",      "content": (
                f"המשך מאותה נקודה. הוסף עד {need} תווים לכל היותר, "
                "בלי לחזור על מה שכבר נכתב ובאותו סגנון. עצור מיד בסוף משפט כאשר אתה מגיע לאורך הזה."
            )},
        ]

    return text
