import streamlit as st
import os
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

def render_sidebar():
    """
    Render the common sidebar navigation for all pages in the PMO Agent application.
    This function should be called on every page to maintain consistent navigation.
    """
    # Configure page
    st.set_page_config(
        page_title="PMO Agent Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.logo(
        "https://upload.wikimedia.org/wikipedia/commons/9/9a/Universal_Robina_logo_2016.svg",
        link="https://www.urc.com.ph/",
    )

    # Custom CSS to adjust padding and hide certain elements
    # This is useful to ensure the layout looks good across different pages
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 3rem;
            # padding-bottom: 1rem;
            # padding-left: 1rem;
            # padding-right: 1rem;
        }
        .stAppDeployButton {
            display: none;
        }
        .st-emotion-cache-15ecox0 {
            display: none;
        }
        .viewerBadge_container__r5tak {
            display: none;
        }
        .styles_viewerBadge__CvC9N {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        with st.container(border=True):
            st.page_link("app.py", label="PMO Dashboard", icon="🚀")
            st.page_link("pages/0_Dashboard_Overview.py", label="Dashboard Overview", icon="🏠")
            st.page_link("pages/1_Employee_Skills_Generator.py", label="Skills Generator", icon="👥")
            st.page_link("pages/2_Project_Scoping_Document_Evaluator.py", label="Document Evaluator", icon="📄")
            st.page_link("pages/3_Project_Timeline_Monitor.py", label="Timeline Monitor", icon="⏰")
            st.page_link("pages/4_Unstructured_Document_Parser.py", label="Document Parser", icon="📋")
            st.page_link("pages/5_Skills_Management.py", label="Skills Management", icon="🎯")
            st.page_link("pages/6_Document_Analysis.py", label="Document Analysis", icon="🔍")
            st.page_link("pages/7_Project_Monitoring.py", label="Project Monitoring", icon="📊")
            st.page_link("pages/8_PMO_Operations.py", label="PMO Operations", icon="🔧")

        st.image(
            "https://cdn.manilastandard.net/wp-content/uploads/2024/02/URC-Universal-Robina-Corp.jpg",
        )
        st.write("Powered by Azure AI Foundry.")

def keep_state(state_object, state_name):
    """
    Keep the Streamlit session state alive across page navigations.
    This is useful to maintain stateful data like uploaded files or user inputs.
    """
    if state_object:
        st.session_state[state_name] = state_object
    elif state_name in st.session_state:
        return True
    return False

# Cosmos DB Configuration and Client
@st.cache_resource
def get_cosmos_client(container_name=None):
    """
    Initialize and return Cosmos DB client, database client, or container client.
    Uses environment variables for configuration.
    
    Args:
        container_name (str, optional): If provided, returns container client for this container.
                                      If None, returns cosmos client or database client based on usage.
    
    Returns:
        CosmosClient, DatabaseProxy, or ContainerProxy: Depending on the container_name parameter
    """
    try:
        # Use DefaultAzureCredential for managed identity or local development
        credential = DefaultAzureCredential()
        
        cosmos_client = CosmosClient(
            url=os.environ.get("AZURE_COSMOS_ENDPOINT"),
            credential=credential
        )
        
        # If no container name provided, return cosmos client
        if container_name is None:
            return cosmos_client
            
        # Get database client
        database_name = os.environ.get("AZURE_COSMOS_DATABASE")
        database_client = cosmos_client.get_database_client(database_name)
        
        # Return container client for the specified container
        return database_client.get_container_client(container_name)
        
    except Exception as e:
        error_msg = f"Failed to initialize Cosmos DB client"
        if container_name:
            error_msg += f" for container '{container_name}'"
        error_msg += f": {e}"
        st.error(error_msg)
        return None
