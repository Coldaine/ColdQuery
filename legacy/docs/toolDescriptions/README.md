# Tool Descriptions Documentation

This folder contains detailed documentation for all MCP tool descriptions used in this project. **Every `.describe()` field in our Zod schemas must be documented and justified here.**

## Why This Matters

Tool descriptions are the primary interface between our MCP server and LLM agents. Poor descriptions lead to:
- Misuse of tools (wrong parameters, wrong context)
- Silent failures (LLM doesn't understand requirements)
- Wasted tokens (verbose or unclear descriptions)
- Security issues (LLM doesn't understand constraints)

Good descriptions lead to:
- Correct tool selection
- Proper parameter usage
- Clear error recovery paths
- Predictable agent behavior

## Documentation Structure

Each tool should have a file in this folder:

```
toolDescriptions/
├── README.md (this file)
├── pg_tx.md
├── pg_query.md
├── pg_schema.md
└── pg_admin.md
```

## Required Sections Per Tool

Each tool documentation file must include:

### 1. Tool Overview
- What the tool does
- When to use it vs alternatives

### 2. Parameter Descriptions
For each parameter with a `.describe()`:

```markdown
#### `parameter_name`
- **Current description:** "The exact text in .describe()"
- **Justification:** Why this wording was chosen
- **Alternatives considered:** Other phrasings we tried
- **LLM behavior observed:** How LLMs respond to this description
```

### 3. Error Messages
Document all error messages and their intended effect on LLM behavior.

### 4. Examples
Show example tool calls and expected LLM reasoning.

## Principles for Writing Descriptions

### Be Prescriptive, Not Descriptive
```
BAD:  "An optional session ID"
GOOD: "Transaction session ID from pg_tx 'begin'. Required for transactional writes."
```

### Include Examples in Descriptions
```
BAD:  "Set to true for autocommit"
GOOD: "Set to true for single-statement writes. Example: { sql: 'INSERT...', autocommit: true }"
```

### State Requirements Explicitly
```
BAD:  "Session ID for the transaction"
GOOD: "REQUIRED for commit, rollback, savepoint, release. Use the ID returned by 'begin'."
```

### Guide Tool Selection
```
BAD:  "Execute SQL"
GOOD: "Execute a READ-ONLY query. For writes, use pg_query with action: 'write'."
```

## Testing Descriptions

Before finalizing any description:

1. **Test with multiple LLMs** - Claude, GPT-4, Gemini may interpret differently
2. **Test edge cases** - What happens when the LLM is confused?
3. **Test in context** - Does the description work when the LLM has many tools available?
4. **Document failures** - If an LLM misuses the tool, update the description

## Change Log

When modifying any tool description:

1. Document the change in git commit
2. Update the justification in this folder
3. Note any observed behavior changes
