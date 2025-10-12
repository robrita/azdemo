import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

# Page configuration
st.set_page_config(
    page_title="PMO Agent Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS with Google Fonts
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Gasoek+One&family=Oswald:wght@300;400;500;600;700&display=swap');
    
    /* Global Styles */
    * {
        font-family: 'Oswald', sans-serif;
    }
    
    /* Main Title */
    h1 {
        font-family: 'Gasoek One', sans-serif !important;
        color: #1E3A8A;
        text-align: center;
        padding: 20px 0;
        background: linear-gradient(90deg, #3B82F6 0%, #1E3A8A 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    /* Sidebar */
    .css-1d391kg, [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1E3A8A 0%, #3B82F6 100%);
    }
    
    .css-1d391kg p, [data-testid="stSidebar"] p {
        color: white;
        font-weight: 500;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(90deg, #3B82F6 0%, #1E3A8A 100%);
        color: white;
        border-radius: 10px;
        padding: 10px 25px;
        font-weight: 600;
        border: none;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 20px rgba(59, 130, 246, 0.3);
    }
    
    /* Cards */
    div.stMetric {
        background: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: all 0.3s;
    }
    
    div.stMetric:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.15);
    }
    
    /* Headers */
    h2, h3 {
        font-family: 'Oswald', sans-serif;
        color: #1E3A8A;
        font-weight: 600;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        font-family: 'Oswald', sans-serif;
        font-weight: 600;
        color: #1E3A8A;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-family: 'Oswald', sans-serif;
        font-weight: 600;
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)

# Main Title
st.markdown("<h1>🚀 PMO Agent Dashboard</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #64748B; font-size: 18px; margin-bottom: 30px;'>Comprehensive Project Management Operations Platform</p>", unsafe_allow_html=True)

# Sidebar Navigation
with st.sidebar:
    st.markdown("### 📋 Navigation")
    page = st.radio(
        "Select Module:",
        ["🏠 Dashboard Overview", "👥 Skills Management", "📄 Document Analysis", 
         "📊 Project Monitoring", "🔧 PMO Operations"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.markdown("""
    **PMO Agent Dashboard** is a comprehensive AI-powered platform designed to automate 
    and enhance project management workflows.
    
    **Key Features:**
    - AI-Powered Skills Management
    - Intelligent Document Analysis
    - Real-time Project Monitoring
    - Automated PMO Operations
    """)

# Dashboard Overview
if page == "🏠 Dashboard Overview":
    st.header("Dashboard Overview")
    
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
        st.plotly_chart(fig, use_container_width=True)
    
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
        st.plotly_chart(fig, use_container_width=True)
    
    # Recent Activities
    st.subheader("📌 Recent Activities")
    activities = pd.DataFrame({
        'Timestamp': [datetime.now() - timedelta(hours=i) for i in range(5)],
        'Activity': [
            'Project "Alpha" milestone completed',
            'New team member onboarded',
            'Risk assessment completed for "Beta" project',
            'Document review initiated for "Gamma"',
            'Skills gap analysis finished'
        ],
        'Type': ['Milestone', 'HR', 'Risk', 'Document', 'Skills']
    })
    st.dataframe(activities, use_container_width=True, hide_index=True)

# Skills Management Module
elif page == "👥 Skills Management":
    st.header("Skills Management")
    
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
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(skills_data, use_container_width=True, hide_index=True)
    
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
        
        st.dataframe(gap_data, use_container_width=True, hide_index=True)
        
        if st.button("Generate AI Recommendations"):
            st.info("🤖 AI is analyzing skills gaps and generating personalized training recommendations...")
            st.balloons()

# Document Analysis Module
elif page == "📄 Document Analysis":
    st.header("Document Analysis")
    
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
                        'Mitigation': [
                            'Secure backup resources',
                            'Technical spike planned',
                            'Phased delivery approach'
                        ]
                    })
                    st.dataframe(risk_df, use_container_width=True, hide_index=True)
    
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
        
        st.dataframe(docs_data, use_container_width=True, hide_index=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Documents", "47")
        with col2:
            st.metric("Analyzed", "35")
        with col3:
            st.metric("Pending", "12")

# Project Monitoring Module
elif page == "📊 Project Monitoring":
    st.header("Project Monitoring")
    
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
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(projects_data, use_container_width=True, hide_index=True)
    
    with tab2:
        st.subheader("Project Timeline")
        
        # Gantt chart simulation
        timeline_data = pd.DataFrame({
            'Task': ['Planning', 'Design', 'Development', 'Testing', 'Deployment'],
            'Start': ['2024-01-01', '2024-02-01', '2024-03-15', '2024-05-01', '2024-06-01'],
            'End': ['2024-01-31', '2024-03-14', '2024-04-30', '2024-05-31', '2024-06-15'],
            'Status': ['Completed', 'Completed', 'In Progress', 'Not Started', 'Not Started']
        })
        
        st.dataframe(timeline_data, use_container_width=True, hide_index=True)
        
        st.info("📅 Next Milestone: Development Phase Completion - May 1, 2024")
    
    with tab3:
        st.subheader("Budget Tracking")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Budget pie chart
            budget_data = pd.DataFrame({
                'Category': ['Development', 'Infrastructure', 'Resources', 'Contingency'],
                'Amount': [1200000, 500000, 600000, 200000]
            })
            
            fig = px.pie(budget_data, values='Amount', names='Category', 
                        title='Budget Allocation',
                        color_discrete_sequence=['#3B82F6', '#10B981', '#F59E0B', '#EF4444'])
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Budget metrics
            st.metric("Total Budget", "$2.5M")
            st.metric("Spent", "$1.8M", delta="-$700K")
            st.metric("Remaining", "$700K")
            
            st.progress(72)
            st.caption("72% of budget utilized")

# PMO Operations Module
elif page == "🔧 PMO Operations":
    st.header("PMO Operations")
    
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
        
        st.dataframe(resources_data, use_container_width=True, hide_index=True)
        
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
            "📊 Performance Dashboards",
            "🔄 Resource Reallocation Triggers"
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

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #64748B; padding: 20px;'>
    <p><strong>PMO Agent Dashboard</strong> v1.0 | Built with Streamlit, Pandas & Plotly</p>
    <p>© 2024 Project Management Operations Platform</p>
</div>
""", unsafe_allow_html=True)
