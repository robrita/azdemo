# pages/5_Skills_Management.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import sys
import os
sys.path.append('..')
from utils import render_sidebar

def main():
    # Setup page configuration, apply custom CSS, and render sidebar
    render_sidebar()

    st.header("👥 Skills Management")

    tab1, tab2, tab3 = st.tabs(["📊 Skills Overview", "➕ Add Skills", "🔍 Gap Analysis"])

    with tab1:
        st.subheader("Team Skills Distribution")
        
        # Sample skills data
        skills_data = pd.DataFrame({
            'Skill': ['Python', 'JavaScript', 'Project Management', 'Data Analysis', 
                     'Cloud Architecture', 'DevOps', 'UI/UX Design', 'Agile/Scrum'],
            'Expert': [15, 12, 20, 18, 10, 8, 6, 22],
            'Intermediate': [25, 30, 15, 20, 15, 18, 12, 18],
            'Beginner': [10, 8, 5, 12, 15, 14, 22, 10]
        })
        
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Expert', x=skills_data['Skill'], y=skills_data['Expert'], 
                            marker_color='#10B981'))
        fig.add_trace(go.Bar(name='Intermediate', x=skills_data['Skill'], y=skills_data['Intermediate'], 
                            marker_color='#3B82F6'))
        fig.add_trace(go.Bar(name='Beginner', x=skills_data['Skill'], y=skills_data['Beginner'], 
                            marker_color='#F59E0B'))
        
        fig.update_layout(barmode='stack', xaxis_tickangle=-45)
        st.plotly_chart(fig, width='stretch')
        
        st.dataframe(skills_data, width='stretch', hide_index=True)

    with tab2:
        st.subheader("Add New Skills")
        
        col1, col2 = st.columns(2)
        
        with col1:
            employee_name = st.text_input("Employee Name")
            skill_name = st.text_input("Skill Name")
            proficiency = st.selectbox("Proficiency Level", ["Beginner", "Intermediate", "Expert"])
        
        with col2:
            years_experience = st.number_input("Years of Experience", min_value=0, max_value=50)
            certification = st.text_input("Certification (if any)")
            last_used = st.date_input("Last Used")
        
        if st.button("Add Skill"):
            st.success(f"✅ Successfully added {skill_name} for {employee_name}")

    with tab3:
        st.subheader("Skills Gap Analysis")
        
        st.markdown("""
        The AI-powered skills gap analysis identifies missing competencies and 
        recommends training programs to bridge the gaps.
        """)
        
        # Sample gap analysis
        gap_data = pd.DataFrame({
            'Required Skill': ['Advanced Python', 'Kubernetes', 'Machine Learning', 'Security Best Practices'],
            'Current Level': ['Intermediate', 'Beginner', 'Beginner', 'Intermediate'],
            'Target Level': ['Expert', 'Expert', 'Intermediate', 'Expert'],
            'Gap': ['High', 'Critical', 'Medium', 'Medium'],
            'Recommended Action': [
                'Advanced Python training course',
                'Kubernetes certification program',
                'ML fundamentals workshop',
                'Security certification'
            ]
        })
        
        st.dataframe(gap_data, width='stretch', hide_index=True)
        
        if st.button("Generate AI Recommendations"):
            st.info("🤖 AI is analyzing skills gaps and generating personalized training recommendations...")
            st.balloons()

if __name__ == "__main__":
    main()