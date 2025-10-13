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

        for option in workflow_options:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(option)
            with col2:
                st.toggle("Enable", key=option)
        
        st.markdown("---")
        
        if st.button("Save Automation Settings"):
            st.success("✅ Automation settings saved successfully!")

    with tab3:
        st.subheader("Generate Reports")
        
        col1, col2 = st.columns(2)
        
        with col1:
            report_type = st.selectbox(
                "Report Type",
                ["Executive Summary", "Detailed Project Report", "Resource Utilization", 
                 "Financial Overview", "Risk Assessment"]
            )
            
            time_period = st.selectbox("Time Period", ["Last Week", "Last Month", "Last Quarter", "YTD"])
        
        with col2:
            format_type = st.selectbox("Format", ["PDF", "Excel", "PowerPoint", "HTML"])
            
            include_charts = st.checkbox("Include Charts & Visualizations", value=True)
        
        if st.button("📄 Generate Report"):
            with st.spinner("Generating report..."):
                st.success("✅ Report generated successfully!")
                st.download_button(
                    label="📥 Download Report",
                    data="Sample report content",
                    file_name=f"{report_type.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )

if __name__ == "__main__":
    main()