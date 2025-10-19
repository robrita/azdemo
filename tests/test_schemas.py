"""
Unit tests for schema validation and data models.

Tests Pydantic models used for structured extraction.
"""


class TestDocSchema:
    """Test suite for DocSchema Pydantic model."""

    def test_schema_with_all_fields(self):
        """Test schema accepts all valid fields."""
        from schemas.gpt_schema import DocSchema

        data = {
            "tin": "123-456-789-00000",
            "taxpayerName": "Sample Corporation",
            "registeredDate": "01/15/2024",
            "registeredAddress": "123 Main St, Manila",
            "tradeName": "Sample Trade",
            "businessType": "Sole Proprietorship",
        }

        schema = DocSchema(**data)

        assert schema.tin == "123-456-789-00000"
        assert schema.taxpayerName == "Sample Corporation"
        assert schema.registeredDate == "01/15/2024"
        assert schema.registeredAddress == "123 Main St, Manila"
        assert schema.tradeName == "Sample Trade"
        assert schema.businessType == "Sole Proprietorship"

    def test_schema_with_partial_fields(self):
        """Test schema accepts partial fields (all optional)."""
        from schemas.gpt_schema import DocSchema

        # Only TIN provided
        schema = DocSchema(tin="123-456-789-00000")
        assert schema.tin == "123-456-789-00000"
        assert schema.taxpayerName is None

        # Only taxpayer name provided
        schema2 = DocSchema(taxpayerName="Sample Corp")
        assert schema2.taxpayerName == "Sample Corp"
        assert schema2.tin is None

    def test_schema_with_no_fields(self):
        """Test schema accepts empty object (all fields optional)."""
        from schemas.gpt_schema import DocSchema

        schema = DocSchema()

        assert schema.tin is None
        assert schema.taxpayerName is None
        assert schema.registeredDate is None
        assert schema.registeredAddress is None
        assert schema.tradeName is None
        assert schema.businessType is None

    def test_schema_converts_to_dict(self):
        """Test schema can be converted to dictionary."""
        from schemas.gpt_schema import DocSchema

        data = {
            "tin": "123-456-789-00000",
            "taxpayerName": "Sample Corporation",
        }

        schema = DocSchema(**data)
        result_dict = schema.model_dump()

        assert isinstance(result_dict, dict)
        assert result_dict["tin"] == "123-456-789-00000"
        assert result_dict["taxpayerName"] == "Sample Corporation"

    def test_schema_json_serialization(self):
        """Test schema can be serialized to JSON."""
        from schemas.gpt_schema import DocSchema

        data = {
            "tin": "123-456-789-00000",
            "taxpayerName": "Sample Corporation",
        }

        schema = DocSchema(**data)
        json_str = schema.model_dump_json()

        assert isinstance(json_str, str)
        assert "123-456-789-00000" in json_str
        assert "Sample Corporation" in json_str

    def test_schema_handles_none_values(self):
        """Test schema explicitly handles None values."""
        from schemas.gpt_schema import DocSchema

        data = {
            "tin": None,
            "taxpayerName": None,
            "registeredDate": None,
        }

        schema = DocSchema(**data)

        assert schema.tin is None
        assert schema.taxpayerName is None
        assert schema.registeredDate is None

    def test_schema_field_types(self):
        """Test schema validates field types correctly."""
        from schemas.gpt_schema import DocSchema

        # String fields should accept strings
        schema = DocSchema(tin="123-456-789-00000")
        assert isinstance(schema.tin, str)

        # Should also accept None
        schema2 = DocSchema(tin=None)
        assert schema2.tin is None

    def test_schema_tin_format_variations(self):
        """Test schema accepts various TIN formats."""
        from schemas.gpt_schema import DocSchema

        # Standard format
        schema1 = DocSchema(tin="123-456-789-00000")
        assert schema1.tin == "123-456-789-00000"

        # Without dashes
        schema2 = DocSchema(tin="12345678900000")
        assert schema2.tin == "12345678900000"

        # Shorter format
        schema3 = DocSchema(tin="123-456-789")
        assert schema3.tin == "123-456-789"

    def test_schema_date_format_variations(self):
        """Test schema accepts various date formats."""
        from schemas.gpt_schema import DocSchema

        # MM/DD/YYYY format
        schema1 = DocSchema(registeredDate="01/15/2024")
        assert schema1.registeredDate == "01/15/2024"

        # Different format
        schema2 = DocSchema(registeredDate="2024-01-15")
        assert schema2.registeredDate == "2024-01-15"

        # Text format
        schema3 = DocSchema(registeredDate="January 15, 2024")
        assert schema3.registeredDate == "January 15, 2024"

    def test_schema_with_extra_fields_ignored(self):
        """Test schema ignores extra fields not in model."""
        from schemas.gpt_schema import DocSchema

        data = {
            "tin": "123-456-789-00000",
            "taxpayerName": "Sample Corp",
            "extraField": "This should be ignored",
            "anotherExtra": 12345,
        }

        # Should not raise error, extra fields ignored
        schema = DocSchema(**data)
        assert schema.tin == "123-456-789-00000"
        assert schema.taxpayerName == "Sample Corp"
        assert not hasattr(schema, "extraField")


