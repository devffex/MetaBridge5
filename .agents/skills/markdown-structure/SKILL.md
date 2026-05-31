---
name: markdown-structure
description: Guidelines for embedding code, mathematical notation, and visual diagrams into markdown documentation to ensure clarity and technical precision.
---

# Human Topic Document Meta-Spec

Purpose: define meta-instructions that enable agents to self-generate task-specific topic documentation for human execution.

## Core Objective

- Convert a task request into a clear, complete, and easy-to-follow topic document.
- Optimize for human understanding and execution, not agent parsing only.
- Preserve deterministic structure so output remains consistent across contributors.

## Processing Rules

### Clarity First

- Use plain language and short sentences.
- Expand jargon on first mention.
- Explain what to do and why it matters.

### Deterministic Structure

- Enforce exactly one level-1 heading as the single topic root.
- Use only level-2 headings for sections; no headings below level-2.
- Use bold inline dividers for internal grouping instead of deeper headings.

### Content Composition Constraints

- Write content as paragraphs only.
- Do not use lists, tables, or checklist formatting inside topic documents generated from this standard.
- Keep one focused idea per paragraph and split mixed paragraphs.
- Incorporate technical formatting elements to enhance clarity. Use inline code for referencing syntax or variables like `const example = true`. Use standard code blocks for multi-line implementation details as shown in the example block below.

```javascript
// Example implementation of a functional requirement
function executeTask(input) {
  return input ? "Success" : "Blocked";
}
```

- Utilize mathematical notation for technical specifications. Inline math should be represented using KaTeX syntax, such as the efficiency variable $E = mc^2$. For more complex logic or derivations, use standalone math blocks:

$$\text{Total Complexity} = \sum_{i=1}^{n} \text{Task}_i \times \text{Difficulty}_i$$

- Embed flow visualization using Mermaid diagrams when describing complex processes to improve user comprehension of conditional logic paths.

### Output Contract

- Always emit Human Topic Markdown in English by default.
- Include purpose, constraints, conditional logic, validation, and completion criteria.
- Keep instructions executable without requiring human reinterpretation.

## Logic Template

- `IF` requirement is ambiguous `THEN` choose the simplest implementation that satisfies explicit scope and state assumptions.
- `IF` missing context blocks execution `THEN` emit a `Blocked` note with exact missing input.
- `IF` implementation changes user-facing behavior `THEN` include a quick regression check.

## Example Intent Mapping

Input task: document a `Share Button` implementation in a Next.js application.

Expected behavior of the agent:

- Generate a human-focused topic document using this structure.
- Explain where the button is added, how it behaves, and why the behavior is correct.
- Provide deterministic validation and regression steps that a human can execute directly.

## Quality Gates

- No undefined terms or unexplained jargon.
- No heading depth violations.
- No lists, tables, or checklist artifacts in generated topic documents.
- No skipped validation, completion, or blocked-state handling.
