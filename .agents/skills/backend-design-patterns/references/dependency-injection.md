# Dependency Injection (DI)

## 1. Overview & Purpose
Dependency Injection decouples a class from its dependencies by passing (injecting) required services at creation time rather than allowing the class to instantiate them internally. This implements the Dependency Inversion Principle (DIP).

## 2. Backing App Scenarios
- **Injecting Repositories**: Providing a controller/service with database repository abstractions.
- **Mocking External APIs**: Supplying HTTP clients (e.g., Stripe service client) during local development or unit testing.
- **Swapping Notification Channels**: Injecting different notifier instances (e.g., EmailNotifier, SlackNotifier) depending on config settings.

## 3. When to Apply
- When a class depends on multiple external systems or concrete services.
- When unit testing requires mocking out side-effect-heavy backing services.
- When dependency configuration varies by deployment environment (dev, staging, prod).

## 4. Drawbacks & Risks
- **Boilerplate Overhead**: Requires writing registration code or configuring container files.
- **Obfuscated Flow**: Finding the exact runtime implementation can be difficult due to abstract contracts.
- **Startup Latency**: Large DI container resolution graphs can slow down application start times.

## 5. Language-Agnostic Design

```
Interface MessageSender {
    send(recipient: String, body: String): Boolean
}

Class SMSClient implements MessageSender {
    public send(recipient: String, body: String): Boolean {
        // Concrete SMS Gateway integration
    }
}

Class UserRegistrationService {
    private sender: MessageSender

    // Dependency is injected via constructor
    public constructor(sender: MessageSender) {
        this.sender = sender
    }

    public registerUser(user: User) {
        saveUser(user)
        this.sender.send(user.phone, "Welcome!")
    }
}
```

## 6. Decision Matrix

| Dimension | Constructor/Property Injection | In-Line Instantiation |
|---|---|---|
| **Coupling** | Loose (Depends on interfaces) | Tight (Depends on concrete classes) |
| **Testability** | High (Easily mock dependencies) | Low (Requires complex stubbing/override) |
| **Setup Cost** | Medium (Requires container setup) | Low (Immediate creation) |
