import sys

import streamlit as st
from dotenv import load_dotenv

sys.path.append("..")
from utils import render_sidebar

# Load environment variables
load_dotenv()


def main():
    # Render shared sidebar navigation
    render_sidebar()

    # Page Title
    st.title("💰 Pricing Reference")
    st.markdown(
        """
    <div style="text-align: center; margin-bottom: 2rem;">
        <p style="font-size: 1.2rem; color: var(--text-secondary);">
            Official pricing information for Azure AI services used in this application
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Create three columns for the pricing cards
    col1, col2, col3 = st.columns(3, gap="large")

    # Azure Document Intelligence Card
    with col1.container(key="container1"):
        st.markdown("### Azure Document Intelligence")
        st.markdown("""
        Extract text, key-value pairs, tables, and structures from documents using pre-built and custom models.
        """)

        st.markdown("#### Features")
        st.markdown("""
        - Prebuilt invoice models
        - Custom template models
        - Neural layout analysis
        - Form recognition
        """)

        st.link_button(
            "View Pricing →",
            "https://azure.microsoft.com/en-us/pricing/details/ai-document-intelligence/",
            use_container_width=True,
        )

    # Azure Content Understanding Card
    with col2.container(key="container2"):
        st.markdown("### Azure Content Understanding")
        st.markdown("""
        Advanced document analysis with deep understanding of content structure and semantic relationships.
        """)

        st.markdown("#### Features")
        st.markdown("""
        - Semantic document analysis
        - Content classification
        - Entity extraction
        - Relationship mapping
        """)

        st.link_button(
            "View Pricing →",
            "https://azure.microsoft.com/en-us/pricing/details/content-understanding/",
            use_container_width=True,
        )

    # Azure OpenAI Card
    with col3.container(key="container3"):
        st.markdown("### Azure OpenAI Service")
        st.markdown("""
        Access GPT-4 Vision and other OpenAI models through Azure's enterprise-grade infrastructure.
        """)

        st.markdown("#### Features")
        st.markdown("""
        - GPT-4 Vision (GPT-4.1/GPT-5)
        - Document understanding
        - Natural language processing
        - Vision capabilities
        """)

        st.link_button(
            "View Pricing →",
            "https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/",
            use_container_width=True,
        )

    # Additional Information Section
    st.markdown("---")
    st.markdown("### 📊 Pricing Comparison Tips")

    col_left, col_right = st.columns(2)

    with col_left:
        st.info("""
        **Document Intelligence** is best for:
        - Structured forms and invoices
        - High-volume batch processing
        - Predictable document formats
        - Cost-effective extraction
        """)

    with col_right:
        st.info("""
        **OpenAI & Content Understanding** excel at:
        - Complex document analysis
        - Unstructured content
        - Semantic understanding
        - Variable document formats
        """)

    # Footer with helpful links
    st.markdown("---")
    st.markdown(
        """
    <div style="text-align: center; margin-top: 2rem;">
        <p style="color: var(--text-secondary);">
            💡 <strong>Tip:</strong> Start with free tiers to test services before scaling up<br>
            📚 Learn more: <a href="https://azure.microsoft.com/en-us/pricing/calculator/" target="_blank">Azure Pricing Calculator</a>
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
