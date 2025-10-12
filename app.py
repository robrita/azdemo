import streamlit as st
from dotenv import load_dotenv
from utils import render_sidebar

# Load environment variables
load_dotenv()

def main():
    # Render shared sidebar navigation
    render_sidebar()

    # Loading the CSS
    with open('style.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

    st.title("🚀 PMO Agent Dashboard")
    st.markdown("Welcome to the PMO Agent Dashboard - your comprehensive project management operations tool.")

    # Main Container
    container = st.container()
    container.empty()
    
    # First row of navigation buttons
    st.markdown("### Core Tools")
    col1, col2, col3, col4, col5 = st.columns(5, gap = 'large')

    with col1.container(key = 'container0'):
        img = "https://cdn-icons-png.flaticon.com/512/1055/1055646.png"
        st.markdown(f"""<div style="text-align: center;"><img src="{img}" width="125" style="border-radius: 5px;" /><br><br></div>""",unsafe_allow_html=True)
        st.empty()
        if st.button("Dashboard Overview", width='stretch'):
            st.switch_page("pages/0_Dashboard_Overview.py")

    with col2.container(key = 'container1'):
        img = "https://cdn-icons-png.flaticon.com/512/7277/7277044.png"
        st.markdown(f"""<div style="text-align: center;"><img src="{img}" width="125" style="border-radius: 5px;" /><br><br></div>""",unsafe_allow_html=True)
        st.empty()
        if st.button("Employee Skills Generator", width='stretch'):
            st.switch_page("pages/1_Employee_Skills_Generator.py")

    with col3.container(key = 'container2'):
        img = "https://cdn-icons-png.freepik.com/512/8366/8366999.png"
        st.markdown(f"""<div style="text-align: center;"><img src="{img}" width="125" style="border-radius: 5px;" /><br><br></div>""",unsafe_allow_html=True)
        if st.button("Scoping Document Evaluator", width='stretch'):
            st.switch_page("pages/2_Project_Scoping_Document_Evaluator.py")

    with col4.container(key = 'container3'):
        img = "https://cdn-icons-png.flaticon.com/512/5656/5656665.png"
        st.markdown(f"""<div style="text-align: center;"><img src="{img}" width="125" style="border-radius: 5px;" /><br><br></div>""",unsafe_allow_html=True)
        if st.button("Project Timeline Monitor", width='stretch'):
            st.switch_page("pages/3_Project_Timeline_Monitor.py")

    with col5.container(key = 'container4'):
        img = "https://cdn-icons-png.freepik.com/256/13558/13558989.png"
        st.markdown(f"""<div style="text-align: center;"><img src="{img}" width="125" style="border-radius: 5px;" /><br><br></div>""",unsafe_allow_html=True)
        if st.button("Unstructured Document Parser", width='stretch'):
            st.switch_page("pages/4_Unstructured_Document_Parser.py")

    # Second row of navigation buttons  
    st.markdown("### Advanced Analytics")
    col6, col7, col8, col9 = st.columns(4, gap = 'large')

    with col6.container(key = 'container5'):
        img = "https://cdn-icons-png.flaticon.com/512/2936/2936719.png"
        st.markdown(f"""<div style="text-align: center;"><img src="{img}" width="125" style="border-radius: 5px;" /><br><br></div>""",unsafe_allow_html=True)
        if st.button("Skills Management", width='stretch'):
            st.switch_page("pages/5_Skills_Management.py")

    with col7.container(key = 'container6'):
        img = "https://cdn-icons-png.flaticon.com/512/3659/3659898.png"
        st.markdown(f"""<div style="text-align: center;"><img src="{img}" width="125" style="border-radius: 5px;" /><br><br></div>""",unsafe_allow_html=True)
        if st.button("Document Analysis", width='stretch'):
            st.switch_page("pages/6_Document_Analysis.py")

    with col8.container(key = 'container7'):
        img = "https://cdn-icons-png.flaticon.com/512/3281/3281289.png"
        st.markdown(f"""<div style="text-align: center;"><img src="{img}" width="125" style="border-radius: 5px;" /><br><br></div>""",unsafe_allow_html=True)
        if st.button("Project Monitoring", width='stretch'):
            st.switch_page("pages/7_Project_Monitoring.py")

    with col9.container(key = 'container8'):
        img = "https://cdn-icons-png.flaticon.com/512/1006/1006555.png"
        st.markdown(f"""<div style="text-align: center;"><img src="{img}" width="125" style="border-radius: 5px;" /><br><br></div>""",unsafe_allow_html=True)
        if st.button("PMO Operations", width='stretch'):
            st.switch_page("pages/8_PMO_Operations.py")

if __name__ == "__main__":
    main()