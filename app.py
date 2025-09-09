# app.py
import html
import os, streamlit as st
import mutagen.mp3

# --- Load .env early so services can read keys ---
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True), override=True)

# ---------- Services ----------
from services.wiki import get_hebrew_summary
from services.generator import generate_kids_podcast_script
from services.tts import split_text_safe, synthesize_chunks_to_file
from services.store import (
    get_cached_podcast,
    save_on_five_stars,
    delete_episode_admin,
    upload_mp3_to_supabase,
    list_saved_podcasts_alphabetical,  # NEW
)

# ---------- NEW: persistent counter + push + shutdown ----------
# Uses Supabase + Pushover (PUSHOVER_APP_TOKEN, PUSHOVER_USER_KEY) and the app_state table
import services.app_state as app_state

# ---------- Settings & page ----------
DEFAULT_HE_VOICE = "he-IL-Wavenet-D"

st.set_page_config(page_title="🎙️ פודקאסט ילדים מוויקיפדיה", layout="wide")

st.markdown("""
<style>
  /* ---------- RTL baseline ---------- */
  html, body, [data-testid="stSidebar"], [data-testid="stAppViewContainer"] {
    direction: rtl !important;
    text-align: right;
  }
  input, textarea { direction: rtl; }

  :root { --sbw: 420px; --gap: 16px; }

  /* ---------- Desktop (≥992px): fix sidebar and push app ---------- */
  @media (min-width: 992px){
    [data-testid="stSidebar"]{
      position: fixed !important;
      top: 0; right: 0; bottom: 0; left: auto;
      width: var(--sbw) !important;
      max-width: var(--sbw) !important;
      background: #f2f3f5;
      border-left: 1px solid #e5e7eb;
      z-index: 100;
    }
    [data-testid="stSidebar"] > div:first-child{
      height: 100%;
      overflow-y: auto;
      background: transparent !important;
    }
    /* Push the entire app view so it doesn't sit under the fixed sidebar */
    [data-testid="stAppViewContainer"]{
      padding-right: calc(var(--sbw) + var(--gap)) !important;
    }
    /* Nudge the top header/toolbar as well */
    [data-testid="stHeader"]{
      right: calc(var(--sbw) + var(--gap)) !important;
    }
  }

  /* ---------- Mobile (<992px): default flow, no fixed sidebar ---------- */
  @media (max-width: 991.98px){
    [data-testid="stSidebar"]{ display: none !important; }
    [data-testid="stAppViewContainer"]{ padding-right: 0 !important; }
    audio{ width: 100% !important; }
  }

  /* ---------- Nice box for script text ---------- */
  .script-pre{
    background:#fff;
    border:1px solid #e5e7eb;
    border-radius:10px;
    padding:14px 16px;
    white-space:pre-wrap; word-wrap:break-word;
    font-size:1.05rem; line-height:1.85;
  }
  .dim-note{ color:#6b7280; font-size:.95rem; }
</style>
""", unsafe_allow_html=True)


st.title("🎙️ פודקאסט ילדים מוויקיפדיה")
st.caption("⭐ כל פרק חדש נשמר למאגר רק אם הדירוג הוא ⭐⭐⭐⭐⭐.")

# ---------- Session state ----------
ss = st.session_state
ss.setdefault("topic", "")
ss.setdefault("minutes", 2.5)
ss.setdefault("script", None)
ss.setdefault("audio_path", None)
ss.setdefault("public_url_saved", None)
ss.setdefault("storage_key_saved", None)
ss.setdefault("using_cached", False)
ss.setdefault("last_summary", None)
# Sidebar state
ss.setdefault("sb_page", 1)
ss.setdefault("sb_search", "")

# ---------- NEW Sidebar: App ON/OFF + total searches (persistent) ----------
with st.sidebar.expander("⚙️ ניהול אפליקציה (כיבוי/הפעלה)"):
    ADMIN_DASH_SECRET = os.getenv("ADMIN_DASH_SECRET", "")
    if ADMIN_DASH_SECRET:
        provided = st.text_input("סיסמת מנהל", type="password", key="admin_dash_secret")
        if provided and provided == ADMIN_DASH_SECRET:
            st.success("מצב מנהל פעיל")
            c1, c2 = st.columns(2)
            if c1.button("🟢 הפעל אפליקציה"):
                app_state.set_enabled(True); st.toast("האפליקציה הופעלה", icon="✅")
            if c2.button("🔴 כבה אפליקציה"):
                app_state.set_enabled(False); st.toast("האפליקציה כובתה", icon="🛑")
            st.caption(f"סה\"כ חיפושים מצטבר: {app_state.get_state().get('searches_total', 0)}")
        else:
            st.caption("הכנס/י סיסמה כדי לשלוט בהדלקה/כיבוי ולהציג מונה חיפושים.")
    else:
        st.caption("להפעלת שליטה מרחוק הוסיפו ADMIN_DASH_SECRET ל-.env")

