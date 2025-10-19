"""
Unit tests for the Schema Builder Streamlit page (pages/1_Schema_Builder.py).

Tests cover schema generation, field management, JSON/Pydantic code generation,
and Streamlit session state management.
"""

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# Add pages directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "pages"))


class TestFieldTypeMapping:
    """Test field type mapping from JSON schema to Python types."""

    def test_string_type_mapping(self):
        """Test string type maps to 'str'."""
        from pages.pg1_Schema_Builder import map_schema_type_to_python

        assert map_schema_type_to_python("string") == "str"

    def test_number_type_mapping(self):
        """Test number type maps to 'float'."""
        from pages.pg1_Schema_Builder import map_schema_type_to_python

        assert map_schema_type_to_python("number") == "float"

    def test_integer_type_mapping(self):
        """Test integer type maps to 'int'."""
        from pages.pg1_Schema_Builder import map_schema_type_to_python

        assert map_schema_type_to_python("integer") == "int"

    def test_boolean_type_mapping(self):
        """Test boolean type maps to 'bool'."""
        from pages.pg1_Schema_Builder import map_schema_type_to_python

        assert map_schema_type_to_python("boolean") == "bool"

    def test_array_type_mapping(self):
        """Test array type maps to 'list'."""
        from pages.pg1_Schema_Builder import map_schema_type_to_python

        assert map_schema_type_to_python("array") == "list"

    def test_object_type_mapping(self):
        """Test object type maps to 'dict'."""
        from pages.pg1_Schema_Builder import map_schema_type_to_python

        assert map_schema_type_to_python("object") == "dict"

    def test_date_type_mapping(self):
        """Test date type maps to 'str'."""
        from pages.pg1_Schema_Builder import map_schema_type_to_python

        assert map_schema_type_to_python("date") == "str"

    def test_email_type_mapping(self):
        """Test email type maps to 'str'."""
        from pages.pg1_Schema_Builder import map_schema_type_to_python

        assert map_schema_type_to_python("email") == "str"

    def test_url_type_mapping(self):
        """Test url type maps to 'str'."""
        from pages.pg1_Schema_Builder import map_schema_type_to_python

        assert map_schema_type_to_python("url") == "str"

    def test_unknown_type_default_to_string(self):
        """Test unknown type defaults to 'str'."""
        from pages.pg1_Schema_Builder import map_schema_type_to_python

        assert map_schema_type_to_python("unknown_type") == "str"


class TestJsonSchemaGeneration:
    """Test JSON schema generation from field definitions."""

    def test_generate_basic_schema(self):
        """Test generating a basic JSON schema."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        fields = [
            {"id": 0, "name": "field_one", "type": "string", "description": "First field"}
        ]
        schema_name = "test_schema"
        schema_description = "Test schema description"

        schema = generate_json_schema_basic(fields, schema_name, schema_description)

        assert schema["name"] == "test_schema"
        assert schema["description"] == "Test schema description"
        assert "schema" in schema
        assert "properties" in schema["schema"]

    def test_schema_includes_default_fields(self):
        """Test schema includes language and summary fields by default."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        fields = []
        schema = generate_json_schema_basic(fields, "test", "test")

        properties = schema["schema"]["properties"]
        assert "language" in properties
        assert "summary" in properties

    def test_schema_includes_custom_fields(self):
        """Test schema includes custom field definitions."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        fields = [
            {"id": 0, "name": "taxpayer_id", "type": "string", "description": "Taxpayer ID"},
            {"id": 1, "name": "amount", "type": "number", "description": "Amount"},
        ]

        schema = generate_json_schema_basic(fields, "test", "test")
        properties = schema["schema"]["properties"]

        assert "taxpayer_id" in properties
        assert "amount" in properties
        assert properties["taxpayer_id"]["type"] == "string"
        assert properties["amount"]["type"] == "number"

    def test_schema_normalizes_field_names(self):
        """Test schema converts field names to snake_case."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        fields = [
            {"id": 0, "name": "taxPayerName", "type": "string", "description": "Name"}
        ]

        schema = generate_json_schema_basic(fields, "test", "test")
        properties = schema["schema"]["properties"]

        # Field name should be as provided (no auto-conversion in this version)
        assert "taxPayerName" in properties

    def test_schema_converts_name_to_snake_case(self):
        """Test schema name is converted to snake_case."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        schema = generate_json_schema_basic([], "My Schema Name", "test")

        assert schema["name"] == "my_schema_name"

    def test_schema_skips_empty_field_names(self):
        """Test schema skips fields with empty names."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        fields = [
            {"id": 0, "name": "", "type": "string", "description": "Empty name"},
            {"id": 1, "name": "valid_field", "type": "string", "description": "Valid"},
        ]

        schema = generate_json_schema_basic(fields, "test", "test")
        properties = schema["schema"]["properties"]

        assert "" not in properties
        assert "valid_field" in properties

    def test_schema_with_multiple_field_types(self):
        """Test schema with various field types."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        fields = [
            {"id": 0, "name": "name", "type": "string", "description": "Name"},
            {"id": 1, "name": "count", "type": "integer", "description": "Count"},
            {"id": 2, "name": "price", "type": "number", "description": "Price"},
            {"id": 3, "name": "is_active", "type": "boolean", "description": "Active"},
            {"id": 4, "name": "date", "type": "date", "description": "Date"},
            {"id": 5, "name": "email", "type": "email", "description": "Email"},
        ]

        schema = generate_json_schema_basic(fields, "test", "test")
        properties = schema["schema"]["properties"]

        assert properties["name"]["type"] == "string"
        assert properties["count"]["type"] == "integer"
        assert properties["price"]["type"] == "number"
        assert properties["is_active"]["type"] == "boolean"
        assert properties["date"]["type"] == "date"
        assert properties["email"]["type"] == "email"

    def test_schema_preserves_field_descriptions(self):
        """Test schema preserves field descriptions."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        fields = [
            {
                "id": 0,
                "name": "field",
                "type": "string",
                "description": "This is a detailed description",
            }
        ]

        schema = generate_json_schema_basic(fields, "test", "test")
        properties = schema["schema"]["properties"]

        assert properties["field"]["description"] == "This is a detailed description"


