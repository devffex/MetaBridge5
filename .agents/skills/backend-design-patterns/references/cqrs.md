# CQRS (Command Query Responsibility Segregation)

## 1. Overview & Purpose
CQRS splits application read operations (Queries) from write operations (Commands) into separate logical models. This separation allows read and write pathways to be scaled, optimized, and modeled independently.

## 2. Backing App Scenarios
- **Complex Reporting**: Serving slow aggregate analytics dashboards from a read-optimized replica while handling fast write requests on the primary database.
- **High-Throughput APIs**: Directing search APIs to Elasticsearch or Redis read-caches while routing modifications to relational databases.

## 3. When to Apply
- When read operations have vastly different scaling and performance requirements than write operations (e.g. read-to-write ratios of 100:1).
- When query logic requires complex joins, search capability, or data denormalization that slows down transaction processing.
- When working with Event Sourcing systems.

## 4. Drawbacks & Risks
- **Eventual Consistency**: If the read database is updated asynchronously (via database replicas or outbox events), read queries might return stale data for a brief window.
- **System Overhead**: Requires maintaining distinct models, APIs, and often multiple databases (e.g., PostgreSQL for writes, Elasticsearch for reads), significantly increasing infrastructure complexity.

## 5. Language-Agnostic Design

```
// 1. Command Side (Write Path)
Class CreateUserCommand {
    public email: String
    public age: Integer
}

Class UserCommandHandler {
    private writeDb: PrimaryDatabase

    public handle(cmd: CreateUserCommand) {
        this.writeDb.execute("INSERT INTO users ...")
        // Publish update event to sync read database
    }
}

// 2. Query Side (Read Path)
Class ActiveUserQuery {
    public minAge: Integer
}

Class UserQueryHandler {
    private readDb: ReadReplicaOrSearchEngine

    public handle(query: ActiveUserQuery): List<UserView> {
        // Query read-optimized index or view directly
        return this.readDb.query("SELECT id, email FROM users WHERE age >= ?", query.minAge)
    }
}
```

## 6. Decision Matrix

| Dimension | CQRS Architecture | Unified CRUD Model |
|---|---|---|
| **Performance Scaling** | High (Optimize read replicas, caching, and schemas separately) | Low (Write locks and schema constraints impact read speeds) |
| **Consistency** | Eventual consistency (propagation delays) | Strong consistency (immediate read-after-write) |
| **Code Complexity** | High (Separate models, handlers, databases, and pipelines) | Low (Single repository, standard CRUD workflows) |
