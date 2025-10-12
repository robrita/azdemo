# pages/7_Project_Monitoring.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
sys.path.append('..')
from utils import render_sidebar

def main():
    # Setup page configuration, apply custom CSS, and render sidebar
    render_sidebar()

    st.header("📊 Project Monitoring")

    tab1, tab2, tab3 = st.tabs(["📈 Project Dashboard", "⏰ Timeline", "💰 Budget Tracking"])

    with tab1:
        st.subheader("Active Projects Overview")
        
        # Sample project data
        projects_data = pd.DataFrame({
            'Project': ['Alpha Initiative', 'Beta Transformation', 'Gamma Optimization', 
                       'Delta Migration', 'Epsilon Enhancement'],
            'Status': ['On Track', 'At Risk', 'On Track', 'Delayed', 'On Track'],
            'Progress': [75, 45, 90, 30, 60],
            'Budget Used': ['$1.2M', '$800K', '$2.1M', '$500K', '$1.5M'],
            'Team Size': [12, 8, 15, 6, 10]
        })
        
        # Progress visualization
        fig = go.Figure()
        colors = ['#10B981', '#F59E0B', '#10B981', '#EF4444', '#10B981']
        
        fig.add_trace(go.Bar(
            x=projects_data['Project'],
            y=projects_data['Progress'],
            marker_color=colors,
            text=projects_data['Progress'].apply(lambda x: f"{x}%"),
            textposition='auto'
        ))
        
        fig.update_layout(
            title='Project Progress',
            yaxis_title='Completion %',
            showlegend=False
        )
        
        st.plotly_chart(fig, width='stretch')
        
        st.dataframe(projects_data, width='stretch', hide_index=True)

    with tab2:
        st.subheader("Project Timeline")
        
        # Gantt chart simulation
        timeline_data = pd.DataFrame({
            'Task': ['Planning', 'Design', 'Development', 'Testing', 'Deployment'],
            'Start': ['2024-01-01', '2024-02-01', '2024-03-15', '2024-05-01', '2024-06-01'],
            'End': ['2024-01-31', '2024-03-14', '2024-04-30', '2024-05-31', '2024-06-15'],
            'Status': ['Completed', 'Completed', 'In Progress', 'Not Started', 'Not Started']
        })
        st.dataframe(timeline_data, width='stretch', hide_index=True)

    with tab3:
        st.subheader("Budget Tracking")
        st.info("Budget tracking feature coming soon!")

if __name__ == "__main__":
    main()