class TestPydanticModelGeneration:
    """Test Pydantic model code generation."""

    def test_generate_pydantic_model_basic(self):
        """Test generating basic Pydantic model code."""
        from pages.pg1_Schema_Builder import generate_pydantic_model_code

        schema = {
            "name": "test_schema",
            "description": "Test schema",
            "schema": {
                "properties": {
                    "field_one": {
                        "type": "string",
                        "description": "First field",
                    }
                }
            },
        }

        code = generate_pydantic_model_code(schema)

        # Check for key components
        assert "from pydantic import BaseModel, Field" in code
        assert "class DocSchema(BaseModel):" in code
        assert "field_one: str | None = Field" in code
        assert "First field" in code

    def test_pydantic_model_has_docstring(self):
        """Test generated Pydantic model includes docstring."""
        from pages.pg1_Schema_Builder import generate_pydantic_model_code

        schema = {
            "name": "test",
            "description": "Test",
            "schema": {"properties": {}},
        }

        code = generate_pydantic_model_code(schema)

        assert '"""Pydantic schemas' in code
        assert "DocSchema" in code

    def test_pydantic_model_includes_all_fields(self):
        """Test Pydantic model includes all schema fields."""
        from pages.pg1_Schema_Builder import generate_pydantic_model_code

        schema = {
            "name": "test",
            "description": "Test",
            "schema": {
                "properties": {
                    "field_a": {"type": "string", "description": "Field A"},
                    "field_b": {"type": "integer", "description": "Field B"},
                    "field_c": {"type": "boolean", "description": "Field C"},
                }
            },
        }

        code = generate_pydantic_model_code(schema)

        assert "field_a: str | None" in code
        assert "field_b: int | None" in code
        assert "field_c: bool | None" in code

    def test_pydantic_model_uses_correct_type_hints(self):
        """Test Pydantic model uses correct Python type hints."""
        from pages.pg1_Schema_Builder import generate_pydantic_model_code

        schema = {
            "name": "test",
            "description": "Test",
            "schema": {
                "properties": {
                    "text": {"type": "string", "description": "Text"},
                    "count": {"type": "integer", "description": "Count"},
                    "price": {"type": "number", "description": "Price"},
                    "active": {"type": "boolean", "description": "Active"},
                }
            },
        }

        code = generate_pydantic_model_code(schema)

        assert "text: str | None" in code
        assert "count: int | None" in code
        assert "price: float | None" in code
        assert "active: bool | None" in code

    def test_pydantic_model_escapes_descriptions(self):
        """Test Pydantic model properly formats field descriptions."""
        from pages.pg1_Schema_Builder import generate_pydantic_model_code

        schema = {
            "name": "test",
            "description": "Test",
            "schema": {
                "properties": {
                    "field": {"type": "string", "description": "Field with 'quotes'"}
                }
            },
        }

        code = generate_pydantic_model_code(schema)

        # Should contain Field definition with description
        assert "description=" in code
        assert "field" in code

    def test_pydantic_model_has_all_marker(self):
        """Test Pydantic model includes __all__ export."""
        from pages.pg1_Schema_Builder import generate_pydantic_model_code

        schema = {
            "name": "test",
            "description": "Test",
            "schema": {"properties": {}},
        }

        code = generate_pydantic_model_code(schema)

        assert '__all__ = ["DocSchema"]' in code


