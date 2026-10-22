# Repository Pattern

## 1. Overview & Purpose
The Repository pattern isolates the application's domain logic from the data mapping and persistence layers. It acts as an in-memory collection of domain objects, exposing query methods while hiding sql, no-sql, or api details.

## 2. Backing App Scenarios
- **ORM Independence**: Abstracting SQL queries (SQLAlchemy, Prisma, Hibernate) away from business controllers.
- **Microservice Migration**: Swapping database query endpoints with REST API client adapters without changing domain logic.
- **Local Testing**: Providing in-memory mock repository implementations for unit testing.

## 3. When to Apply
- When you want to reuse query logic across multiple services or endpoints.
- When you want to shield domain models from database table schemas.
- When you need to support multiple data sources (e.g. read replica database and memory cache).

## 4. Drawbacks & Risks
- **Anemic Models**: Repositories can easily turn into mere CRUD wrappers, adding redundant boilerplate code for simple database updates.
- **Query Optimization Limits**: High-performance database operations (such as fine-tuned SQL joins or native window functions) can be difficult to express through abstract repository interfaces.

## 5. Language-Agnostic Design

```
Interface UserRepository {
    fetchById(id: String): User
    save(user: User)
    delete(id: String)
}

Class DatabaseUserRepository implements UserRepository {
    private dbClient: DBConnection

    public fetchById(id: String): User {
        Row row = this.dbClient.query("SELECT * FROM users WHERE id = ?", id)
        return new User(row.get("id"), row.get("email"))
    }

    public save(user: User) {
        this.dbClient.execute("INSERT INTO users(id, email) VALUES(?, ?)", user.id, user.email)
    }
}
```

## 6. Decision Matrix

| Dimension | Repository Layer | Direct Database/ORM Queries |
|---|---|---|
| **Separation of Concerns** | High (Business logic knows nothing of database schemas) | Low (SQL scripts/ORM calls are mixed into business logic) |
| **Testing** | Simple (Mock repository interface directly) | Complex (Requires active database running or heavy ORM mocks) |
| **Boilerplate Code** | Higher (Needs interfaces, implementations, mappings) | Lower (Immediate execution of queries) |
