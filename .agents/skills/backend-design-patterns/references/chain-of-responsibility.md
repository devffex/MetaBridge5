# Chain of Responsibility

## 1. Overview & Purpose
The Chain of Responsibility pattern passes requests along a handler chain. Upon receiving a request, each handler decides either to process it or to pass it to the next handler in the chain.

## 2. Backing App Scenarios
- **HTTP Middleware Pipelines**: Processing incoming HTTP requests through Logging -> CORS -> Authentication -> Rate Limiting -> Request Handler.
- **Form Data Validation**: Validating user input through consecutive checkers (e.g., SchemaValidator -> BusinessRulesValidator -> DatabaseUniquenessValidator).
- **Security Scanners**: Analyzing file uploads through a series of virus scanners, size limits, and type checkers.

## 3. When to Apply
- When more than one handler can process a request, and you want the exact handler to be determined dynamically at runtime.
- When you want to issue a request to one of several objects without specifying the receiver explicitly.
- When the set of handlers and their execution order should be configurable at runtime.

## 4. Drawbacks & Risks
- **Unreachable End**: If no handler processes the request or routes it to the end, the request can drop silently without notification.
- **Latency**: Long pipelines can impact API latency if each node adds processing overhead.
- **Debugging Complexity**: Tracking control flow across multiple nested handlers is difficult.

## 5. Language-Agnostic Design

```
Abstract Class MiddlewareHandler {
    private next: MiddlewareHandler

    public setNext(handler: MiddlewareHandler): MiddlewareHandler {
        this.next = handler
        return handler
    }

    public handle(request: HTTPRequest): HTTPResponse {
        if (this.next != null) {
            return this.next.handle(request)
        }
        return new HTTPResponse(200, "OK")
    }
}

Class AuthMiddleware extends MiddlewareHandler {
    public handle(request: HTTPRequest): HTTPResponse {
        if (request.headers.get("Authorization") == null) {
            return new HTTPResponse(401, "Unauthorized")
        }
        return super.handle(request)
    }
}

Class RateLimitingMiddleware extends MiddlewareHandler {
    public handle(request: HTTPRequest): HTTPResponse {
        if (isRateLimited(request.ip)) {
            return new HTTPResponse(429, "Too Many Requests")
        }
        return super.handle(request)
    }
}
```

## 6. Decision Matrix

| Dimension | Middleware Chain | Monolithic Handler Function |
|---|---|---|
| **SRP Compliance** | Perfect (Each handler isolates one check/concern) | Poor (Single function holds all validation, auth, logic) |
| **Execution Flexibility** | Dynamic (Reorder or insert steps at runtime) | Fixed (Execution sequence is hardcoded) |
| **Traceability** | Complex (Requests pass through multiple scopes) | Simple (Linear execution trace) |