# If app is disabled, block early
if not app_state.is_enabled():
    st.error("🚫 האפליקציה כבויה כרגע. נסו שוב מאוחר יותר.")
    st.stop()

# ---------- Sidebar: Saved podcasts (alphabetical + search) ----------
with st.sidebar:
    st.header("📚 פרקים שמורים (א-ת)")

    # Search box (kept in session)
    sb_search = st.text_input("חיפוש לפי נושא", key="sb_search", placeholder="חפשי נושא…")

    # Prev / Next pagination
    sb_limit = 10
    col_a, col_b, col_c = st.columns([1, 1, 2])
    with col_a:
        if st.button("⬅️ הקודם", use_container_width=True) and ss["sb_page"] > 1:
            ss["sb_page"] -= 1; st.rerun()
    with col_b:
        if st.button("➡️ הבא", use_container_width=True):
            ss["sb_page"] += 1; st.rerun()
    with col_c:
        st.write(f"עמוד: **{ss['sb_page']}**")

    sb_offset = (ss["sb_page"] - 1) * sb_limit

    try:
        with st.spinner("טוען פרקים (א-ת)…"):
            rows = list_saved_podcasts_alphabetical(
                limit=sb_limit,
                offset=sb_offset,
                collapse_by_minutes=True,
                search=(sb_search or None),
            )
    except Exception as e:
        rows = []; st.error(f"שגיאה בטעינה: {e}")

    if not rows:
        st.write("אין תוצאות.")
    else:
        for i, r in enumerate(rows, start=1):
            topic_i = r.get("topic", "—")
            minutes_i = r.get("minutes", 5)
            public_url_i = r.get("public_url") or ""
            created_i = r.get("created_at", "")
            stars_i = r.get("stars", 0)
            script_i = r.get("script")
            storage_key_i = r.get("storage_key")

            with st.container(border=True):
                st.write(f"**{topic_i}** · ⏱️ {int(minutes_i)} ד׳ · ⭐ {stars_i}")
                if created_i: st.caption(created_i)
                if public_url_i:
                    st.link_button("פתח MP3", public_url_i, type="secondary", use_container_width=True)

                if st.button("טעני קובץ", key=f"load_alpha_{sb_offset+i}", use_container_width=True):
                    # Hydrate state to mimic cached episode
                    ss["using_cached"] = True
                    ss["topic"] = topic_i
                    ss["minutes"] = float(minutes_i) if isinstance(minutes_i, (int, float)) else 5.0
                    ss["script"] = script_i
                    ss["public_url_saved"] = public_url_i
                    ss["audio_path"] = None
                    ss["storage_key_saved"] = storage_key_i
                    st.rerun()

# ---------- Helpers ----------
def render_episode_view(*, script: str, public_url: str, is_cached: bool):
    if is_cached:
        st.success("נמצא פרק שמור ⭐⭐⭐⭐⭐ — משתמשים בו אוטומטית.")
    st.markdown("## האזנה לפרק:")
    st.audio(public_url)
    st.markdown(f"[🔗 הורדה/פתיחה]({public_url})")
    st.markdown("## התסריט 🧾")
    st.markdown(
        f'<div class="script-pre">{html.escape(script or "")}</div>',
        unsafe_allow_html=True,
    )
    if is_cached:
        st.caption("כדי ליצור חדש, ניתן למחוק כמנהלת למטה.")

def star_rating(*, default: int = 5, key: str = "rating_stars") -> int:
    st.markdown("### ⭐ דירוג")
    st.markdown('<div class="dim-note">(5 כוכבים) — כדי לשמור לאחסון בחרו ⭐⭐⭐⭐⭐</div>', unsafe_allow_html=True)
    selected = st.radio(
        "בחרו דירוג",
        options=[1, 2, 3, 4, 5],
        index=default - 1,
        horizontal=True,
        format_func=lambda n: "⭐" * n + "☆" * (5 - n),
        label_visibility="collapsed",
        key=key,
    )
    return int(selected)

