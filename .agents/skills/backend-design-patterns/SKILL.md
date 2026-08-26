---
name: backend-design-patterns
description: Use when choosing or implementing software design patterns for backend and backing services. Triggers on architectural decisions, pattern mentions, or design discussions.
tags: ["software-architecture", "design-patterns", "backend", "system-design"]
version: "1.0.0"
author: "Antigravity Pair"
created: "2026-06-22"
updated: "2026-06-22"
---

# Backend Design Patterns

Guidelines for selecting, assessing, and implementing language-agnostic software design patterns for backing applications and services.

## Using This Skill
When deciding on codebase architecture, refactoring service layers, or designing integrations with external backing resources, refer to the relevant pattern details below before implementation.

---

## Pattern Sitemap

### 1. Creational Patterns
Creational patterns abstract the instantiation process, decoupling the system from how its objects are created and composed.
- **Singleton**: [references/singleton.md](references/singleton.md) — For globally shared, single-instance resources (pools, client connections).
- **Dependency Injection**: [references/dependency-injection.md](references/dependency-injection.md) — For decoupling services from their dependencies at runtime.
- **Factory**: [references/factory.md](references/factory.md) — For dynamically instantiating implementations based on environment or settings.
- **Builder**: [references/builder.md](references/builder.md) — For constructing complex, multi-step entities, payloads, or queries.

### 2. Structural Patterns
Structural patterns organize classes and objects to form larger structures while keeping them flexible and efficient.
- **Adapter**: [references/adapter.md](references/adapter.md) — For wrapping external SDKs to match internal interfaces.
- **Facade**: [references/facade.md](references/facade.md) — For providing a unified, simplified interface to complex subsystems.
- **Proxy**: [references/proxy.md](references/proxy.md) — For intercepting calls to add cross-cutting concerns (lazy loading, logging, caching).
- **Decorator**: [references/decorator.md](references/decorator.md) — For dynamically wrapping objects to append behaviors (retries, logging, telemetry).

### 3. Behavioral Patterns
Behavioral patterns deal with algorithms and the assignment of responsibilities between objects.
- **Strategy**: [references/strategy.md](references/strategy.md) — For runtime algorithm selection (payment processors, tax calculators).
- **Observer (Pub/Sub)**: [references/observer.md](references/observer.md) — For event-driven communication and messaging.
- **Command**: [references/command.md](references/command.md) — For encapsulating actions as objects for scheduling and queues.
- **Chain of Responsibility**: [references/chain-of-responsibility.md](references/chain-of-responsibility.md) — For request processing middleware pipelines.
- **State**: [references/state.md](references/state.md) — For managing complex transaction lifecycle states.

### 4. Backing & System Architecture Patterns
System patterns orchestrate communication, storage boundaries, and reliability across distributed resources.
- **Repository**: [references/repository.md](references/repository.md) — For decoupling domain logic from data persistence mechanisms.
- **Unit of Work**: [references/unit-of-work.md](references/unit-of-work.md) — For grouping multiple repository actions into single transactional boundaries.
- **Circuit Breaker**: [references/circuit-breaker.md](references/circuit-breaker.md) — For preventing cascading failures when external services fail.
- **Bulkhead**: [references/bulkhead.md](references/bulkhead.md) — For isolating resource allocations per backing service to avoid complete system failure.
- **Transactional Outbox**: [references/transactional-outbox.md](references/transactional-outbox.md) — For reliable messaging via database-triggered outbox processing.
- **CQRS**: [references/cqrs.md](references/cqrs.md) — For splitting write commands and read queries into optimized paths.
