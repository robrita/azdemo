import json
import sys
from typing import Any

import streamlit as st
from dotenv import load_dotenv

sys.path.append("..")
from utils import render_sidebar

# Load environment variables
load_dotenv()

# Field type options
FIELD_TYPES = [
    "string",
    "number",
    "integer",
    "boolean",
    "array",
    "object",
    "date",
    "email",
    "url",
]


def initialize_session_state():
    """Initialize session state for schema builder."""
    if "schema_name" not in st.session_state:
        st.session_state.schema_name = "document_extraction"

    if "schema_description" not in st.session_state:
        st.session_state.schema_description = "Extract structured information from documents"

    if "fields" not in st.session_state:
        # Initialize with one default field
        st.session_state.fields = [
            {
                "id": 0,
                "name": "field_name",
                "type": "string",
                "description": "Field description",
            }
        ]

    if "next_field_id" not in st.session_state:
        st.session_state.next_field_id = 1


def generate_json_schema() -> dict[str, Any]:
    """Generate JSON schema object from collected fields."""
    properties = {
        "language": {
            "title": "Language",
            "type": "string",
            "description": "The language of the document.",
        },
        "summary": {
            "title": "Summary",
            "type": "string",
            "description": "A brief summary of the document in English.",
        },
    }

    for field in st.session_state.fields:
        field_name = field["name"].strip()
        if not field_name:
            continue

        properties[field_name] = {
            "title": field_name.replace("_", " ").title(),
            "type": field["type"],
            "description": field["description"],
        }

    schema = {
        "name": st.session_state.schema_name.replace(" ", "_").lower(),
        "description": st.session_state.schema_description,
        "schema": {"properties": properties},
    }

    return schema


def add_field():
    """Add a new field to the schema."""
    field_id = st.session_state.next_field_id
    st.session_state.fields.append(
        {
            "id": field_id,
            "name": f"field_{field_id}",
            "type": "string",
            "description": "Enter field description",
        }
    )
    st.session_state.next_field_id += 1


def remove_field(field_id: int):
    """Remove a field from the schema."""
    st.session_state.fields = [f for f in st.session_state.fields if f["id"] != field_id]


