# pages/3_Project_Timeline_Monitor.py
import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import numpy as np
sys.path.append('..')
from utils import render_sidebar, keep_state

class ProjectTimelineMonitor:
    def __init__(self):
        self.projects_data = {}
        
    def load_project_file(self, file, project_name):
        """Load and process project data from CSV/Excel file"""
        try:
            # Read file based on extension
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file)
            else:
                st.error("Unsupported file format. Please upload CSV or Excel files.")
                return None
                
            # Validate required columns
            required_columns = ['TaskID', 'TaskName', 'PlannedStart', 'PlannedEnd', 'ActualStart', 'ActualEnd']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                st.error(f"Missing required columns: {', '.join(missing_columns)}")
                return None
            
            # Convert date columns to datetime
            date_columns = ['PlannedStart', 'PlannedEnd', 'ActualStart', 'ActualEnd']
            for col in date_columns:
                df[col] = pd.to_datetime(df[col])
            
            # Calculate durations and deviations
            df['PlannedDuration'] = (df['PlannedEnd'] - df['PlannedStart']).dt.days + 1
            df['ActualDuration'] = (df['ActualEnd'] - df['ActualStart']).dt.days + 1
            df['Deviation'] = df['ActualDuration'] - df['PlannedDuration']
            df['Project'] = project_name
            
            # Store the processed data
            self.projects_data[project_name] = df
            
            return df
            
        except Exception as e:
            st.error(f"Error processing file {file.name}: {str(e)}")
            return None
    
    def create_gantt_chart(self, selected_projects):
        """Create Gantt chart with baseline overlay"""
        if not selected_projects:
            return None
            
        # Combine data from selected projects
        combined_data = []
        for project in selected_projects:
            if project in self.projects_data:
                df = self.projects_data[project].copy()
                combined_data.append(df)
        
        if not combined_data:
            return None
            
        all_data = pd.concat(combined_data, ignore_index=True)
        
        # Create subplot
        fig = go.Figure()
        
        # Color mapping for projects
        colors = px.colors.qualitative.Set3
        project_colors = {project: colors[i % len(colors)] for i, project in enumerate(selected_projects)}
        
        # Add planned bars (baseline)
        for _, row in all_data.iterrows():
            fig.add_trace(go.Bar(
                name=f"{row['Project']} - Planned",
                x=[row['PlannedDuration']],
                y=[f"{row['TaskName']} ({row['Project']})"],
                base=[row['PlannedStart']],
                orientation='h',
                marker=dict(
                    color=project_colors[row['Project']],
                    opacity=0.3,
                    line=dict(color='black', width=1)
                ),
                showlegend=True if _ == 0 else False,
                legendgroup=f"{row['Project']}-planned",
                hovertemplate=f"<b>{row['TaskName']}</b><br>" +
                            f"Project: {row['Project']}<br>" +
                            f"Planned: {row['PlannedStart'].strftime('%Y-%m-%d')} to {row['PlannedEnd'].strftime('%Y-%m-%d')}<br>" +
                            f"Duration: {row['PlannedDuration']} days<extra></extra>"
            ))
        
        # Add actual bars
        for _, row in all_data.iterrows():
            fig.add_trace(go.Bar(
                name=f"{row['Project']} - Actual",
                x=[row['ActualDuration']],
                y=[f"{row['TaskName']} ({row['Project']})"],
                base=[row['ActualStart']],
                orientation='h',
                marker=dict(
                    color=project_colors[row['Project']],
                    opacity=0.8
                ),
                showlegend=True if _ == 0 else False,
                legendgroup=f"{row['Project']}-actual",
                hovertemplate=f"<b>{row['TaskName']}</b><br>" +
                            f"Project: {row['Project']}<br>" +
                            f"Actual: {row['ActualStart'].strftime('%Y-%m-%d')} to {row['ActualEnd'].strftime('%Y-%m-%d')}<br>" +
                            f"Duration: {row['ActualDuration']} days<br>" +
                            f"Deviation: {row['Deviation']:+d} days<extra></extra>"
            ))
        
        fig.update_layout(
            title="Project Timeline - Gantt Chart with Baseline Overlay",
            xaxis_title="Timeline",
            yaxis_title="Tasks",
            barmode='overlay',
            height=max(400, len(all_data) * 30),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig
    
    def create_deviation_chart(self, selected_projects):
        """Create timeline deviation chart"""
        if not selected_projects:
            return None
            
        # Combine data from selected projects
        combined_data = []
        for project in selected_projects:
            if project in self.projects_data:
                df = self.projects_data[project].copy()
                combined_data.append(df)
        
        if not combined_data:
            return None
            
        all_data = pd.concat(combined_data, ignore_index=True)
        
        # Create bar chart for deviations
        fig = go.Figure()
        
        # Color bars based on deviation (red for delays, green for early completion)
        colors = ['red' if x > 0 else 'green' if x < 0 else 'gray' for x in all_data['Deviation']]
        
        fig.add_trace(go.Bar(
            x=all_data['Deviation'],
            y=[f"{row['TaskName']} ({row['Project']})" for _, row in all_data.iterrows()],
            orientation='h',
            marker=dict(color=colors),
            text=[f"{dev:+d}" for dev in all_data['Deviation']],
            textposition='outside',
            hovertemplate="<b>%{y}</b><br>" +
                        "Deviation: %{x} days<br>" +
                        "Planned Duration: %{customdata[0]} days<br>" +
                        "Actual Duration: %{customdata[1]} days<extra></extra>",
            customdata=list(zip(all_data['PlannedDuration'], all_data['ActualDuration']))
        ))
        
        # Add vertical line at x=0
        fig.add_vline(x=0, line_dash="dash", line_color="black", opacity=0.5)
        
        fig.update_layout(
            title="Timeline Deviation Analysis",
            xaxis_title="Deviation (days)",
            yaxis_title="Tasks",
            height=max(400, len(all_data) * 30),
            annotations=[
                dict(
                    x=0.02, y=0.98,
                    xref="paper", yref="paper",
                    text="🔴 Red: Delayed | 🟢 Green: Early | ⚫ Gray: On Time",
                    showarrow=False,
                    font=dict(size=10),
                    bgcolor="white",
                    bordercolor="black",
                    borderwidth=1
                )
            ]
        )
        
        return fig
    
    def get_project_summary(self, project_name):
        """Get summary statistics for a project"""
        if project_name not in self.projects_data:
            return None
            
        df = self.projects_data[project_name]
        
        total_tasks = len(df)
        delayed_tasks = len(df[df['Deviation'] > 0])
        early_tasks = len(df[df['Deviation'] < 0])
        on_time_tasks = len(df[df['Deviation'] == 0])
        
        avg_deviation = df['Deviation'].mean()
        total_story_points = df['StoryPoints'].sum() if 'StoryPoints' in df.columns else 0
        
        return {
            'total_tasks': total_tasks,
            'delayed_tasks': delayed_tasks,
            'early_tasks': early_tasks,
            'on_time_tasks': on_time_tasks,
            'avg_deviation': avg_deviation,
            'total_story_points': total_story_points
        }

def main():
    # Render shared sidebar navigation
    render_sidebar()
    
    st.title("⏱️ Project Timeline Monitor")
    st.markdown("Monitor project timelines, track deviations, and visualize progress with Gantt charts and deviation analysis.")
    
    # Initialize monitor
    monitor = ProjectTimelineMonitor()
    
    # Initialize session state for projects
    if 'uploaded_projects' not in st.session_state:
        st.session_state.uploaded_projects = {}
    
    container1 = st.container(border=True, key="upload_container")
    
    # File upload section
    container1.subheader("📁 Upload Project Data")
    
    uploaded_files = container1.file_uploader(
        "Upload Project Timeline Data (CSV/Excel)",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        key="project_files",
        help="Upload CSV or Excel files containing project timeline data"
    )
    
    # Process uploaded files
    if uploaded_files:
        for file in uploaded_files:
            # Use filename (without extension) as project name
            project_name = file.name.rsplit('.', 1)[0]
            
            if project_name not in st.session_state.uploaded_projects:
                df = monitor.load_project_file(file, project_name)
                if df is not None:
                    st.session_state.uploaded_projects[project_name] = df
                    container1.success(f"✅ Loaded project: {project_name}")
    
    # Load existing projects into monitor
    for project_name, df in st.session_state.uploaded_projects.items():
        monitor.projects_data[project_name] = df
    
    # Show example or help
    with container1.expander("ℹ️ How this tool works?"):
        st.markdown("""
        ### How to Use the Timeline Monitor:
        
        1. **Upload Project Data**: Upload CSV or Excel files containing project timeline data
        2. **Select Projects**: Choose which projects to analyze in the charts
        3. **Click 'Show Charts'**: Generate Gantt chart and deviation analysis
        
        ### Required Data Format:
        Your files should contain these columns:
        - `TaskID`: Unique identifier for each task
        - `TaskName`: Name/description of the task
        - `PlannedStart`: Planned start date (YYYY-MM-DD)
        - `PlannedEnd`: Planned end date (YYYY-MM-DD)
        - `ActualStart`: Actual start date (YYYY-MM-DD)
        - `ActualEnd`: Actual end date (YYYY-MM-DD)
        - `StoryPoints`: (Optional) Story points for the task
        - `Sprint`: (Optional) Sprint number
        
        ### What You'll Get:
        - **Gantt Chart**: Visual timeline with planned vs actual dates
        - **Deviation Analysis**: Chart showing task delays and early completions
        - **Project Statistics**: Summary metrics for each project
        """)
    
    # Project selection and analysis
    if st.session_state.uploaded_projects:
        st.subheader("📊 Project Analysis")
        
        # Project selection
        available_projects = list(st.session_state.uploaded_projects.keys())
        selected_projects = st.multiselect(
            "Select Projects to Analyze",
            available_projects,
            default=available_projects,
            help="Choose one or more projects to include in the charts"
        )
        
        # Show project summaries
        if selected_projects:
            st.subheader("📈 Project Statistics")
            cols = st.columns(len(selected_projects))
            
            for i, project in enumerate(selected_projects):
                with cols[i]:
                    summary = monitor.get_project_summary(project)
                    if summary:
                        st.metric(f"**{project}**", "")
                        st.write(f"📋 Total Tasks: {summary['total_tasks']}")
                        st.write(f"🔴 Delayed: {summary['delayed_tasks']}")
                        st.write(f"🟢 Early: {summary['early_tasks']}")
                        st.write(f"⚫ On Time: {summary['on_time_tasks']}")
                        st.write(f"📊 Avg Deviation: {summary['avg_deviation']:.1f} days")
                        if summary['total_story_points'] > 0:
                            st.write(f"⭐ Story Points: {summary['total_story_points']}")
        
        # Chart generation
        if st.button("📊 Show Charts", type="primary", disabled=not selected_projects):
            with st.spinner("Generating charts..."):
                # Create Gantt chart
                gantt_fig = monitor.create_gantt_chart(selected_projects)
                if gantt_fig:
                    st.plotly_chart(gantt_fig, width='stretch')
                
                # Create deviation chart
                deviation_fig = monitor.create_deviation_chart(selected_projects)
                if deviation_fig:
                    st.plotly_chart(deviation_fig, width='stretch')
                
                st.success("✅ Charts generated successfully!")
        
        # Data preview section
        if selected_projects:
            st.subheader("📋 Data Preview")
            
            for project in selected_projects:
                with st.expander(f"View data for {project}"):
                    df = st.session_state.uploaded_projects[project]
                    
                    # Display summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Tasks", len(df))
                    with col2:
                        avg_planned = df['PlannedDuration'].mean()
                        st.metric("Avg Planned Duration", f"{avg_planned:.1f} days")
                    with col3:
                        avg_actual = df['ActualDuration'].mean()
                        st.metric("Avg Actual Duration", f"{avg_actual:.1f} days")
                    with col4:
                        avg_dev = df['Deviation'].mean()
                        st.metric("Avg Deviation", f"{avg_dev:+.1f} days")
                    
                    # Display data table
                    display_columns = ['TaskID', 'TaskName', 'PlannedStart', 'PlannedEnd', 
                                     'ActualStart', 'ActualEnd', 'PlannedDuration', 
                                     'ActualDuration', 'Deviation']
                    
                    if 'StoryPoints' in df.columns:
                        display_columns.insert(-3, 'StoryPoints')
                    
                    st.dataframe(
                        df[display_columns],
                        width='stretch',
                        hide_index=True
                    )
    
    else:
        st.info("👆 Upload project timeline data files to get started!")

if __name__ == "__main__":
    main()
