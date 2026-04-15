"""
OxData — Entry point.
Defines navigation and global page config.
All page logic lives in views/chat.py and views/schema.py.
"""

import streamlit as st

st.set_page_config(
    page_title="OxData",
    page_icon="📊",
    layout="wide",
)

pg = st.navigation(
    {
        "Analytics": [
            st.Page("views/chat.py",   title="Chat",            icon="💬", default=True),
            st.Page("views/schema.py", title="Schema Explorer", icon="🗂️"),
        ],
        "Help": [
            st.Page("views/api_guide.py", title="API Key Guide", icon="🔑"),
        ],
    }
)

pg.run()
