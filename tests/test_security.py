import pytest
from coldquery.security.identifiers import (
    validate_identifier,
    sanitize_identifier,
    sanitize_table_name,
    sanitize_column_ref,
    InvalidIdentifierError,
    MAX_IDENTIFIER_LENGTH,
)

# Test cases for validate_identifier
def test_validate_identifier_valid():
    validate_identifier("valid_identifier")
    validate_identifier("a" * MAX_IDENTIFIER_LENGTH)
    validate_identifier("_starts_with_underscore")
    validate_identifier("with_numbers123")
    validate_identifier("with_dollar$")

def test_validate_identifier_too_long():
    with pytest.raises(InvalidIdentifierError):
        validate_identifier("a" * (MAX_IDENTIFIER_LENGTH + 1))

def test_validate_identifier_invalid_chars():
    with pytest.raises(InvalidIdentifierError):
        validate_identifier("invalid-identifier")
    with pytest.raises(InvalidIdentifierError):
        validate_identifier("invalid identifier")
    with pytest.raises(InvalidIdentifierError):
        validate_identifier("1starts_with_number")

def test_validate_identifier_contains_dot():
    with pytest.raises(InvalidIdentifierError):
        validate_identifier("schema.table")

# Test cases for sanitize_identifier
def test_sanitize_identifier_valid():
    assert sanitize_identifier("my_table") == '"my_table"'

def test_sanitize_identifier_with_quotes():
    # Identifiers with quotes should be rejected during validation
    with pytest.raises(InvalidIdentifierError):
        sanitize_identifier('table_with_"_quotes')

def test_sanitize_identifier_invalid():
    with pytest.raises(InvalidIdentifierError):
        sanitize_identifier("invalid-table")

# Test cases for sanitize_table_name
def test_sanitize_table_name_no_schema():
    assert sanitize_table_name("my_table") == '"my_table"'

def test_sanitize_table_name_with_schema():
    assert sanitize_table_name("my_table", schema="my_schema") == '"my_schema"."my_table"'

def test_sanitize_table_name_invalid_table():
    with pytest.raises(InvalidIdentifierError):
        sanitize_table_name("invalid-table")

def test_sanitize_table_name_invalid_schema():
    with pytest.raises(InvalidIdentifierError):
        sanitize_table_name("my_table", schema="invalid-schema")

# Test cases for sanitize_column_ref
def test_sanitize_column_ref_no_table():
    assert sanitize_column_ref("my_column") == '"my_column"'

def test_sanitize_column_ref_with_table():
    assert sanitize_column_ref("my_column", table="my_table") == '"my_table"."my_column"'

def test_sanitize_column_ref_invalid_column():
    with pytest.raises(InvalidIdentifierError):
        sanitize_column_ref("invalid-column")

def test_sanitize_column_ref_invalid_table():
    with pytest.raises(InvalidIdentifierError):
        sanitize_column_ref("my_column", table="invalid-table")
