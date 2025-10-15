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
    "Daphnia Code Generator": coder_page,
    "Daphnia Analysis": analysis_page,
    "Test Connectivity": test_connectivity,
}

MOINA_PAGES = {
    "Moina Analysis": test_connectivity,  # placeholder
}

st.sidebar.title("Navigation")

# Initialize session state for page selection
if "selected_page" not in st.session_state:
    st.session_state.selected_page = "Daphnia Code Generator"
    st.session_state.selected_species = "daphnia"

# Create a simple vertical menu
st.sidebar.markdown("### Daphnia magna")
for page_name in DAPHNIA_PAGES.keys():
    if st.sidebar.button(
        page_name, 
        key=f"daphnia_{page_name}",
        use_container_width=True,
        type="primary" if (st.session_state.selected_species == "daphnia" and st.session_state.selected_page == page_name) else "secondary"
    ):
        st.session_state.selected_species = "daphnia"
        st.session_state.selected_page = page_name
        st.rerun()

st.sidebar.markdown("---")

st.sidebar.markdown("### Moina")
for page_name in MOINA_PAGES.keys():
    if st.sidebar.button(
        page_name,
        key=f"moina_{page_name}",
        use_container_width=True,
        type="primary" if (st.session_state.selected_species == "moina" and st.session_state.selected_page == page_name) else "secondary"
    ):
        st.session_state.selected_species = "moina"
        st.session_state.selected_page = page_name
        st.rerun()

# Render the selected page
if st.session_state.selected_species == "daphnia":
    DAPHNIA_PAGES[st.session_state.selected_page].render()
else:
    MOINA_PAGES[st.session_state.selected_page].render()