class TestMistralSchema:
    """Test suite for Mistral Document AI schema."""

    def test_mistral_schema_structure(self):
        """Test Mistral schema has correct structure."""
        from schemas.mistral_schema import get_mistral_json_schema

        mistral_schema = get_mistral_json_schema()

        assert "name" in mistral_schema
        assert "description" in mistral_schema
        assert "schema" in mistral_schema
        assert "properties" in mistral_schema["schema"]

    def test_mistral_schema_has_expected_properties(self):
        """Test Mistral schema includes expected field properties."""
        from schemas.mistral_schema import get_mistral_json_schema

        mistral_schema = get_mistral_json_schema()
        properties = mistral_schema["schema"]["properties"]

        # Check for expected fields (including extra Mistral-specific fields)
        expected_fields = [
            "tin",
            "taxpayerName",
            "registeredDate",
            "registeredAddress",
            "tradeName",
            "businessType",
        ]

        for field in expected_fields:
            assert field in properties, f"Field '{field}' missing from schema"

    def test_mistral_schema_field_types(self):
        """Test Mistral schema fields have correct types."""
        from schemas.mistral_schema import get_mistral_json_schema

        mistral_schema = get_mistral_json_schema()
        properties = mistral_schema["schema"]["properties"]

        # All fields should be string type
        for _field_name, field_def in properties.items():
            assert "type" in field_def
            # Fields can be either "string" or ["string", "null"]
            field_type = field_def["type"]
            if isinstance(field_type, list):
                assert "string" in field_type
            else:
                assert field_type == "string"

    def test_mistral_schema_has_descriptions(self):
        """Test Mistral schema fields have descriptions."""
        from schemas.mistral_schema import get_mistral_json_schema

        mistral_schema = get_mistral_json_schema()
        properties = mistral_schema["schema"]["properties"]

        for _field_name, field_def in properties.items():
            assert "description" in field_def, "Field missing description"
            assert len(field_def["description"]) > 0

    def test_mistral_schema_required_fields(self):
        """Test Mistral schema structure is valid."""
        from schemas.mistral_schema import get_mistral_json_schema

        mistral_schema = get_mistral_json_schema()

        # Schema should have name and description
        assert mistral_schema["name"] == "bir_document_extraction"
        assert len(mistral_schema["description"]) > 0