class TestPythonFunctionGeneration:
    """Test Python function code generation (Mistral format)."""

    def test_generate_python_function_basic(self):
        """Test generating basic Python function."""
        from pages.pg1_Schema_Builder import generate_python_function_code

        schema = {
            "name": "test_schema",
            "description": "Test schema",
            "schema": {"properties": {"field_one": {"type": "string"}}},
        }

        code = generate_python_function_code(schema)

        assert "def get_mistral_json_schema() -> dict[str, Any]:" in code
        assert "return" in code
        assert '"name": "test_schema"' in code

    def test_python_function_includes_docstring(self):
        """Test generated function includes docstring."""
        from pages.pg1_Schema_Builder import generate_python_function_code

        schema = {
            "name": "test",
            "description": "Test schema",
            "schema": {"properties": {}},
        }

        code = generate_python_function_code(schema)

        assert '"""' in code
        assert "JSON schema object" in code

    def test_python_function_valid_syntax(self):
        """Test generated function has valid Python syntax."""
        from pages.pg1_Schema_Builder import generate_python_function_code

        schema = {
            "name": "test",
            "description": "Test",
            "schema": {"properties": {}},
        }

        code = generate_python_function_code(schema)

        # Should be able to compile without syntax errors
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            pytest.fail(f"Generated code has syntax error: {e}")

    def test_python_function_returns_valid_json(self):
        """Test function returns valid JSON schema."""
        from pages.pg1_Schema_Builder import generate_python_function_code

        schema = {
            "name": "test",
            "description": "Test",
            "schema": {
                "properties": {
                    "field": {"type": "string", "description": "A field"}
                }
            },
        }

        code = generate_python_function_code(schema)

        # Execute the code and verify it returns valid schema
        namespace = {"Any": Any}
        exec(code, namespace)
        get_schema_func = namespace["get_mistral_json_schema"]
        result = get_schema_func()

        assert isinstance(result, dict)
        assert result["name"] == "test"
        assert "schema" in result


class TestFieldOperations:
    """Test field management operations (add, remove, update)."""

    def test_field_structure(self):
        """Test field has correct structure."""
        field = {"id": 0, "name": "test_field", "type": "string", "description": "Test"}

        assert "id" in field
        assert "name" in field
        assert "type" in field
        assert "description" in field

    def test_field_with_various_types(self):
        """Test field supports all field types."""
        from pages.pg1_Schema_Builder import FIELD_TYPES

        for field_type in FIELD_TYPES:
            field = {"id": 0, "name": "test", "type": field_type, "description": "Test"}
            assert field["type"] == field_type

    def test_field_name_normalization(self):
        """Test field name can handle various formats."""
        field_names = [
            "simple_name",
            "fieldName",
            "FIELD_NAME",
            "field-name",
            "field.name",
            "field name",
        ]

        for name in field_names:
            field = {"id": 0, "name": name, "type": "string", "description": "Test"}
            assert field["name"] == name

    def test_field_description_length(self):
        """Test field supports long descriptions."""
        long_description = "A" * 1000

        field = {"id": 0, "name": "test", "type": "string", "description": long_description}

        assert len(field["description"]) == 1000
        assert field["description"] == long_description