# ---------- Inputs card ----------
#st.markdown('<div class="card">', unsafe_allow_html=True)

topic = st.text_input(
    "נושא (עברית):",
    value=ss.get("topic", ""),
    placeholder="למשל איינשטיין, ליאו מסי , דינוזאורים",
    key="topic_input",
)

length_label = st.selectbox(
    "⏱️ אורך משוער:",
    ["2.5~ דקות", "5.0~ דקות", "7.5~ דקות"],
    index={2.5: 0, 5.0: 1, 7.5: 2}.get(ss.get("minutes", 2.5), 1),
    key="length_select",
)
minutes = {"2.5~ דקות": 2.5, "5.0~ דקות": 5.0, "7.5~ דקות": 7.5}[length_label]

age_ui = st.selectbox("קהל יעד:", options=["12-7", "6-3"], index=0, key="age_select")
age_label = "7-12" if age_ui == "12-7" else "3-6"

search_clicked = st.button("חפש 🔎", key="search_btn")

st.markdown('</div>', unsafe_allow_html=True)

if topic:
    ss["topic"] = topic
ss["minutes"] = minutes

# ---------- Fetch on search click ----------
if search_clicked and ss["topic"]:

    # Count this search persistently + push on every 10th (10,20,30…)
    try:
        total_searches = app_state.increment_searches_and_maybe_notify(every=10)
        st.caption(f"(מידע למפתחת) חיפושים מצטבר: {total_searches}")
    except Exception:
        # never break the app if push/counter fails
        st.caption("(מידע למפתחת) לא ניתן לעדכן מונה חיפושים כרגע.")

    # Try to use a cached episode first
    try:
        cached = get_cached_podcast(ss["topic"], ss["minutes"])
    except Exception as e:
        cached = None
        st.warning(f"לא ניתן לטעון פרק שמור כרגע: {e}")

    if cached:
        ss["using_cached"] = True
        ss["script"] = cached.get("script")
        ss["audio_path"] = None
        ss["public_url_saved"] = cached.get("public_url")
        ss["storage_key_saved"] = None
        ss["last_summary"] = None
    else:
        ss["using_cached"] = False
        ss["public_url_saved"] = None
        ss["storage_key_saved"] = None

        st.toast("מחפשת מידע ראשוני…", icon="🔎")
        with st.spinner("מביאה תקציר מוויקיפדיה…"):
            ok, summary_or_msg = get_hebrew_summary(ss["topic"])
        if not ok:
            st.error(summary_or_msg)
        else:
            ss["last_summary"] = summary_or_msg

            with st.expander("📘 תקציר מוויקיפדיה (לחצי להצגה)", expanded=False):
                st.write(summary_or_msg)
            #st.toast("✍️ כותבת תסריט מותאם לילדים…", icon="✍️")
            with st.spinner("מייצרת תסריט…"):
                ss["script"] = generate_kids_podcast_script(
                    summary=summary_or_msg,
                    topic=ss["topic"],
                    minutes=ss["minutes"],
                    age_label=age_label,
                )

            # TTS and save
            try:
                st.toast("🎙️ מסנתזת קריינות…", icon="🎙️")
                with st.spinner("טקסט לדיבור (TTS)…"):
                    segments = split_text_safe(ss["script"], max_chars=1200)
                    audio_path = synthesize_chunks_to_file(
                        segments, voice_name=DEFAULT_HE_VOICE, filename="podcast.mp3"
                    )
                ss["audio_path"] = str(audio_path)

                # --- Length calibration (CHARS_PER_MIN) ---
                try:
                    from mutagen.mp3 import MP3  # make sure 'mutagen' is in requirements.txt
                    audio = MP3(ss["audio_path"])
                    dur_min = max(0.01, audio.info.length / 60.0)
                    cpm = int(len(ss["script"]) / dur_min)
                    st.caption(f"מדידה: {len(ss['script'])} תווים • {dur_min:.2f} דקות • ≈{cpm} תווים/דקה (CHARS_PER_MIN)")
                except Exception:
                    pass
            except Exception as e:
                st.error(f"שגיאה ביצירת אודיו: {e}")
                ss["audio_path"] = None

