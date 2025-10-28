"""
Monthly Reports landing page - directs to specific months
"""

import streamlit as st

st.title("📅 Monthly Reports")

st.markdown("""
### Available Reports

Select a month from the sidebar to view detailed analysis.

Currently available:
- **September 2025** - Complete monthly analysis including demographics, mortality, reproduction, and survival metrics

### Coming Soon

Future updates will include:
- **General Comparisons**: Compare metrics across multiple months
- **Trend Analysis**: Visualize population trends over time
- **Cross-Month Statistics**: Identify long-term patterns and changes
""")

st.divider()

st.info("👈 Select **September 2025** from the sidebar to view the detailed monthly report")
