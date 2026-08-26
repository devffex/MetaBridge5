# Proxy Pattern

## 1. Overview & Purpose
The Proxy pattern provides a surrogate or placeholder for another object to control access to it. It intercepts calls to the original object to run logging, access control, caching, lazy initialization, or network redirection.

## 2. Backing App Scenarios
- **Caching Proxy**: Intercepting database queries; returning cached data if present, or executing the query and saving it to cache before returning.
- **Lazy Initializer**: Delaying the creation of heavy connections (e.g., third-party clients) until the client actually calls an execution method.
- **Access Control / Security Proxy**: Intercepting service requests to validate user session authorization before calling internal handlers.

## 3. When to Apply
- When a resource is expensive to instantiate or load, and you want to delay creation until it is accessed (Virtual Proxy).
- When access rules must be strictly enforced before invoking underlying service operations (Protection Proxy).
- When caching or logging is required without changing target class logic (Smart Reference).

## 4. Drawbacks & Risks
- **Execution Indirection**: Increases response latency slightly due to interception logic.
- **Complexity**: Adds duplicate structures, since the proxy must replicate the original target's complete interface.

## 5. Language-Agnostic Design

```
Interface DocumentRepository {
    fetchById(id: String): Document
}

Class DatabaseDocumentRepository implements DocumentRepository {
    public fetchById(id: String): Document {
        // Expensive SQL database query execution
    }
}

Class CachingDocumentProxy implements DocumentRepository {
    private realRepo: DatabaseDocumentRepository
    private cache: CacheClient

    public constructor(repo: DatabaseDocumentRepository, cache: CacheClient) {
        this.realRepo = repo
        this.cache = cache
    }

    public fetchById(id: String): Document {
        Document cachedDoc = this.cache.get(id)
        if (cachedDoc != null) {
            return cachedDoc
        }
        Document dbDoc = this.realRepo.fetchById(id)
        this.cache.set(id, dbDoc)
        return dbDoc
    }
}
```

## 6. Decision Matrix

| Dimension | Proxy Wrapper | Integrated Handler Logic |
|---|---|---|
| **Separation of Concerns** | High (Business logic is clean of caching/auth checks) | Low (Caching/auth logic is mixed into target code) |
| **Interface Maintenance** | High (Changing original class signature requires updating the proxy) | Low (Only target implementation updates) |
| **Run Overhead** | Minor wrapper redirection | Minimal raw call path |
