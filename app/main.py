import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import os
import streamlit as st
from app.core import utils
from app.ui import coder_page

# ========= BRANDING: page config =========
APP_DIR = os.path.dirname(__file__)
ICON_PATH = os.path.join(APP_DIR, "assets", "daphnia.svg")
LOGO_PATH = os.path.join(APP_DIR, "assets", "marine_ugent.png")

st.set_page_config(
    page_title="Daphnia Coding Protocol",
    page_icon=ICON_PATH,
    layout="wide",
)

# ========= Background =========
utils.set_faded_bg_from_svg(
    ICON_PATH, overlay_alpha=0.90, img_width="48vw", img_position="center 6%"
)

# ========= Router =========
PAGES = {
    "Code Generator": coder_page,
}
st.sidebar.image(LOGO_PATH, use_container_width=True)
st.sidebar.title("Navigation")
selection = st.sidebar.radio("Go to:", list(PAGES.keys()))
page = PAGES[selection]
page.render()
