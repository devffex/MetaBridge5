# Builder Pattern

## 1. Overview & Purpose
The Builder pattern separates the construction of a complex object from its representation. This allows the same construction process to create different representations and prevents "telescoping constructors" (constructors with long parameter lists).

## 2. Backing App Scenarios
- **SQL Query Builders**: Generating complex queries with conditional `WHERE` clauses, joins, and ordering.
- **HTTP Client Requests**: Designing client calls with custom headers, query params, timeouts, and body payload structures.
- **Reporting Engines**: Constructing highly customized report layouts (e.g., CSV vs. PDF headers, aggregate settings).

## 3. When to Apply
- When an object requires several optional fields, configurations, or step-by-step construction processes.
- When you want to ensure constructed objects are immutable once complete.
- When parameter combinations must follow strict validation rules during build phase.

## 4. Drawbacks & Risks
- **Object Allocation overhead**: Requires creating helper builder instances, which increases memory allocation overhead.
- **Boilerplate**: Requires writing a parallel Builder class matching the target structure's fields.

## 5. Language-Agnostic Design

```
Class DatabaseQuery {
    private table: String
    private selections: List<String>
    private conditions: List<String>

    public constructor(builder: QueryBuilder) {
        this.table = builder.table
        this.selections = builder.selections
        this.conditions = builder.conditions
    }
}

Class QueryBuilder {
    public table: String
    public selections: List<String> = new List()
    public conditions: List<String> = new List()

    public fromTable(table: String): QueryBuilder {
        this.table = table
        return this
    }

    public select(column: String): QueryBuilder {
        this.selections.add(column)
        return this
    }

    public where(clause: String): QueryBuilder {
        this.conditions.add(clause)
        return this
    }

    public build(): DatabaseQuery {
        if (this.table == null) {
            throw new InvalidQueryException("Table must be set")
        }
        return new DatabaseQuery(this)
    }
}
```

## 6. Decision Matrix

| Dimension | Builder Pattern | Telescoping Constructor / Config Object |
|---|---|---|
| **API Usability** | Fluent API, self-describing steps | Heavy parameter signatures or nested maps |
| **Object Immutability** | Perfect (Build returns a final read-only entity) | Poor (Often requires setters on target class) |
| **Simple Objects** | Over-engineering, redundant files | Fast, simple implementation |
