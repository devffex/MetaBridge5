# Factory / Abstract Factory

## 1. Overview & Purpose
The Factory pattern delegates the instantiation logic of objects to a dedicated creator. The Abstract Factory variant provides an interface for creating families of related or dependent objects without specifying their concrete classes.

## 2. Backing App Scenarios
- **Storage Engines**: Generating storage adapters (e.g., LocalStorage vs. AWSS3Storage) based on configuration files.
- **Database Adapters**: Instantiating appropriate connection adapters (Postgres, ClickHouse, SQLite) depending on the connection string.
- **Auth Strategies**: Constructing different login verifiers (OAuth, JWT, BasicAuth) based on request headers.

## 3. When to Apply
- When the exact type of objects the system needs to construct is unknown beforehand or depends on config values.
- When you want to decouple the object creation logic from client application code.
- When objects must be created in families or grouped together.

## 4. Drawbacks & Risks
- **Class Explosion**: Can lead to a high volume of factory classes and concrete implementations.
- **Added Complexity**: Introduces additional layers of abstraction, making the codebase harder to read for simple instantiation flows.

## 5. Language-Agnostic Design

```
Interface CacheStore {
    get(key: String): Object
    set(key: String, value: Object)
}

Class RedisStore implements CacheStore { ... }
Class InMemoryStore implements CacheStore { ... }

Class CacheStoreFactory {
    public static create(engineType: String): CacheStore {
        if (engineType == "redis") {
            return new RedisStore(Env.get("REDIS_URL"))
        }
        if (engineType == "memory") {
            return new InMemoryStore()
        }
        throw new InvalidEngineException("Unsupported engine: " + engineType)
    }
}
```

## 6. Decision Matrix

| Dimension | Factory Instantiation | Direct Instantiation |
|---|---|---|
| **Flexibility** | High (Easily swap engine implementations) | Low (Hardcoded dependency type) |
| **Code Readability** | Indirection makes code flow abstract | Straightforward, linear execution |
| **Scale Limits** | Clean abstraction as variant types grow | Code rot in caller files as variants grow |
