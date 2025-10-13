import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
from app.core import utils
from app.ui import coder_page, analysis_page, test_connectivity

APP_DIR = os.path.dirname(__file__)
ICON_PATH = os.path.join(APP_DIR, "assets", "daphnia.svg")
LOGO_PATH = os.path.join(APP_DIR, "assets", "marine_ugent.png")

st.set_page_config(
    page_title="Daphnia Coding Protocol",
    page_icon=ICON_PATH,
    layout="wide",
)

utils.set_faded_bg_from_svg(
    ICON_PATH, overlay_alpha=0.90, img_width="48vw", img_position="center 6%"
)

DAPHNIA_PAGES = {
    "Code Generator": coder_page,
    "Analysis Page": analysis_page,
    "Test Connectivity": test_connectivity,
}

MOINA_PAGES = {
    "Analysis Page": test_connectivity,  # placeholder
}

st.sidebar.title("Navigation")

st.sidebar.markdown("### Daphnia magna")
daphnia_selection = st.sidebar.radio(
    "Select Daphnia page:",
    list(DAPHNIA_PAGES.keys()),
    label_visibility="collapsed",
    key="daphnia_radio",
)

st.sidebar.markdown("---")

st.sidebar.markdown("### Moina")
moina_selection = st.sidebar.radio(
    "Select Moina page:",
    list(MOINA_PAGES.keys()),
    label_visibility="collapsed",
    key="moina_radio",
)

# --- Only render the last changed section ---
if "last_species" not in st.session_state:
    st.session_state.last_species = "daphnia"

if st.session_state.daphnia_radio != st.session_state.get("prev_daphnia"):
    st.session_state.last_species = "daphnia"
if st.session_state.moina_radio != st.session_state.get("prev_moina"):
    st.session_state.last_species = "moina"

st.session_state.prev_daphnia = st.session_state.daphnia_radio
st.session_state.prev_moina = st.session_state.moina_radio

if st.session_state.last_species == "daphnia":
    DAPHNIA_PAGES[st.session_state.daphnia_radio].render()
else:
    MOINA_PAGES[st.session_state.moina_radio].render()