# ---------- Render / Actions ----------
# 1) Cached episode → render + admin delete form
if ss.get("using_cached") and ss.get("public_url_saved") and ss.get("script"):
    render_episode_view(script=ss["script"], public_url=ss["public_url_saved"], is_cached=True)

    with st.expander("ניהול פרק שמור (מחק עם אסימון מנהל)", expanded=False):
        with st.form("admin_delete_form", clear_on_submit=False):
            st.text_input(
                "אסימון מנהלי (למחיקה)",
                type="password",
                key="admin_token_input",
                help="הדביקי כאן את ADMIN_TOKEN בדיוק כפי שב-.env. מחיקה מתבצעת רק בלחיצה על הכפתור.",
            )
            do_delete = st.form_submit_button("🗑️ מחק פרק (מנהל)")

        if do_delete:
            token = (st.session_state.get("admin_token_input") or "").strip()
            if not token:
                st.warning("יש להזין אסימון מנהל.")
            else:
                with st.spinner("מוחק מהמסד ומ-Supabase…"):
                    try:
                        ok, msg = delete_episode_admin(ss["topic"], ss["minutes"], token)
                        st.write(f"DEBUG: delete_episode_admin returned ok={ok}, msg={msg}")
                    except Exception as e:
                        ok, msg = False, f"שגיאה: {e}"
                        st.write(f"DEBUG: exception during delete: {e}")

                if ok:
                    st.success(msg or "הפרק נמחק בהצלחה.")
                    for k in ("admin_token_input", "script", "audio_path", "public_url_saved", "storage_key_saved"):
                        ss.pop(k, None)
                    ss["using_cached"] = False
                    st.write("DEBUG: state cleared, rerunning app")
                    st.rerun()
                else:
                    st.error(msg or "מחיקה נכשלה. ודאי שאסימון המנהל תקין.")
                    st.write("DEBUG: deletion failed, not rerunning")

    st.stop()

# 2) Show newly generated (if any, and not cached)
if ss.get("script") and not ss.get("using_cached"):
    st.markdown("## האזנה לפרק:")
    if ss.get("audio_path"):
        st.audio(ss["audio_path"])
        try:
            with open(ss["audio_path"], "rb") as fh:
                mp3_bytes = fh.read()
            st.download_button(
                "⬇️ הורד MP3 (מקומי)",
                mp3_bytes,
                file_name=f"{ss['topic']}_{int(ss['minutes']*60)}s.mp3",
                mime="audio/mpeg",
            )
        except Exception as e:
            st.warning(f"שגיאה בהכנת הורדה מקומית: {e}")

    st.markdown("## התסריט 🧾")
    st.markdown(
        f'<div class="script-pre">{html.escape(ss["script"] or "")}</div>',
        unsafe_allow_html=True,
    )

# ---------- Rating & Save ----------
st.markdown("---")
stars = star_rating(default=5, key="rating_stars")

if st.button("שמור דירוג"):
    if stars != 5:
        st.info("הפרק נשמר רק אם הדירוג הוא ⭐⭐⭐⭐⭐.")
    elif ss.get("using_cached"):
        st.info("הפרק כבר שמור ⭐⭐⭐⭐⭐ — אין צורך לשמור שוב.")
    elif not ss.get("script") or not ss.get("audio_path"):
        st.error("אין תסריט/אודיו לשמירה. לחצי 'חפש' כדי לייצר קודם.")
    else:
        try:
            with st.spinner("⬆️ מעלה את האודיו ושומר לבסיס הנתונים..."):
                public_url, storage_key = upload_mp3_to_supabase(ss["audio_path"])
                ok = save_on_five_stars(
                    topic=ss["topic"],
                    minutes=ss["minutes"],
                    script=ss["script"],
                    stars=5,
                    public_url=public_url,
                    storage_key=storage_key,
                )
            if ok:
                ss["public_url_saved"] = public_url
                ss["storage_key_saved"] = storage_key
                ss["using_cached"] = True
                st.success("🎉 הפרק נשמר! הועלה לענן והקישור נשמר בבסיס הנתונים.")
                st.markdown(f"[🔗 קישור קבוע ל-MP3]({public_url})")
            else:
                st.error("השמירה לא בוצעה.")
        except Exception as e:
            st.error(f"שגיאה בהעלאת האודיו/שמירה: {e}")