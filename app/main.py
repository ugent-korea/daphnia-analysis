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
    # "Test Connectivity": test_connectivity,
}

# MOINA_PAGES = {
#     "Moina Analysis": test_connectivity,  # placeholder
# }

# st.sidebar.title("Navigation")
# --- Sidebar header: flush logo (covers top gap) ---
with st.sidebar:
    # Nuke all default top padding in the sidebar and pull the image up a bit
    st.markdown(
        """
        <style>
            /* Remove default top padding in the sidebar container */
            section[data-testid="stSidebar"] .block-container { padding-top: 0 !important; }
            section[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }

            /* Pull the first image upward to cover the remaining gap under the chevrons */
            section[data-testid="stSidebar"] [data-testid="stImage"] img {
                margin-top: -28px !important;           /* tweak if you want it tighter/looser */
                display: block;
            }

            /* Optional: remove rounded white “card” feel if any wrapper adds it */
            section[data-testid="stSidebar"] [data-testid="stImage"] {
                margin-top: 0 !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Full-width logo, no "Navigation" heading anymore
    st.image(LOGO_PATH, use_container_width=True)

# Initialize session state for page selection
if "selected_page" not in st.session_state:
    st.session_state.selected_page = "Daphnia Code Generator"
    st.session_state.selected_species = "daphnia"

# ---- Daphnia section ----
st.sidebar.markdown("### Daphnia magna")
for page_name in DAPHNIA_PAGES.keys():
    if st.sidebar.button(
        page_name,
        key=f"daphnia_{page_name}",
        use_container_width=True,
        type="primary" if (
            st.session_state.selected_species == "daphnia"
            and st.session_state.selected_page == page_name
        ) else "secondary"
    ):
        st.session_state.selected_species = "daphnia"
        st.session_state.selected_page = page_name
        st.rerun()

# ---- Commented Moina section ----
# st.sidebar.markdown("---")
# st.sidebar.markdown("### Moina")
# for page_name in MOINA_PAGES.keys():
#     if st.sidebar.button(
#         page_name,
#         key=f"moina_{page_name}",
#         use_container_width=True,
#         type="primary" if (
#             st.session_state.selected_species == "moina"
#             and st.session_state.selected_page == page_name
#         ) else "secondary"
#     ):
#         st.session_state.selected_species = "moina"
#         st.session_state.selected_page = page_name
#         st.rerun()

# ---- Render selected page ----
if st.session_state.selected_species == "daphnia":
    DAPHNIA_PAGES[st.session_state.selected_page].render()
# else:
#     MOINA_PAGES[st.session_state.selected_page].render()
