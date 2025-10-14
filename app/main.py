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
    "Daphnia Analysis": analysis_page,
    "Test Connectivity": test_connectivity,
}

MOINA_PAGES = {
    "Moina Analysis": test_connectivity,  # placeholder
}

st.sidebar.title("Navigation")

# Initialize session state for radio selections
if "selected_page" not in st.session_state:
    st.session_state.selected_page = "Code Generator"
    st.session_state.selected_species = "daphnia"

st.sidebar.markdown("### Daphnia magna")
daphnia_selection = st.sidebar.radio(
    "Select Daphnia page:",
    list(DAPHNIA_PAGES.keys()),
    index=list(DAPHNIA_PAGES.keys()).index(st.session_state.selected_page) 
          if st.session_state.selected_species == "daphnia" 
          else 0,
    label_visibility="collapsed",
    key="daphnia_radio",
)

st.sidebar.markdown("---")

st.sidebar.markdown("### Moina")
moina_selection = st.sidebar.radio(
    "Select Moina page:",
    list(MOINA_PAGES.keys()),
    index=list(MOINA_PAGES.keys()).index(st.session_state.selected_page) 
          if st.session_state.selected_species == "moina" 
          else 0,
    label_visibility="collapsed",
    key="moina_radio",
)

# Detect which radio button changed
if st.session_state.get("prev_daphnia") != daphnia_selection:
    st.session_state.selected_species = "daphnia"
    st.session_state.selected_page = daphnia_selection
    
if st.session_state.get("prev_moina") != moina_selection:
    st.session_state.selected_species = "moina"
    st.session_state.selected_page = moina_selection

# Store previous values for next comparison
st.session_state.prev_daphnia = daphnia_selection
st.session_state.prev_moina = moina_selection

# Render the selected page
if st.session_state.selected_species == "daphnia":
    DAPHNIA_PAGES[st.session_state.selected_page].render()
else:
    MOINA_PAGES[st.session_state.selected_page].render()
