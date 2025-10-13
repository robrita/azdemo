# pages/6_Document_Analysis.py
import streamlit as st
import pandas as pd
import sys
import os
sys.path.append('..')
from utils import render_sidebar

def main():
    # Setup page configuration, apply custom CSS, and render sidebar
    render_sidebar()

    st.header("📄 Document Analysis")

    tab1, tab2 = st.tabs(["📤 Upload & Analyze", "📚 Document Repository"])

    with tab1:
        st.subheader("Upload Document for AI Analysis")
        
        uploaded_file = st.file_uploader("Choose a file", type=['pdf', 'docx', 'txt', 'csv', 'xlsx'])
        
        col1, col2 = st.columns(2)
        
        with col1:
            analysis_type = st.selectbox(
                "Analysis Type",
                ["Summary Generation", "Key Points Extraction", "Risk Identification", 
                 "Action Items", "Compliance Check"]
            )
        
        with col2:
            output_format = st.selectbox("Output Format", ["Detailed Report", "Executive Summary", "Bullet Points"])
        
        if uploaded_file is not None:
            st.success(f"✅ File '{uploaded_file.name}' uploaded successfully!")
            
            if st.button("🔍 Analyze Document"):
                with st.spinner("AI is analyzing the document..."):
                    st.info("Analysis in progress...")
                    
                    # Simulated analysis results
                    st.markdown("### Analysis Results")
                    
                    st.markdown("**📋 Summary:**")
                    st.write("""
                    The document outlines the project scope, timeline, and resource allocation 
                    for the Q4 2024 digital transformation initiative. Key stakeholders have 
                    been identified, and the budget has been approved at $2.5M.
                    """)
                    
                    st.markdown("**🎯 Key Points:**")
                    st.markdown("""
                    - Project duration: 6 months
                    - Budget: $2.5M
                    - Team size: 15 members
                    - Primary technology stack: Cloud-native architecture
                    - Expected ROI: 35% within 12 months
                    """)
                    
                    st.markdown("**⚠️ Identified Risks:**")
                    risk_df = pd.DataFrame({
                        'Risk': ['Resource availability', 'Technical complexity', 'Timeline constraints'],
                        'Severity': ['High', 'Medium', 'Medium'],
                    })
                    st.dataframe(risk_df, width='stretch', hide_index=True)

    with tab2:
        st.subheader("Document Repository")
        
        # Sample document repository
        docs_data = pd.DataFrame({
            'Document Name': [
                'Q4 Project Plan.pdf',
                'Risk Assessment Report.docx',
                'Budget Proposal.xlsx',
                'Technical Specification.pdf',
                'Stakeholder Analysis.pptx'
            ],
            'Type': ['Project Plan', 'Risk Report', 'Financial', 'Technical', 'Analysis'],
            'Upload Date': pd.date_range(start='2024-01-01', periods=5, freq='W'),
            'Status': ['Analyzed', 'Analyzed', 'Pending', 'Analyzed', 'In Progress'],
            'Size': ['2.3 MB', '1.5 MB', '890 KB', '4.2 MB', '3.1 MB']
        })
        
        st.dataframe(docs_data, width='stretch', hide_index=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Documents", "47")
        with col2:
            st.metric("Analyzed", "35")
        with col3:
            st.metric("Pending", "12")

if __name__ == "__main__":
    main()