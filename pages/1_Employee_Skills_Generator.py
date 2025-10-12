# pages/1_Employee_Skills_Generator.py
import os
import sys
import json
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
sys.path.append('..')
from utils import render_sidebar, keep_state

from azure.ai.agents import AgentsClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import (
    MessageRole,
)

# Load environment variables
load_dotenv()

# Create an instance of the AgentsClient using DefaultAzureCredential
agents_client = AgentsClient(
    endpoint=os.getenv("FOUNDRY_API_ENDPOINT"),
    credential=DefaultAzureCredential()
)

class SkillsGenerator:
    def __init__(self):
        # Create a thread for the agent
        if "thread1" not in st.session_state:
            with st.spinner("Please wait while creating a thread..."):
                st.session_state.thread1 = agents_client.threads.create()

        self.thread = st.session_state.thread1

    def generate_skills(self, content):
        """Generate skills for a given role using Azure Foundry Agent"""
        try:
            # Create a message, with the prompt being the message content that is sent to the model
            agents_client.messages.create(
                thread_id=self.thread.id,
                role="user",
                content=content,
            )
            
            # [START create_and_process]
            run = agents_client.runs.create_and_process(
                thread_id=self.thread.id,
                agent_id=os.getenv("AGENT_SKILLS_GENERATOR_ID"),
            )

            # [END create_and_process]
            if run.status == "failed":
                raise Exception(run.last_error)

            # Get the last message from the sender
            last_msg = agents_client.messages.get_last_message_text_by_role(
                thread_id=self.thread.id, role=MessageRole.AGENT
            )
 
            return last_msg.text.value
            
        except Exception as e:
            st.error(f"Error generating skills: {str(e)}")
            return "Error generating skills"

def main():
    # Render shared sidebar navigation
    render_sidebar()
    
    st.title("👥 Employee Skills Generator")
    st.markdown("Generate relevant skills for employees based on their job roles using AI.")
    
    # Initialize the skills generator
    skills_gen = SkillsGenerator()
    container1 = st.container(border=True, key="container1")
    
    # Input section
    container1.subheader("📝 Input Employee Data")

    # Example data
    example_data = """Sarah Johnson, Data Scientist, Mid-level
Mike Chen, DevOps Engineer, Mid-level
Lisa Brown, UX Designer, Junior"""

    saved_data = st.session_state.get("input_text", "")
    
    input_text = container1.text_area(
        "Enter employees in the format: Name, Job Role, Seniority Level (one per line)",
        placeholder="Sarah Johnson, Data Scientist, Mid-level\nMike Chen, DevOps Engineer, Mid-level",
        height=150,
        value=example_data if container1.checkbox("Use example data") else saved_data
    )

    if keep_state(input_text, "input_text"):
        input_text = st.session_state.input_text

    employees = input_text.strip()
    results = []

    # Show example or help
    with container1.expander("ℹ️ How this tool works?"):
        st.markdown("""
        ### How to Use the Skills Generator:
        
        1. **Enter Employee Data**: Input employee details in the format: `Name, Job Role, Seniority Level` (one per line)
        2. **Click 'Generate Skills'**: The AI will analyze the input and generate relevant skills for each employee
        
        ### What You'll Get:
        - **Skills List**: A list of skills relevant to each employee's role and seniority level
        - **Download Option**: Download the results as a CSV file for further use
        """)

    # Generate button
    if st.button("🚀 Generate Skills", type="primary", disabled=employees == ""):
        # Generate skills
        with st.spinner("Generating skills..."):
            skills = skills_gen.generate_skills(employees)
            skills_json = json.loads(skills)
            results = skills_json.get("results", [])
            st.success("✅ Skills generated successfully!")

    if keep_state(results, "results"):
        results = st.session_state.results

    if results:
        # Display results
        st.subheader("📊 Results")
        
        # Display the results in an expandable format
        with st.expander("📋 Full Results", expanded=True):
            # Create DataFrame
            df = pd.DataFrame(results)
        
            # Display as table
            st.dataframe(
                df,
                width='stretch',
                hide_index=True
            )
        
        # Download option
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name="employee_skills.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main()