import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
from app.core import utils
from app.ui import coder_page, analysis_page, test_connectivity

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
    "Test Connectivity": test_connectivity,
}

MOINA_PAGES = {
    # placeholders until Moina modules are added
    "Analysis Page": test_connectivity,
}

# ========= SIDEBAR NAVIGATION =========
st.sidebar.title("Navigation")

selected_page = None

with st.sidebar:
    with st.expander("Daphnia magna", expanded=True):
        daphnia_selection = st.radio(
            "Select a page:",
            list(DAPHNIA_PAGES.keys()),
            label_visibility="collapsed",
            key="daphnia_radio",
        )
        if daphnia_selection:
            selected_page = DAPHNIA_PAGES[daphnia_selection]

    with st.expander("Moina", expanded=False):
        moina_selection = st.radio(
            "Select a page:",
            list(MOINA_PAGES.keys()),
            label_visibility="collapsed",
            key="moina_radio",
        )
        if moina_selection:
            selected_page = MOINA_PAGES[moina_selection]

# ========= RENDER SELECTED PAGE =========
if selected_page:
    selected_page.render()
else:
    st.write("Select a page from the sidebar to begin.")
