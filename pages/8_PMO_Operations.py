# pages/8_PMO_Operations.py
import streamlit as st
import pandas as pd
import sys
import os
sys.path.append('..')
from utils import render_sidebar

def main():
    # Setup page configuration, apply custom CSS, and render sidebar
    render_sidebar()

    st.header("🔧 PMO Operations")

    tab1, tab2, tab3 = st.tabs(["🎯 Resource Allocation", "📋 Workflow Automation", "📊 Reports"])

    with tab1:
        st.subheader("Resource Allocation Management")
        
        # Resource allocation matrix
        resources_data = pd.DataFrame({
            'Resource': ['John Doe', 'Jane Smith', 'Bob Johnson', 'Alice Williams', 'Charlie Brown'],
            'Role': ['Senior Developer', 'Project Manager', 'DevOps Engineer', 'Data Analyst', 'UX Designer'],
            'Current Project': ['Alpha', 'Beta', 'Alpha', 'Gamma', 'Delta'],
            'Utilization': ['85%', '90%', '75%', '95%', '70%'],
            'Availability': ['15%', '10%', '25%', '5%', '30%']
        })
        
        st.dataframe(resources_data, width='stretch', hide_index=True)
        
        st.markdown("### Allocation Optimizer")
        col1, col2 = st.columns(2)
        
        with col1:
            st.selectbox("Select Project", ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"])
            st.multiselect("Required Skills", ["Python", "JavaScript", "Cloud", "Data Analysis", "Design"])
        
        with col2:
            st.number_input("Team Size Needed", min_value=1, max_value=20)
            st.date_input("Start Date")
        
        if st.button("🤖 AI-Powered Allocation Suggestion"):
            st.success("✨ AI has identified optimal resource allocation!")
            st.info("""
            **Recommended Team:**
            - Lead: Jane Smith (10% availability from Beta project)
            - Developer: Bob Johnson (25% available)
            - Designer: Charlie Brown (30% available)
            
            **Estimated Delivery:** 12 weeks with current allocation
            """)

    with tab2:
        st.subheader("Workflow Automation")
        
        st.markdown("""
        Configure automated workflows for common PMO tasks:
        """)
        
        workflow_options = [
            "📧 Automated Status Reports",
            "⚠️ Risk Alert Notifications",
            "📅 Meeting Scheduler",
            "🔄 Task Assignment Automation",
            "📊 Dashboard Updates"
        ]
        selected_workflows = st.multiselect("Select Workflows to Automate", workflow_options)
        if st.button("Enable Automation"):
            st.success("✅ Selected workflows have been automated!")

    with tab3:
        st.subheader("Reports")
        st.info("Reports feature coming soon!")

if __name__ == "__main__":
    main()