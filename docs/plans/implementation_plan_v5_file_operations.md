# Implementation Plan v5: File-Based Operations & Bulk Ingestion

## 1. Overview
This plan introduces high-bandwidth data capabilities to the PostgreSQL MCP server. It addresses the "Token Limit Bottleneck" by allowing agents to move large datasets in and out of the database using common file formats without exhausting the LLM's context window.

## 2. Supported Formats & Strategies

| Format | Export Strategy | Ingestion Strategy |
|--------|-----------------|--------------------|
| **CSV** | Node.js Stream (`fast-csv`) | PostgreSQL `COPY` command (Fastest) |
| **JSON** | Native PG `json_agg` to Stream | Node.js Streaming Parser to Batch Insert |
| **Parquet**| DuckDB CLI / Python Bridge | DuckDB to CSV/SQL Pipe |

### Why DuckDB for Parquet?
PostgreSQL does not support Parquet natively without complex extensions. DuckDB is a lightweight CLI tool that can read Parquet files and pipe them directly into PostgreSQL or convert them to CSV/SQL with extreme efficiency.

## 3. Tool Specifications

### A. `pg_export`
Generates a file from a query result.

**Parameters:**
- `sql`: The query to execute.
- `format`: `csv` | `json` | `parquet`.
- `session_id`: (Optional) Use to export uncommitted data.
- `options`: 
    - `filename`: Custom name for the file.
    - `delimiter`: (For CSV) Default `,`.

**Behavior:**
1. Execute query via the resolved executor.
2. Stream results to a file in the project's `exports/` directory.
3. Return a file path or a downloadable URL (if HTTP transport is active).

### B. `pg_import`
Ingests bulk data from a file into a table.

**Parameters:**
- `file_path`: Path to the local file.
- `target_table`: Name of the table to receive data.
- `format`: `csv` | `json` | `parquet`.
- `schema_mapping`: (Optional) Map file columns to table columns `{ "file_col": "db_col" }`.
- `autocommit`: (Boolean) Default `false`.

**Behavior:**
1. **Validation:** Check if the file exists and the `target_table` schema is compatible.
2. **Transformation:** Apply basic type casting or column renaming based on mapping.
3. **Execution:** Use `COPY FROM` for CSV or batch inserts for JSON.
4. **Error Handling:** Return a summary of successful rows vs. failed rows with specific error samples.

## 4. File Management & Security

### A. Secure Storage
- **Sandbox:** All file operations are restricted to a specific `data/` directory.
- **Path Sanitization:** Prevent directory traversal attacks (`../`) by validating all incoming paths.
- **Persistence:** Exported files will have a configurable TTL (default 24h) before automatic deletion.

### B. Ingestion API / Resources
- **MCP Resources:** Expose generated files as MCP resources (e.g., `pg://exports/data.csv`) so the LLM can "read" them back using the protocol's native capability if supported by the client.

## 5. Implementation Phases

### Phase 1: Infrastructure
- [ ] Create `data/exports` and `data/imports` directory structure.
- [ ] Implement path sanitization utility.
- [ ] Add DuckDB or a similar lightweight bridge for Parquet support.

### Phase 2: Export Tool
- [ ] Implement `pg_export` handler.
- [ ] Support CSV and JSON streaming.
- [ ] Add file metadata tracking (creation time, size).

### Phase 3: Import Tool & Validation
- [ ] Implement `pg_import` with native `COPY` support for CSV.
- [ ] Add schema validation logic (compare file headers to `information_schema.columns`).
- [ ] Implement partial failure reporting (don't fail the whole job on one bad row).

### Phase 4: Data Transformation
- [ ] Add column mapping logic.
- [ ] Implement basic casting (e.g., string to UUID, ISO-date to TIMESTAMP).

### Phase 5: Verification & Docs
- [ ] Test: Export 10,000 rows to CSV → Success.
- [ ] Test: Import CSV with mismatched columns → Catch Validation Error.
- [ ] Test: Directory traversal attempt → Block.
- [ ] README: Update with bulk data guide.

## 6. Success Metrics
1. **Zero Context Bloat:** Agents can process million-row tables without hitting token limits.
2. **Speed:** Bulk imports are at least 10x faster than individual `INSERT` statements.
3. **Safety:** No files can be read or written outside the designated sandbox.
