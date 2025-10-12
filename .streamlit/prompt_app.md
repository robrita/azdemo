## Objective: Build a multi-page Streamlit web application with three distinct functionalities:

## Page 1: Employee Skills Generator
Functionality:

A text area input where users can paste a list of employees and their current job roles in the format:
John Regala, Frontend Developer
A button labeled "Generate Skills" that, when clicked, sends each job role to Azure OpenAI to generate a list of relevant skills.
Display the final output in a table with three columns:
Name, Role, Suggested Skills
Tech Requirements:

Use Azure OpenAI API for skill generation.
Handle multiple entries and ensure clean parsing of input.
Display results using st.dataframe() or similar.

## Page 2: Project Scoping Document Evaluator
Functionality:

Upload two .docx files:
Project Scoping Document
Project Guidelines Document
Upon upload, analyze the scoping document against the guidelines.
Generate a report that highlights:
Missing sections
Incomplete details
Misalignments with the guidelines
Tech Requirements:

Use python-docx or similar to parse .docx files.
Use Azure OpenAI to assist in evaluating document completeness and alignment.
Display the evaluation report in a readable format (e.g., markdown or expandable sections).

## Page 3: Project Timeline Monitor
Functionality:

Upload or input project timelines (e.g., via CSV or form).
Monitor progress against deadlines.
Highlight projects that are off-track.
Notify project owners (e.g., via email or on-screen alert).
Tech Requirements:

Use pandas for timeline tracking.
Calculate delays or risks based on current date vs. milestones.
Optional: Integrate with email service or Slack for notifications.
Display a dashboard with status indicators (e.g., green/yellow/red).
General Requirements:

Use Streamlit’s multi-page app structure (streamlit >= 1.10).
Ensure clean UI/UX with clear labels and instructions.
Modularize code for maintainability (e.g., separate logic for each page).
Include error handling for file uploads and API calls.
