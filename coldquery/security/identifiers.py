import re

# PostgreSQL identifier max length is 63 characters
MAX_IDENTIFIER_LENGTH = 63
# PostgreSQL identifier pattern - letters, digits, underscore, dollar sign
IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_$]*$")


class InvalidIdentifierError(ValueError):
    """Raised when an identifier is invalid."""

    pass


def validate_identifier(name: str) -> None:
    """
    Validates a single PostgreSQL identifier.

    Args:
        name: The identifier to validate.

    Raises:
        InvalidIdentifierError: If the identifier is invalid.
    """
    if not name:
        raise InvalidIdentifierError("Identifier must be a non-empty string")
    if len(name) > MAX_IDENTIFIER_LENGTH:
        raise InvalidIdentifierError(
            f"Identifier '{name}' exceeds the maximum length of {MAX_IDENTIFIER_LENGTH} characters."
        )
    if not IDENTIFIER_PATTERN.match(name):
        raise InvalidIdentifierError(
            f"Identifier '{name}' contains invalid characters. Must match {IDENTIFIER_PATTERN.pattern}"
        )
    if "." in name:
        raise InvalidIdentifierError(
            "Identifier cannot contain a dot. Use sanitize_table_name for schema-qualified names."
        )


def sanitize_identifier(name: str) -> str:
    """
    Validates and sanitizes a single PostgreSQL identifier by double-quoting it.

    Args:
        name: The identifier to sanitize.

    Returns:
        The sanitized identifier.
    """
    validate_identifier(name)
    # Escape any double quotes inside the identifier
    escaped_name = name.replace('"', '""')
    return f'"{escaped_name}"'


def sanitize_table_name(table: str, schema: str | None = None) -> str:
    """
    Sanitizes a table name, optionally with a schema.

    Args:
        table: The table name.
        schema: The optional schema name.

    Returns:
        The sanitized, schema-qualified table name.
    """
    sanitized_table = sanitize_identifier(table)
    if schema:
        sanitized_schema = sanitize_identifier(schema)
        return f"{sanitized_schema}.{sanitized_table}"
    return sanitized_table


def sanitize_column_ref(column: str, table: str | None = None) -> str:
    """
    Sanitizes a column reference, optionally with a table.

    Args:
        column: The column name.
        table: The optional table name.

    Returns:
        The sanitized column reference.
    """
    sanitized_column = sanitize_identifier(column)
    if table:
        sanitized_table = sanitize_identifier(table)
        return f"{sanitized_table}.{sanitized_column}"
    return sanitized_column