def main():
    render_sidebar()

    st.title("🏗️ JSON Schema Builder")
    st.markdown(
        """
    <div style="text-align: center; margin-bottom: 2rem;">
        <p style="font-size: 1.1rem; color: var(--text-secondary);">
            Create custom JSON schemas for document extraction with an intuitive field builder
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Initialize session state
    initialize_session_state()

    # Create two main sections
    col1, col2 = st.columns([1, 2], gap="large")

    with col1:
        st.markdown("### ⚙️ Field Configuration")

        # Add field button
        if st.button("➕ Add Field", use_container_width=True):
            add_field()
            st.rerun()

        st.markdown(f"**Total Fields:** {len(st.session_state.fields)}")

    with col2:
        st.markdown("### 📋 Schema Configuration")

        with st.container(border=True):
            st.markdown("**Schema Details**")

            # Schema name input
            schema_name = st.text_input(
                "Schema Name",
                value=st.session_state.schema_name,
                placeholder="e.g., invoice_extraction",
                help="Name for your schema (will be converted to snake_case)",
            )
            st.session_state.schema_name = schema_name

            # Schema description input
            schema_description = st.text_input(
                "Schema Description",
                value=st.session_state.schema_description,
                placeholder="Describe what this schema extracts from...",
                help="Brief description of the schema purpose",
            )
            st.session_state.schema_description = schema_description

    # Fields Management Section
    st.markdown("---")
    st.markdown("### 🔧 Field Manager")

    if st.session_state.fields:
        for idx, field in enumerate(st.session_state.fields):
            with st.container(border=True):
                # Field header with delete button
                col_header, col_delete = st.columns([4, 1])

                with col_header:
                    st.markdown(f"**Field {idx + 1}**")

                with col_delete:
                    if st.button(
                        "🗑️",
                        key=f"delete_field_{field['id']}",
                        help="Delete this field",
                        use_container_width=True,
                    ):
                        remove_field(field["id"])
                        st.rerun()

                # Field inputs in columns for better layout
                col_name, col_type = st.columns([1, 1])

                with col_name:
                    field_name = st.text_input(
                        "Field Name",
                        value=field["name"],
                        placeholder="e.g., taxpayer_name",
                        key=f"name_{field['id']}",
                        help="Name of the field to extract",
                    )
                    field["name"] = field_name

                with col_type:
                    field_type = st.selectbox(
                        "Field Type",
                        FIELD_TYPES,
                        index=FIELD_TYPES.index(field["type"]),
                        key=f"type_{field['id']}",
                        help="Data type of the field",
                    )
                    field["type"] = field_type

                # Description field (full width)
                field_description = st.text_input(
                    "Field Description",
                    value=field["description"],
                    placeholder="Describe what this field contains...",
                    key=f"desc_{field['id']}",
                    help="Detailed description for the schema",
                )
                field["description"] = field_description
    else:
        st.info("No fields added yet. Click 'Add Field' to get started.")

    # Generate Schema Section
    st.markdown("---")
    st.markdown("### 📥 Generate & Export")

    col_generate, _ = st.columns([1, 2])
    with col_generate:
        if st.button("🚀 Generate Schema", use_container_width=True):
            generated_schema = generate_json_schema()

            # Store in session state for download
            st.session_state.generated_schema = generated_schema

            st.success("✅ Schema generated successfully!")

    # Display generated schema
    if "generated_schema" in st.session_state:
        st.markdown("---")
        st.markdown("### ✅ Generated Schema")

        # Create tabs for different formats
        tab_pydantic, tab_function, tab_json_schema = st.tabs(
            ["🐍 Pydantic Model", "⚙️ JSON Function", "📋 JSON Schema"]
        )

        with tab_pydantic:
            st.markdown("**Pydantic Model Format** (like `gpt_schema.py`)")
            pydantic_code = generate_pydantic_model_code(st.session_state.generated_schema)
            st.code(pydantic_code, language="python")

            pydantic_str = pydantic_code
            schema_name = (
                st.session_state.generated_schema["name"].replace("_", " ").title().replace(" ", "")
            )
            st.download_button(
                label="💾 Download Pydantic Model",
                data=pydantic_str,
                file_name=f"{schema_name.lower()}_schema.py",
                mime="text/plain",
                key="download_pydantic",
            )

        with tab_function:
            st.markdown("**Python Function Format** (like `mistral_schema.py`)")
            python_code = generate_python_function_code(st.session_state.generated_schema)
            st.code(python_code, language="python")

            st.download_button(
                label="💾 Download JSON Function",
                data=python_code,
                file_name=f"{st.session_state.schema_name.replace(' ', '_').lower()}_schema.py",
                mime="text/plain",
                key="download_function",
            )

        with tab_json_schema:
            st.markdown("**Generated JSON Schema**")
            st.json(st.session_state.generated_schema)

            schema_json = json.dumps(st.session_state.generated_schema, indent=2)
            st.download_button(
                label="💾 Download JSON",
                data=schema_json,
                file_name=f"{st.session_state.schema_name.replace(' ', '_').lower()}_schema.json",
                mime="application/json",
                key="download_json",
            )

    # Help section
    st.markdown("---")
    st.markdown("### 💡 Tips & Guidance")

    col_tips1, col_tips2 = st.columns(2)

    with col_tips1:
        st.info(
            """
        **Best Practices:**
        - Use descriptive, lowercase field names with underscores
        - Provide clear, specific field descriptions
        - Choose appropriate data types for validation
        - Start with `string` type when unsure
        - ⭐ **Language & Summary are included by default** to enhance data extraction quality
        """
        )

    with col_tips2:
        st.info(
            """
        **Field Type Guide:**
        - **string**: Text data, names, addresses
        - **number/integer**: Numeric values, counts
        - **date**: Date values in ISO format
        - **email**: Email addresses
        - **url**: Web URLs
        - **boolean**: True/false values
        - **array/object**: Complex structures
        """
        )


def map_schema_type_to_python(field_type: str) -> str:
    """Map JSON schema types to Python type hints."""
    type_mapping = {
        "string": "str",
        "number": "float",
        "integer": "int",
        "boolean": "bool",
        "array": "list",
        "object": "dict",
        "date": "str",
        "email": "str",
        "url": "str",
    }
    return type_mapping.get(field_type, "str")


def generate_pydantic_model_code(schema: dict[str, Any]) -> str:
    """Generate Pydantic model code for the schema (like gpt_schema.py format)."""
    properties = schema.get("schema", {}).get("properties", {})

    # Build field definitions
    field_lines = []
    for field_name, field_info in properties.items():
        field_type = field_info.get("type", "string")
        field_description = field_info.get("description", "")
        python_type = map_schema_type_to_python(field_type)

        # Format as optional field (str | None pattern like gpt_schema.py)
        field_lines.append(
            f'    {field_name}: {python_type} | None = Field(None, description="{field_description}")'
        )

    field_definitions = "\n".join(field_lines)

    code = f'''"""Pydantic schemas for GPT Vision document extraction.

Defines structured models used for parsing Azure OpenAI Vision responses.
"""

from pydantic import BaseModel, Field


class DocSchema(BaseModel):
    """Structured extraction model for document extraction.

    Fields map to the standardized JSON output consumed by the Streamlit app.
    All fields are optional because documents may have missing values.
    """

{field_definitions}


__all__ = ["DocSchema"]
'''
    return code


def generate_python_function_code(schema: dict[str, Any]) -> str:
    """Generate Python function code for the schema (Mistral JSON schema format)."""
    schema_dict_str = json.dumps(schema, indent=4)

    code = f'''from typing import Any


def get_mistral_json_schema() -> dict[str, Any]:
    """
    Return the JSON schema object for {schema.get("description", "document extraction")}.
    """
    return {schema_dict_str}
'''
    return code


if __name__ == "__main__":
    main()
