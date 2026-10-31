import re
import os
import duckdb

FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "ATTACH", "DETACH", "PRAGMA", "COPY", "EXPORT", "IMPORT",
    "LOAD", "INSTALL", "CALL", "EXECUTE", "SET", "VACUUM",
}

class SQLGuardError(Exception):
    pass

def sanitize_and_validate_sql(query: str) -> str:
    """
    Validates that a SQL query is a single read-only SELECT or WITH statement.
    Rejects multi-statement queries and forbidden DDL/DML keywords.
    """
    if not query or not isinstance(query, str):
        raise SQLGuardError("Query cannot be empty.")

    cleaned = query.strip()
    # Strip trailing semicolons
    cleaned = cleaned.rstrip(";").strip()
    if not cleaned:
        raise SQLGuardError("Query cannot be empty.")

    # Reject internal semicolons that indicate multiple statements
    # Simple check for semicolon outside strings
    # Replace single-quoted strings temporarily
    without_strings = re.sub(r"'[^']*'", "''", cleaned)
    if ";" in without_strings:
        raise SQLGuardError("Multiple statements are not permitted.")

    # Check first word: must be SELECT, WITH, or EXPLAIN
    first_token_match = re.match(r"^\s*([A-Za-z]+)", cleaned)
    if not first_token_match:
        raise SQLGuardError("Invalid query syntax.")

    first_token = first_token_match.group(1).upper()
    if first_token not in ("SELECT", "WITH", "EXPLAIN"):
        raise SQLGuardError(f"Only SELECT queries are permitted. Found: {first_token}")

    # Check for forbidden keywords in statement
    tokens = set(re.findall(r"\b[A-Za-z_]+\b", without_strings.upper()))
    intersection = tokens.intersection(FORBIDDEN_KEYWORDS)
    if intersection:
        raise SQLGuardError(f"Forbidden SQL keyword(s) detected: {', '.join(sorted(intersection))}")

    return cleaned

def create_secured_duckdb_connection(data_dir: str = "/data/parquet") -> duckdb.DuckDBPyConnection:
    """
    Initializes an in-memory DuckDB connection locked down to read-only directories
    with external network access completely disabled.
    """
    try:
        os.makedirs(data_dir, exist_ok=True)
    except OSError:
        pass
    try:
        os.makedirs("/tmp/analytics", exist_ok=True)
    except OSError:
        pass

    con = duckdb.connect(database=":memory:", read_only=False)

    threads = os.getenv("DUCKDB_THREADS", "2")
    memory_limit = os.getenv("DUCKDB_MEMORY_LIMIT", "2GB")

    con.execute(f"SET threads = {int(threads)};")
    con.execute(f"SET max_memory = '{memory_limit}';")
    con.execute(f"SET allowed_directories = ['{data_dir}', '/tmp/analytics'];")
    con.execute("SET enable_external_access = false;")
    con.execute("SET lock_configuration = true;")

    return con
