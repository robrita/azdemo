# pages/0_Dashboard_Overview.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os
sys.path.append('..')
from utils import render_sidebar

def main():
    # Setup page configuration, apply custom CSS, and render sidebar
    render_sidebar()

    st.header("🏠 Dashboard Overview")

    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="Active Projects", value="24", delta="3")

    with col2:
        st.metric(label="Team Members", value="156", delta="12")

    with col3:
        st.metric(label="Completion Rate", value="87%", delta="5%")

    with col4:
        st.metric(label="On-Time Delivery", value="92%", delta="3%")

    st.markdown("---")

    # Charts Row
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Project Status Distribution")
        # Sample data for pie chart
        status_data = pd.DataFrame({
            'Status': ['In Progress', 'Completed', 'Planning', 'On Hold'],
            'Count': [12, 8, 3, 1]
        })
        fig = px.pie(status_data, values='Count', names='Status', 
                     color_discrete_sequence=['#3B82F6', '#10B981', '#F59E0B', '#EF4444'])
        st.plotly_chart(fig, width='stretch')

    with col2:
        st.subheader("Monthly Project Trends")
        # Sample data for line chart
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
        trend_data = pd.DataFrame({
            'Month': months,
            'Projects Started': [5, 7, 4, 8, 6, 9],
            'Projects Completed': [3, 5, 6, 4, 7, 8]
        })
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=trend_data['Month'], y=trend_data['Projects Started'], 
                                mode='lines+markers', name='Started', line=dict(color='#3B82F6')))
        fig.add_trace(go.Scatter(x=trend_data['Month'], y=trend_data['Projects Completed'], 
                                mode='lines+markers', name='Completed', line=dict(color='#10B981')))
        fig.update_layout(hovermode='x unified')
        st.plotly_chart(fig, width='stretch')

    st.markdown("---")

    # Recent Activities
    st.subheader("Recent Project Activities")
    activities_data = pd.DataFrame({
        'Date': ['2024-06-15', '2024-06-14', '2024-06-13', '2024-06-12'],
        'Project': ['Alpha Initiative', 'Beta Transformation', 'Gamma Optimization', 'Alpha Initiative'],
        'Activity': ['Sprint Review Completed', 'Risk Assessment Updated', 'Deployment Successful', 'New Team Member Added'],
        'Status': ['✅ Completed', '⚠️ Review Needed', '✅ Completed', '✅ Completed']
    })

    st.dataframe(activities_data, width='stretch', hide_index=True)

if __name__ == "__main__":
    main()