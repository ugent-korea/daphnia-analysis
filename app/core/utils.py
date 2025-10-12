import base64, datetime
import streamlit as st
from zoneinfo import ZoneInfo

def set_faded_bg_from_svg(svg_path: str, overlay_alpha: float = 0.86,
                          img_width: str = "55vw", img_position: str = "center 8%"):
    with open(svg_path, "r", encoding="utf-8") as f:
        svg = f.read()
    b64 = base64.b64encode(svg.encode("utf-8")).decode()

    st.markdown(
        f"""
        <style>
        [data-testid="stHeader"] {{ background: transparent; }}
        .block-container {{ padding-top: 1rem; max-width: 900px; margin: 0 auto; }}
        .stApp {{
          background-image:
            linear-gradient(rgba(255,255,255,{overlay_alpha}), rgba(255,255,255,{overlay_alpha})),
            url("data:image/svg+xml;base64,{b64}");
          background-repeat: no-repeat, no-repeat;
          background-size: cover, {img_width} auto;
          background-position: center, {img_position};
          background-attachment: fixed, fixed;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def today_suffix(tz="Asia/Seoul") -> str:
    return datetime.datetime.now(ZoneInfo(tz)).strftime("_%m%d")

def last_refresh_kst(meta) -> str:
    ts = (meta or {}).get("last_refresh")
    if not ts:
        return "unknown"
    s = ts.replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(s)
        kst = dt.astimezone(ZoneInfo("Asia/Seoul"))
        return kst.strftime("%Y-%m-%d %H:%M:%S KST")
    except Exception:
        return ts