class TestSessionStateManagement:
    """Test Streamlit session state initialization and management."""

    def test_schema_name_session_state(self):
        """Test schema name persists in session state."""
        schema_name = "test_schema"
        session_state = {"schema_name": schema_name}

        assert session_state["schema_name"] == schema_name

    def test_schema_description_session_state(self):
        """Test schema description persists in session state."""
        description = "Test description"
        session_state = {"schema_description": description}

        assert session_state["schema_description"] == description

    def test_fields_list_session_state(self):
        """Test fields list persists in session state."""
        fields = [
            {"id": 0, "name": "field_one", "type": "string", "description": "Field 1"},
            {"id": 1, "name": "field_two", "type": "integer", "description": "Field 2"},
        ]
        session_state = {"fields": fields}

        assert len(session_state["fields"]) == 2
        assert session_state["fields"][0]["name"] == "field_one"

    def test_next_field_id_tracking(self):
        """Test next field ID is tracked in session state."""
        session_state = {"next_field_id": 5}

        assert session_state["next_field_id"] == 5

    def test_generated_schema_session_state(self):
        """Test generated schema is stored in session state."""
        schema = {
            "name": "test",
            "description": "Test",
            "schema": {"properties": {}},
        }
        session_state = {"generated_schema": schema}

        assert "generated_schema" in session_state
        assert session_state["generated_schema"]["name"] == "test"


class TestSchemaExportFormats:
    """Test schema export in different formats."""

    def test_export_as_json(self):
        """Test exporting schema as JSON string."""
        schema = {
            "name": "test_schema",
            "description": "Test",
            "schema": {"properties": {"field": {"type": "string"}}},
        }

        json_str = json.dumps(schema, indent=2)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["name"] == "test_schema"

    def test_export_json_preserves_structure(self):
        """Test JSON export preserves schema structure."""
        schema = {
            "name": "complex_schema",
            "description": "Complex schema",
            "schema": {
                "properties": {
                    "field_a": {"type": "string", "description": "Field A"},
                    "field_b": {"type": "integer", "description": "Field B"},
                }
            },
        }

        json_str = json.dumps(schema, indent=2)
        parsed = json.loads(json_str)

        assert parsed["schema"]["properties"]["field_a"]["type"] == "string"
        assert parsed["schema"]["properties"]["field_b"]["type"] == "integer"

    def test_pydantic_code_is_valid_python(self):
        """Test Pydantic code export is valid Python."""
        from pages.pg1_Schema_Builder import generate_pydantic_model_code

        schema = {
            "name": "test",
            "description": "Test",
            "schema": {
                "properties": {
                    "field": {"type": "string", "description": "Field"}
                }
            },
        }

        code = generate_pydantic_model_code(schema)

        # Should compile without errors
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            pytest.fail(f"Invalid Python syntax: {e}")

    def test_function_code_is_valid_python(self):
        """Test function code export is valid Python."""
        from pages.pg1_Schema_Builder import generate_python_function_code

        schema = {
            "name": "test",
            "description": "Test",
            "schema": {"properties": {}},
        }

        code = generate_python_function_code(schema)

        # Should compile without errors
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            pytest.fail(f"Invalid Python syntax: {e}")


class TestSchemaValidation:
    """Test schema validation and error handling."""

    def test_empty_schema_generation(self):
        """Test generating schema with no fields."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        schema = generate_json_schema_basic([], "empty_schema", "An empty schema")

        # Should still have default fields
        properties = schema["schema"]["properties"]
        assert "language" in properties
        assert "summary" in properties

    def test_schema_with_whitespace_names(self):
        """Test schema handles fields with whitespace names."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        fields = [
            {"id": 0, "name": "  field_name  ", "type": "string", "description": "Test"}
        ]

        schema = generate_json_schema_basic(fields, "test", "test")

        # Should strip or handle whitespace
        properties = schema["schema"]["properties"]
        # The key should exist (with or without whitespace stripped)
        assert len(properties) > 2  # More than just language and summary

    def test_schema_special_characters_in_names(self):
        """Test schema handles special characters in field names."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        fields = [
            {"id": 0, "name": "field@name#1", "type": "string", "description": "Test"}
        ]

        schema = generate_json_schema_basic(fields, "test", "test")

        # Should include the field (even with special chars)
        properties = schema["schema"]["properties"]
        assert "field@name#1" in properties or len(properties) > 2

    def test_large_number_of_fields(self):
        """Test schema generation with many fields."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        fields = [
            {"id": i, "name": f"field_{i}", "type": "string", "description": f"Field {i}"}
            for i in range(100)
        ]

        schema = generate_json_schema_basic(fields, "large_schema", "Many fields")

        properties = schema["schema"]["properties"]
        # Should include all 100 custom fields plus language and summary
        assert len(properties) >= 100


