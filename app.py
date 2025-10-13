import streamlit as st
from dotenv import load_dotenv
from utils import render_sidebar

# Load environment variables
load_dotenv()

def main():
    # Render shared sidebar navigation
    render_sidebar()

    st.title("🚀 PMO Agent Dashboard")
    st.markdown("Welcome to the PMO Agent Dashboard - your comprehensive project management operations tool.")

    # Main Container
    container = st.container()
    container.empty()
    
    # Navigation buttons
    st.markdown("### Available Tools")
    
    # First row: 4 columns
    col1, col2, col3, col4 = st.columns(4, gap = 'medium')

    with col1.container(key = 'container0'):
        img = "https://cdn-icons-png.flaticon.com/512/1055/1055646.png"
        st.markdown(f"""<div style="text-align: center;"><img src="{img}" width="125" style="border-radius: 12px;" /><br><br></div>""",unsafe_allow_html=True)
        st.empty()
        if st.button("Dashboard Overview", width='stretch'):
            st.switch_page("pages/1_Dashboard_Overview.py")

    with col2.container(key = 'container5'):
        img = "https://cdn-icons-png.flaticon.com/512/2936/2936719.png"
        st.markdown(f"""<div style="text-align: center;"><img src="{img}" width="125" style="border-radius: 12px;" /><br><br></div>""",unsafe_allow_html=True)
        if st.button("Skills Management", width='stretch'):
            st.switch_page("pages/2_Skills_Management.py")

    with col3.container(key = 'container6'):
        img = "https://cdn-icons-png.flaticon.com/512/3659/3659898.png"
        st.markdown(f"""<div style="text-align: center;"><img src="{img}" width="125" style="border-radius: 12px;" /><br><br></div>""",unsafe_allow_html=True)
        if st.button("Document Analysis", width='stretch'):
            st.switch_page("pages/3_Document_Analysis.py")

    with col4.container(key = 'container7'):
        img = "https://cdn-icons-png.flaticon.com/512/3281/3281289.png"
        st.markdown(f"""<div style="text-align: center;"><img src="{img}" width="125" style="border-radius: 12px;" /><br><br></div>""",unsafe_allow_html=True)
        if st.button("Project Monitoring", width='stretch'):
            st.switch_page("pages/4_Project_Monitoring.py")

    # Second row: 1 column (centered)
    col5_container = st.container()
    col5_left, col5, col5_right = st.columns([1.5, 1, 1.5], gap = 'medium')

    with col5.container(key = 'container8'):
        img = "https://cdn-icons-png.flaticon.com/512/1006/1006555.png"
        st.markdown(f"""<div style="text-align: center;"><img src="{img}" width="125" style="border-radius: 12px;" /><br><br></div>""",unsafe_allow_html=True)
        if st.button("PMO Operations", width='stretch'):
            st.switch_page("pages/5_PMO_Operations.py")

if __name__ == "__main__":
    main()