# services/generator.py
# Generate opening + body only; append fixed closing to avoid mid-script endings.

import random
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

# Rotating, topic-aware sign-offs so saved episodes don't all end on the
# exact same sentence. {topic} is filled in per episode.
_CLOSING_TEMPLATES = [
    "איזה כיף היה ללמוד היום על {topic}! תודה שהקשבתם, ונתראה בפרק הבא עם נושא חדש ומרתק.",
    "זהו לנו להיום עם הסיפור המרתק על {topic}. תודה שהצטרפתם, ונשמע שוב בפעם הבאה!",
    "תודה שיצאתם איתנו למסע אל {topic}! שמרו על הסקרנות, ונתראה בפרק הבא.",
    "סיימנו פרק נוסף על {topic} — היה כיף לגלות ביחד. נתראה בקרוב עם עוד נושא מסקרן!",
]

# Content-safety instructions applied to every attempt; reinforced further
# on the retry after a moderation flag (see _is_flagged).
_SAFETY_RULES = (
    "אין לכלול שום תוכן מפחיד, אלים, עצוב, מלחיץ, מדאיג או לא מתאים לילדים — "
    "הטון תמיד חיובי, סקרן ומעודד. "
    "כל עובדה בתסריט חייבת להתבסס אך ורק על התקציר שסופק; "
    "אין להמציא תאריכים, שמות, מספרים או פרטים שאינם מופיעים בתקציר."
)


def _token_cap(for_chars: int) -> int:
    t = max(1, int(for_chars / AVG_CHARS_PER_TOKEN))
    return max(MIN_TOKENS_FLOOR, int(t * (1 + MAXTOK_BUFFER)))


def _trim_to_sentence(text: str, cap: int) -> str:
    slice_ = text[:cap]
    matches = list(re.finditer(r"[.!?](?=\s|$)", slice_))
    if matches:
        return slice_[:matches[-1].end()].rstrip()
    cut = slice_.rfind(" ")
    out = (slice_[:cut] if cut != -1 else slice_).rstrip()
    if not out.endswith((".", "!", "?")):
        out += "..."
    return out


def _is_flagged(text: str) -> bool:
    """
    Best-effort content-safety check via OpenAI's (free) Moderation endpoint.
    Fails open (assumes safe) on any error — a moderation-API hiccup should
    never block episode generation, only genuine flags should trigger a retry.
    """
    try:
        result = oai.moderations.create(model="omni-moderation-latest", input=text)
        return bool(result.results[0].flagged)
    except Exception:
        return False


def generate_kids_podcast_script(
    summary: str,
    topic: str,
    minutes: float = 5.0,
    age_label: str = "7-12",
) -> str:
    target_chars = max(MIN_CHARS_FLOOR, int(round(minutes * CHARS_PER_MIN)))
    min_chars = int(target_chars * 1.10)
    max_chars = int(target_chars * 1.25)
    body_goal = min_chars - 180

    if age_label == "3-6":
        age_tone = (
            "שפה פשוטה מאוד למאזינים בגילאי 3-6: משפטים קצרים (עד כ-8-10 מילים), "
            "חמים ורגועים, עם רגעי צחוק קלילים והזמנות לשיתוף. "
            "בלי מילים מסובכות ובלי שום דבר מפחיד או עצוב."
        )
    else:
        age_tone = (
            "דברו בגובה העיניים לילדים בגילאי 7-12, בסגנון סיפורי ומעורר סקרנות. "
            "אפשר להוסיף זווית מעניינת או השוואה יומיומית לעובדות שכבר מופיעות בתקציר — "
            "אך אך ורק על בסיס התקציר, בלי להמציא מידע חדש."
        )

    def _attempt(strict_safety: bool) -> str:
        system_msg = (
            "אתה כותב תסריט לפודקאסט חינוכי-בידורי לילדים בעברית, שמטרתו ללמד תוך כדי הנאה. "
            "אל תכתוב כותרת או פסקה בשם סיום/סיכום/תודה/להתראות. "
            "אין אמירות סיום בכלל; שמור אותן לסוף שנוסיף אחרי הגוף. "
            + _SAFETY_RULES
            + (
                " הקפידו במיוחד הפעם: זהו ניסיון חוזר בעקבות חשד לתוכן לא מתאים — "
                "היו שמרניים במיוחד ואל תתקרבו לגבול."
                if strict_safety
                else ""
            )
        )

        user_prompt = f"""
כתוב פתיחה קצרה וגוף בלבד לפודקאסט ילדים בעברית לפי הנושא והתקציר.
אין לכלול סיום, סיכום, תודה או להתראות.
{age_tone}
נושא: {topic}
תקציר בסיסי:
\"\"\"{summary}\"\"\"

מבנה:
1) פתיחה קצרה ומזמינה, מותאמת לנושא הספציפי (לא תבנית גנרית שמתאימה לכל נושא).
2) גוף עם 4-6 חלקים, כל אחד מוסיף רעיון/דוגמה חדשה ללא חזרה על הקודם.
3) לקראת הסוף (בלי כותרת בשם "סיכום"): שאלו באופן טבעי "אז מה למדנו היום?" והזכירו
   בקצרה 2-3 מהעובדות המעניינות שכבר הוזכרו למעלה, בניסוח חדש ולא כהעתקה.

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

        if len(body) < body_goal:
            need = max(0, body_goal - len(body))
            cont_prompt = (
                f"הרחב את גוף התסריט בלבד. ללא פתיחה חדשה וללא סיום/סיכום/תודה. "
                f"הוסף תוכן חדש (רעיונות/דוגמאות) עד כ-{need} תווים נוספים, "
                f"בלי לחזור על פסקאות קודמות. {_SAFETY_RULES}"
            )
            cont_messages = [
                {"role": "system", "content": system_msg},
                {"role": "assistant", "content": body},
                {"role": "user", "content": cont_prompt},
            ]
            resp2 = oai.chat.completions.create(
                model=OPENAI_MODEL,
                messages=cont_messages,
                temperature=0.78,
                max_tokens=_token_cap(max_chars - len(body)),
                presence_penalty=0.6,
                frequency_penalty=0.35,
                stop=["\nסיום", "\nסיכום", "\nתודה", "\nלהתראות"],
            )
            addition = (resp2.choices[0].message.content or "").strip()
            if addition:
                body = body + "\n\n" + addition

        closing = random.choice(_CLOSING_TEMPLATES).format(topic=topic)
        closing_block = "\n\n" + closing
        body = body.rstrip()
        budget_for_body = max(0, max_chars - len(closing_block))
        if len(body) > budget_for_body:
            body = _trim_to_sentence(body, budget_for_body)

        return (body + closing_block).strip()

    script = _attempt(strict_safety=False)
    if _is_flagged(script):
        script = _attempt(strict_safety=True)
    return script
