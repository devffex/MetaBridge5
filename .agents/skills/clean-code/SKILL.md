---
name: "clean-code"
description: "Universal standards for code readability, maintainability, SOLID principles, and refactoring heuristics."
tags: ["software-engineering", "clean-code", "refactoring", "dry", "solid"]
version: "2.1.0"
author: "julio"
created: "2026-06-14"
updated: "2026-06-22"
---

# Clean Code & Core Design Principles

This skill enforces universal software craftsmanship and design principles across all languages and frameworks to ensure codebase readability, maintainability, and structural integrity.

## Purpose

Provide structured guidance for writing clear, semantic code, designing stable abstractions (SOLID & DRY), and managing error handling and refactoring workflows to prevent code rot.

## Activation Triggers

- Authoring new source files, modules, classes, functions, or UI components.
- Reviewing, refactoring, or optimizing existing code.
- Identifying code duplication, knowledge redundancy, or domain coupling.
- Decomposing large, monolithic classes or helper modules.

## Core Mandates

### 1. SOLID Design Principles

- **Single Responsibility (SRP)**: Every module, class, or function must have exactly one reason to change. Separate domain/business rules from infrastructure details (APIs, databases, UI).
- **Open/Closed (OCP)**: Entities should be open for extension but closed for modification. Leverage polymorphism, interfaces, and composition to add behavior without editing existing files.
- **Liskov Substitution (LSP)**: Subtypes must be completely substitutable for their base types. Avoid overriding base methods with empty implementations or throwing unexpected exceptions.
- **Interface Segregation (ISP)**: Clients should not be forced to depend on methods they do not use. Split fat interfaces into small, cohesive, client-specific contracts.
- **Dependency Inversion (DIP)**: Depend on abstractions, not concretions. Inject dependencies instead of hardcoding instances directly in the class constructor.

### 2. Don't Repeat Yourself (DRY)

Ensure every piece of business logic, configuration, or data schema has a single, authoritative representation within the system.

- **Logical Extraction**: Encapsulate duplicate code blocks into reusable functions, utilities, or components.
- **Parameterization**: Handle variation using inputs and arguments rather than copying blocks with minor modifications.
- **Rule of Three**: Avoid premature abstraction. Extract patterns only when they appear for the third time.

### 3. Function & Method Design

- **Smallness**: Functions must be short (ideally under 25 lines) and do exactly one thing.
- **Stepdown Rule**: Maintain a single level of abstraction per function. High-level orchestrators should call mid-level functions, which in turn call low-level library helpers. Do not mix business logic with raw parsing or string manipulation.
- **Low Arity (Arguments count)**: Limit arguments to 0-2 (niladic, monadic, dyadic). Avoid 3 (triadic). If 4 or more are needed (polyadic), group them into a configuration object or struct.
- **Command-Query Separation (CQS)**: A method should either perform an action (state change) or return data, but not both.
- **No Side Effects**: Eliminate hidden state updates. Pure functions should return new values instead of silently mutating inputs or global state.

### 4. Clean Error Handling & Null Safety

- **Use Exceptions or Typed Results**: Prefer throwing explicit exceptions or returning typed result wrappers (`Result`, `Either`, `Optional`) over returning error status codes.
- **No Null Propagation**: Never return `null` or `nil` from functions. Return empty collections, default Null Objects, or raise exceptions. Avoid passing `null` as a parameter.
- **Transactional Catch Blocks**: Keep try-catch structures clean by isolating block bodies. Extract the body of the `try` block and the `catch` handler into separate, named helper functions.

### 5. Refactoring & Code Smells

- **Boy Scout Rule**: Always leave the code cleaner than you found it. Improve small things (naming, formatting, small extractions) in every file you touch.
- **Primitive Obsession**: Encapsulate primitives in small, value-like types when they represent domain concepts (e.g., wrap a float in a `Money` class, a string in `EmailAddress`).
- **Feature Envy**: Relocate methods that are more interested in the data of another class than the class they reside in.
- **Dead Code Elimination**: Rigorously remove unused code, commented-out logic, dead comments, and exports to prevent noise.

### 6. Clean Testing (F.I.R.S.T.)

- **Fast**: Tests must execute quickly to encourage frequent runs.
- **Independent**: Tests must not depend on each other or run in a specific order.
- **Repeatable**: Tests must yield identical results in any environment (local, CI, production).
- **Self-Validating**: Tests must output a clear boolean pass/fail without manual log inspection.
- **Timely**: Write tests alongside production code (or beforehand).
- **Structure**: Follow the Arrange-Act-Assert (AAA) pattern to keep test files clean and readable.

## Implementation Guidelines & Workflows

### Refactoring DRY Abstractions

1. **Analyze**: Identify repeating logic clusters or code blocks in the workspace.
2. **Isolate**: Extract the shared core logic to a clean, stateless function/component.
3. **Generalize**: Add configuration parameters/props to support all original use cases.
4. **Integrate**: Replace original duplicate blocks with calls to the new utility.

### Abstraction Level Separation (Stepdown Rule)

1. **Identify Mixing**: Scan functions that mix business rules (e.g. `if (user.isPremium)`) with technical details (e.g. `const query = 'SELECT * FROM...'`).
2. **Extract Infrastructure**: Move technical details to dedicated data-access or helper functions.
3. **Refactor Orchestration**: Ensure the main function reads like high-level step-by-step instructions.

## Review Checklist

- [ ] Does this entity have more than one primary objective? (SRP)
- [ ] Can the class or module be extended with new behavior without modifying its source code? (OCP)
- [ ] Is the function small (<25 lines) and focused on a single level of abstraction? (Stepdown Rule)
- [ ] Are parameter counts low (0-2)? If not, can they be grouped? (Arity)
- [ ] Does this function return null or magic error codes? (Null Safety)
- [ ] Are we leaving the modified files cleaner than we found them? (Boy Scout Rule)
- [ ] Do variable and function names express "why" they exist and "what" they represent?
- [ ] Are comments restricted to describing non-obvious "why" decisions rather than restating code behavior?

## Constraints

- Never duplicate business rules, data schemas, or system configurations.
- Do not let presentation or data-fetching logic leak into core domain business rules.
- Do not over-abstract; prioritize readability and simplicity over premature optimization.
- Never commit commented-out code; rely on git for history tracking.
