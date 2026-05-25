from metis.tools.schema_validator import ToolArgumentSchemaValidator


def test_schema_validator_requires_properties():
    schema = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}

    result = ToolArgumentSchemaValidator().validate(schema, {})

    assert result.passed is False
    assert "$.path: missing required property" in result.errors


def test_schema_validator_checks_types_and_enum():
    schema = {
        "type": "object",
        "properties": {
            "timeout": {"type": "integer"},
            "mode": {"type": "string", "enum": ["fast", "safe"]},
        },
    }

    result = ToolArgumentSchemaValidator().validate(schema, {"timeout": "30", "mode": "unsafe"})

    assert result.passed is False
    assert "$.timeout: expected integer, got str" in result.errors
    assert "$.mode: value 'unsafe' not in enum ['fast', 'safe']" in result.errors


def test_schema_validator_accepts_one_of_branch():
    schema = {
        "type": "object",
        "properties": {
            "command": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ]
            }
        },
        "required": ["command"],
    }

    result = ToolArgumentSchemaValidator().validate(schema, {"command": ["python", "-m", "pytest"]})

    assert result.passed is True


def test_schema_validator_enforces_exactly_one_one_of_branch():
    schema = {"oneOf": [{"type": "integer"}, {"type": "number"}]}

    result = ToolArgumentSchemaValidator().validate(schema, 3)

    assert result.passed is False
    assert "$: value matched multiple oneOf schemas: [0, 1]" in result.errors


def test_schema_validator_reports_one_of_branch_errors():
    schema = {"oneOf": [{"type": "string", "minLength": 3}, {"type": "array", "minItems": 1}]}

    result = ToolArgumentSchemaValidator().validate(schema, 7)

    assert result.passed is False
    assert result.errors[0].startswith("$: value did not match exactly one oneOf schema")
    assert "branch 0: $: expected string, got int" in result.errors[0]
    assert "branch 1: $: expected array, got int" in result.errors[0]


def test_schema_validator_rejects_additional_properties_when_closed():
    schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "additionalProperties": False,
    }

    result = ToolArgumentSchemaValidator().validate(schema, {"path": "README.md", "url": "https://example.com"})

    assert result.passed is False
    assert "$.url: additional property not allowed" in result.errors


def test_schema_validator_allows_additional_properties_by_default():
    schema = {"type": "object", "properties": {"path": {"type": "string"}}}

    result = ToolArgumentSchemaValidator().validate(schema, {"path": "README.md", "url": "https://example.com"})

    assert result.passed is True


def test_schema_validator_rejects_nested_additional_properties_when_closed():
    schema = {
        "type": "object",
        "properties": {
            "request": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "additionalProperties": False,
            }
        },
    }

    result = ToolArgumentSchemaValidator().validate(schema, {"request": {"path": "README.md", "url": "x"}})

    assert result.passed is False
    assert "$.request.url: additional property not allowed" in result.errors


def test_schema_validator_validates_additional_properties_schema():
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "additionalProperties": {"type": "string"},
    }

    result = ToolArgumentSchemaValidator().validate(schema, {"name": "task", "attempts": 3})

    assert result.passed is False
    assert "$.attempts: expected string, got int" in result.errors


def test_schema_validator_validates_pattern_properties():
    schema = {
        "type": "object",
        "patternProperties": {"^S_": {"type": "string"}, "^I_": {"type": "integer"}},
        "additionalProperties": False,
    }

    result = ToolArgumentSchemaValidator().validate(schema, {"S_name": 7, "I_count": "3", "other": True})

    assert result.passed is False
    assert "$.S_name: expected string, got int" in result.errors
    assert "$.I_count: expected integer, got str" in result.errors
    assert "$.other: additional property not allowed" in result.errors


def test_schema_validator_checks_string_number_and_array_bounds():
    schema = {
        "type": "object",
        "properties": {
            "slug": {"type": "string", "minLength": 3, "maxLength": 6, "pattern": "^[a-z]+$"},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 60},
            "strict_score": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1},
            "command": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
        },
    }

    result = ToolArgumentSchemaValidator().validate(
        schema,
        {"slug": "A", "timeout": 0, "strict_score": 1, "command": ["python", "-m", "pytest", "-q"]},
    )

    assert result.passed is False
    assert "$.slug: length 1 is less than minLength 3" in result.errors
    assert "$.slug: value 'A' does not match pattern '^[a-z]+$'" in result.errors
    assert "$.timeout: value 0 is less than minimum 1" in result.errors
    assert "$.strict_score: value 1 must be less than exclusiveMaximum 1" in result.errors
    assert "$.command: item count 4 exceeds maxItems 3" in result.errors
