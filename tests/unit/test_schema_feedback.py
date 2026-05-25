from metis.tools.schema_feedback import (
    schema_repair_feedback,
    schema_repair_hint_details,
    schema_repair_hint_types,
    schema_repair_hints,
)


def test_schema_repair_feedback_returns_stable_types_and_human_hints():
    errors = [
        "$.url: additional property not allowed",
        "$.path: missing required property",
        "$.timeout: expected integer, got str",
        "$.command: item count 0 is less than minItems 1",
        "$.encoding: value 'utf-16' not in enum ['utf-8', 'utf-8-sig']",
    ]

    feedback = schema_repair_feedback(errors)

    assert feedback["hint_types"] == [
        "remove_additional_property",
        "add_required_property",
        "fix_type",
        "increase_array_items",
        "use_enum_value",
    ]
    assert feedback["hints"] == schema_repair_hints(errors)
    assert feedback["hint_types"] == schema_repair_hint_types(errors)
    assert feedback["details"] == schema_repair_hint_details(errors)
    assert feedback["details"][0] == {
        "hint_type": "remove_additional_property",
        "schema_path": "$.url",
        "schema_keyword": "additionalProperties",
        "schema_error": "$.url: additional property not allowed",
        "hint_text": "Remove the unsupported argument at $.url.",
    }
