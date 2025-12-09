# services/wiki.py
import re
import warnings
import wikipedia

# Silence BeautifulSoup parser warning emitted by wikipedia package
warnings.filterwarnings("ignore", category=UserWarning, module="wikipedia")

wikipedia.set_lang("he")

def is_mixed_he_en(s: str) -> bool:
    has_he = re.search(r"[\u0590-\u05FF]", s) is not None
    has_en = re.search(r"[A-Za-z]", s) is not None
    return has_he and has_en

def get_hebrew_summary(topic: str, sentences: int = 6):
    if is_mixed_he_en(topic):
        return False, "הטקסט מכיל עברית ואנגלית — נסו בעברית בלבד."
    try:
        summary = wikipedia.summary(topic, sentences=sentences)
        return True, summary.strip()
    except (wikipedia.DisambiguationError, wikipedia.PageError):
        return False, "לא נמצא ערך מתאים או הערך לא חד-משמעי."
    except Exception:
        return False, "אירעה שגיאה בשליפת ויקיפדיה. נסו ערך אחר."
