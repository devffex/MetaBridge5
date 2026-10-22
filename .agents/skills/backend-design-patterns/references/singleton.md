# Singleton Pattern

## 1. Overview & Purpose
The Singleton pattern restricts the instantiation of a class to a single object instance and provides a global access point to it. It ensures that coordinate operations across a system use exactly one shared state.

## 2. Backing App Scenarios
- **Database Connection Pools**: Managing a single coordinator instance to limit active database connections and reuse sockets.
- **Cache Clients**: Sharing a single instance of a Redis or Memcached connection client across HTTP workers.
- **Configuration Registries**: Storing application configuration variables loaded from `.env` files or remote configuration endpoints.

## 3. When to Apply
- When a single resource manager must control access to a shared physical resource.
- When creating multiple instances of a resource is computationally expensive or exhausts connection limits.

## 4. Drawbacks & Risks
- **Concurrency Bottlenecks**: Thread contention or lock acquisition delays under high request volumes.
- **Global State Pollution**: Introduces implicit dependencies, making unit testing difficult due to shared state persistence between test suites.
- **Concurrency Control**: Requires thread-safe initialization mechanisms (e.g., double-checked locking, static init blocks).

## 5. Language-Agnostic Design

```
Class SharedResourceCoordinator {
    private static instance: SharedResourceCoordinator
    private connectionPool: Pool

    private constructor() {
        this.connectionPool = InitializePool()
    }

    public static getInstance(): SharedResourceCoordinator {
        if (this.instance == null) {
            acquireLock()
            if (this.instance == null) {
                this.instance = new SharedResourceCoordinator()
            }
            releaseLock()
        }
        return this.instance
    }

    public query(sql: String): Result {
        return this.connectionPool.execute(sql)
    }
}
```

## 6. Decision Matrix

| Dimension | Singletons | Multiple Instances |
|---|---|---|
| **Resource Usage** | Optimized (Shared instance) | Expensive (Allocation per request) |
| **Testability** | Complex (Requires mocking global states) | Clean (Mockable via standard instances) |
| **State Mutation** | High risk of cross-request pollution | Isolated per execution path |