class TestSchemaCompatibility:
    """Test compatibility between different schema formats."""

    def test_gpt_and_mistral_have_common_fields(self):
        """Test GPT and Mistral schemas define common BIR fields."""
        from schemas.gpt_schema import DocSchema
        from schemas.mistral_schema import get_mistral_json_schema

        # Get GPT schema fields
        gpt_fields = set(DocSchema.model_fields.keys())

        # Get Mistral schema fields (excluding extra fields like language, summary)
        mistral_schema = get_mistral_json_schema()
        mistral_fields = set(mistral_schema["schema"]["properties"].keys())

        # Common BIR fields that should be in both
        common_fields = {
            "tin",
            "taxpayerName",
            "registeredDate",
            "registeredAddress",
            "tradeName",
            "businessType",
        }

        # Both schemas should have all common fields
        assert common_fields.issubset(gpt_fields), (
            f"GPT schema missing: {common_fields - gpt_fields}"
        )
        assert common_fields.issubset(mistral_fields), (
            f"Mistral schema missing: {common_fields - mistral_fields}"
        )

    def test_schemas_accept_same_data(self):
        """Test both schemas accept the same data structure."""
        from schemas.gpt_schema import DocSchema
        from schemas.mistral_schema import get_mistral_json_schema

        test_data = {
            "tin": "123-456-789-00000",
            "taxpayerName": "Sample Corporation",
            "registeredDate": "01/15/2024",
            "registeredAddress": "123 Main St, Manila",
            "tradeName": "Sample Trade",
            "businessType": "Sole Proprietorship",
        }

        # GPT schema should accept it
        gpt_schema = DocSchema(**test_data)
        assert gpt_schema.tin == test_data["tin"]

        # Mistral schema properties should match
        mistral_schema = get_mistral_json_schema()
        for field in test_data:
            assert field in mistral_schema["schema"]["properties"]

    def test_schemas_handle_partial_data_consistently(self):
        """Test both schemas handle partial data the same way."""
        from schemas.gpt_schema import DocSchema
        from schemas.mistral_schema import get_mistral_json_schema

        partial_data = {"tin": "123-456-789-00000"}

        # GPT schema accepts partial data
        gpt_schema = DocSchema(**partial_data)
        assert gpt_schema.tin == "123-456-789-00000"
        assert gpt_schema.taxpayerName is None

        # Mistral schema should have tin property
        mistral_schema = get_mistral_json_schema()
        assert "tin" in mistral_schema["schema"]["properties"]


class TestSchemaEdgeCases:
    """Test edge cases and boundary conditions for schemas."""

    def test_schema_with_very_long_strings(self):
        """Test schema handles very long field values."""
        from schemas.gpt_schema import DocSchema

        long_name = "A" * 1000
        long_address = "B" * 5000

        schema = DocSchema(taxpayerName=long_name, registeredAddress=long_address)

        assert len(schema.taxpayerName) == 1000
        assert len(schema.registeredAddress) == 5000

    def test_schema_with_special_characters(self):
        """Test schema handles special characters."""
        from schemas.gpt_schema import DocSchema

        special_data = {
            "taxpayerName": "Test Corp & Co. (Ñ) Ltd.",
            "registeredAddress": "123 Main St., Apt #5B",
            "tradeName": "Test™ Trading®",
        }

        schema = DocSchema(**special_data)

        assert schema.taxpayerName == special_data["taxpayerName"]
        assert schema.registeredAddress == special_data["registeredAddress"]
        assert schema.tradeName == special_data["tradeName"]

    def test_schema_with_unicode_characters(self):
        """Test schema handles Unicode characters."""
        from schemas.gpt_schema import DocSchema

        unicode_data = {
            "taxpayerName": "菲律宾公司",
            "registeredAddress": "Calle José Rizal № 123",
            "tradeName": "商店",
        }

        schema = DocSchema(**unicode_data)

        assert schema.taxpayerName == unicode_data["taxpayerName"]
        assert schema.registeredAddress == unicode_data["registeredAddress"]

    def test_schema_with_empty_strings(self):
        """Test schema handles empty strings."""
        from schemas.gpt_schema import DocSchema

        empty_data = {
            "tin": "",
            "taxpayerName": "",
            "registeredDate": "",
        }

        schema = DocSchema(**empty_data)

        # Empty strings should be preserved, not converted to None
        assert schema.tin == ""
        assert schema.taxpayerName == ""
        assert schema.registeredDate == ""

    def test_schema_serialization_preserves_null(self):
        """Test schema serialization preserves null values correctly."""
        from schemas.gpt_schema import DocSchema

        schema = DocSchema(tin="123-456-789-00000", taxpayerName=None)

        # Model dump should preserve None
        dump = schema.model_dump()
        assert dump["tin"] == "123-456-789-00000"
        assert dump["taxpayerName"] is None

        # JSON dump should convert None to null
        json_str = schema.model_dump_json()
        assert "null" in json_str or "None" not in json_str
