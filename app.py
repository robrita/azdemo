import streamlit as st
from dotenv import load_dotenv
from utils import render_sidebar

# Load environment variables
load_dotenv()

def main():
    # Render shared sidebar navigation
    render_sidebar()

    st.title("🚀 Document Processing Dashboard")
    st.markdown("Welcome to the Document Processing Dashboard - your comprehensive document extraction and analysis tool.")

    # Main Container
    container = st.container()
    container.empty()
    
    # Navigation buttons
    st.markdown("### Available Tools")
    
    # Single centered column for Document Extraction
    col1, col2, col3 = st.columns([1, 2, 1], gap='medium')

    with col2.container(key='container0'):
        img = "https://images.icon-icons.com/2331/PNG/512/documentation_folder_document_management_files_file_project_icon_142253.png"
        st.markdown(f"""<div style="text-align: center;"><img src="{img}" width="125" style="border-radius: 12px;" /><br><br></div>""", unsafe_allow_html=True)
        if st.button("Document Extraction", width='stretch'):
            st.switch_page("pages/1_Document_Extraction.py")

if __name__ == "__main__":
    main()