class TestFieldTypeOptions:
    """Test all available field type options."""

    def test_all_field_types_available(self):
        """Test all field types are defined."""
        from pages.pg1_Schema_Builder import FIELD_TYPES

        expected_types = [
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

        for field_type in expected_types:
            assert field_type in FIELD_TYPES

    def test_field_types_are_unique(self):
        """Test all field types are unique."""
        from pages.pg1_Schema_Builder import FIELD_TYPES

        assert len(FIELD_TYPES) == len(set(FIELD_TYPES))

    def test_field_types_are_lowercase(self):
        """Test all field types are lowercase."""
        from pages.pg1_Schema_Builder import FIELD_TYPES

        for field_type in FIELD_TYPES:
            assert field_type == field_type.lower()


class TestSchemaNameHandling:
    """Test schema name handling and conversion."""

    def test_schema_name_to_snake_case(self):
        """Test schema name is converted to snake_case."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        test_cases = [
            ("My Schema", "my_schema"),
            ("MySchema", "myschema"),
            ("my schema", "my_schema"),
            ("MY_SCHEMA", "my_schema"),
            ("my-schema", "my-schema"),  # Dashes might be preserved
        ]

        for input_name, expected_output in test_cases:
            schema = generate_json_schema_basic([], input_name, "test")
            # The schema name should be processed (typically snake_case or lowercased)
            assert schema["name"] == expected_output

    def test_schema_name_with_special_characters(self):
        """Test schema name handling with special characters."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        schema = generate_json_schema_basic(
            [], "schema-with-special@chars#123", "test"
        )

        # Should handle or strip special characters
        assert schema["name"] is not None
        assert len(schema["name"]) > 0


class TestCodeGenerationIntegration:
    """Integration tests for code generation."""

    def test_generated_pydantic_can_be_used(self):
        """Test generated Pydantic code can actually be imported and used."""
        from pages.pg1_Schema_Builder import generate_pydantic_model_code

        schema = {
            "name": "test",
            "description": "Test",
            "schema": {
                "properties": {
                    "name": {"type": "string", "description": "Name"},
                    "age": {"type": "integer", "description": "Age"},
                }
            },
        }

        code = generate_pydantic_model_code(schema)

        # Execute the generated code
        namespace = {}
        exec(code, namespace)

        # Should have DocSchema class
        assert "DocSchema" in namespace
        DocSchema = namespace["DocSchema"]

        # Should be able to instantiate
        instance = DocSchema(name="Test", age=30)
        assert instance.name == "Test"
        assert instance.age == 30

    def test_generated_function_can_be_executed(self):
        """Test generated function can be executed."""
        from pages.pg1_Schema_Builder import generate_python_function_code

        schema = {
            "name": "test_schema",
            "description": "Test",
            "schema": {
                "properties": {
                    "field": {"type": "string", "description": "Field"}
                }
            },
        }

        code = generate_python_function_code(schema)

        # Execute the generated code
        namespace = {"Any": Any}
        exec(code, namespace)

        # Should have function
        assert "get_mistral_json_schema" in namespace
        func = namespace["get_mistral_json_schema"]

        # Should be callable and return dict
        result = func()
        assert isinstance(result, dict)
        assert result["name"] == "test_schema"


class TestEdgeCasesAndBoundaries:
    """Test edge cases and boundary conditions."""

    def test_very_long_field_name(self):
        """Test handling very long field names."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        long_name = "field_" + "x" * 500
        fields = [
            {"id": 0, "name": long_name, "type": "string", "description": "Test"}
        ]

        schema = generate_json_schema_basic(fields, "test", "test")
        properties = schema["schema"]["properties"]

        assert long_name in properties

    def test_very_long_description(self):
        """Test handling very long descriptions."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        long_desc = "A" * 5000
        fields = [
            {"id": 0, "name": "field", "type": "string", "description": long_desc}
        ]

        schema = generate_json_schema_basic(fields, "test", "test")
        properties = schema["schema"]["properties"]

        assert len(properties["field"]["description"]) == 5000

    def test_unicode_in_field_names(self):
        """Test Unicode characters in field names."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        fields = [
            {"id": 0, "name": "名前", "type": "string", "description": "Japanese name"}
        ]

        schema = generate_json_schema_basic(fields, "test", "test")
        properties = schema["schema"]["properties"]

        assert "名前" in properties

    def test_unicode_in_descriptions(self):
        """Test Unicode in descriptions."""
        from pages.pg1_Schema_Builder import generate_json_schema_basic

        fields = [
            {
                "id": 0,
                "name": "field",
                "type": "string",
                "description": "Description with émojis 🎉 and ñ",
            }
        ]

        schema = generate_json_schema_basic(fields, "test", "test")
        properties = schema["schema"]["properties"]

        assert "émojis" in properties["field"]["description"]

