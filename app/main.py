import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
from app.core import utils
from app.ui import coder_page, analysis_page, test_analysis
# (later you can add: from app.ui import moina_analysis, moina_coder, etc.)

# ========= BRANDING =========
APP_DIR = os.path.dirname(__file__)
ICON_PATH = os.path.join(APP_DIR, "assets", "daphnia.svg")
LOGO_PATH = os.path.join(APP_DIR, "assets", "marine_ugent.png")

st.set_page_config(
    page_title="Daphnia Coding Protocol",
    page_icon=ICON_PATH,
    layout="wide",
)

# ========= BACKGROUND =========
utils.set_faded_bg_from_svg(
    ICON_PATH, overlay_alpha=0.90, img_width="48vw", img_position="center 6%"
)

# ========= PAGE ROUTER =========
DAPHNIA_PAGES = {
    "Code Generator": coder_page,
    "Analysis Page": analysis_page,
    "Test Analysis": test_analysis,
}

MOINA_PAGES = {
    # placeholders until you add Moina modules
    "Analysis Page (Moina)": test_analysis,   # temporary reuse of test_analysis
}

# ========= SIDEBAR NAVIGATION =========
st.sidebar.title("Species Selection")

species = st.sidebar.radio(
    "Choose species:",
    ["🪳 Daphnia magna", "🦠 Moina"],
    horizontal=False,
)

if "Daphnia" in species:
    st.sidebar.markdown("### 🪳 Daphnia magna Pages")
    selection = st.sidebar.radio("Select a page:", list(DAPHNIA_PAGES.keys()))
    page = DAPHNIA_PAGES[selection]

elif "Moina" in species:
    st.sidebar.markdown("### 🦠 Moina Pages")
    selection = st.sidebar.radio("Select a page:", list(MOINA_PAGES.keys()))
    page = MOINA_PAGES[selection]

# ========= RENDER SELECTED PAGE =========
page.render()
