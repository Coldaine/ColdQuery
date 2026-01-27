# Contributing to ColdQuery

Thank you for your interest in contributing to ColdQuery! This document provides guidelines for contributing to the project.

## Code of Conduct

- Be respectful and collaborative
- Assume good intentions
- Focus on constructive feedback
- Help others learn and grow

## How to Contribute

### Reporting Issues

1. **Search existing issues** first to avoid duplicates
2. **Use the issue template** when available
3. **Include reproduction steps** for bugs
4. **Provide environment details** (Node.js version, OS, PostgreSQL version)

### Feature Requests

1. Open an issue describing the feature
2. Explain the use case and motivation
3. Discuss potential implementation approaches
4. Wait for feedback before implementing

### Submitting Pull Requests

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/my-feature
   ```
3. **Make changes** following the code standards
4. **Write or update tests** for your changes
5. **Update documentation** if needed
6. **Run the full test suite**
   ```bash
   npm run check && npm run test:ci
   ```
7. **Commit with conventional commits**
   ```bash
   git commit -m "feat: add new capability"
   ```
8. **Push and create pull request**

## Development Setup

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for detailed setup instructions.

Quick start:
```bash
git clone https://github.com/Coldaine/ColdQuery.git
cd ColdQuery
npm install
npm run build
docker compose up -d
npm test
```

## Pull Request Process

### Before Submitting

1. **Ensure tests pass**: `npm run test:ci`
2. **Ensure type checking passes**: `npm run typecheck`
3. **Ensure linting passes**: `npm run lint`
4. **Update CHANGELOG.md** with your changes

### PR Requirements

- Clear title describing the change
- Description of what changed and why
- Link to related issue(s) if applicable
- Tests for new functionality
- Documentation updates if needed

### Review Process

1. Maintainers will review your PR
2. Address any feedback
3. Once approved, maintainers will merge
4. Squash commits before merge if needed

## Code Standards

### TypeScript

- **Strict mode**: All code must pass TypeScript strict checks
- **No implicit any**: Use explicit types
- **Document complex logic**: Add comments explaining "why"

### Testing

- **Test new features**: 100% coverage for new code is expected
- **Test edge cases**: Include error conditions
- **Use descriptive test names**: Describe the behavior being tested

### Documentation

- **Every tool must have a description file** in `docs/toolDescriptions/`
- **Update TOOL_REFERENCE.md** for schema changes
- **Add examples** for new features
- **Keep README.md concise** - link to detailed docs

### Security

- **Follow Default-Deny policy** for write operations
- **Never trust user input** - validate and sanitize
- **Use parameterized queries** - never string concatenation
- **No secrets in code** - use environment variables

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `style` | Code style changes (formatting) |
| `refactor` | Code refactoring |
| `test` | Adding or updating tests |
| `chore` | Maintenance tasks |
| `perf` | Performance improvements |

### Examples

```bash
feat(pg_query): add EXPLAIN ANALYZE support
fix(session): prevent memory leak on timeout
docs(readme): add quick start guide
test(pg_tx): add savepoint edge case tests
```

### Rules

- First line under 72 characters
- Reference issues: `fix: resolve #123`
- Use imperative mood: "add" not "added"

## Adding New Tools

When adding a new tool:

1. **Create action handlers** in `packages/core/src/actions/<tool>/`
2. **Create tool definition** in `packages/core/src/tools/`
3. **Register in server.ts** (add to tools array)
4. **Write comprehensive tests**
5. **Create documentation** in `docs/toolDescriptions/`
6. **Update TOOL_REFERENCE.md** with schema

### Tool Structure

```typescript
// packages/core/src/tools/pg-example.ts
export const pgExampleTool: ToolDefinition = {
  name: "pg_example",
  config: {
    description: `Description for LLM...`,
    inputSchema: ExampleSchema,
    readOnlyHint: true, // or destructiveHint: true
  },
  handler: (context) => (params) => handler(params, context),
};
```

### Required Documentation

```markdown
<!-- docs/toolDescriptions/pg_example.md -->
# Tool: pg_example

## Purpose
[What this tool does]

## Safety Considerations
[Default-Deny policy, restrictions]

## Parameters
[Detailed parameter docs]

## Examples
[Real-world usage with JSON]

## Error Handling
[Common errors and solutions]
```

## Questions?

- Open an issue for questions about contributing
- Tag maintainers if urgent
- Join discussions in existing issues/PRs

Thank you for contributing to ColdQuery!
