# Decorator Pattern

## 1. Overview & Purpose
The Decorator pattern attaches additional responsibilities to an object dynamically. Decorators provide a flexible alternative to subclassing for extending functionality without modifying the original class source code.

## 2. Backing App Scenarios
- **Retry Mechanisms**: Wrapping database operations or external API client calls to retry operations on transient network failures.
- **Telemetry & Tracing**: Wrapping repository queries with timers to emit performance data to Datadog or OpenTelemetry.
- **Payload Encryption**: Wrapping storage writers to transparently encrypt files before sending them to disk or S3.

## 3. When to Apply
- When you want to add behaviors to individual objects at runtime without affecting other instances.
- When subclassing leads to an explosion of classes to support every combination of behaviors (e.g., `CachedEncryptedRepository`, `RetryingCachedRepository`).
- When cross-cutting concerns (retries, logging, metric aggregation) must remain decoupled from target business logic.

## 4. Drawbacks & Risks
- **Object Wrappers**: Creates a chain of small nested objects, which can make stack trace debugging difficult.
- **Order Dependency**: The order in which decorators are wrapped matters (e.g., caching should run *before* retrying, encryption must occur *before* writing).

## 5. Language-Agnostic Design

```
Interface CloudWriter {
    write(path: String, data: Bytes)
}

Class BasicCloudWriter implements CloudWriter {
    public write(path: String, data: Bytes) {
        // Concrete storage upload logic
    }
}

// Decorator base class
Abstract Class CloudWriterDecorator implements CloudWriter {
    protected wrapped: CloudWriter

    public constructor(writer: CloudWriter) {
        this.wrapped = writer
    }

    public write(path: String, data: Bytes) {
        this.wrapped.write(path, data)
    }
}

// Concrete Decorator
Class RetryingCloudWriter extends CloudWriterDecorator {
    public write(path: String, data: Bytes) {
        Integer attempts = 0
        while (attempts < 3) {
            try {
                this.wrapped.write(path, data)
                return
            } catch (TransientException ex) {
                attempts++
                if (attempts >= 3) throw ex
            }
        }
    }
}
```

## 6. Decision Matrix

| Dimension | Decorator Composition | Subclass Inheritance |
|---|---|---|
| **Flexibility** | High (Mix and match wrappers at runtime) | Low (Fixed design at compilation time) |
| **Code Isolation** | High (Each decorator handles one concern) | Low (Base features are coupled in class hierarchies) |
| **Complexity** | Medium (Requires managing nested object graphs) | Low (Standard class inheritance structure) |
