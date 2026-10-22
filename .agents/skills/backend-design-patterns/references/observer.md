# Observer (Publish-Subscribe) Pattern

## 1. Overview & Purpose
The Observer pattern defines a one-to-many dependency between objects. When one object (the Subject/Publisher) changes state, all its dependents (Observers/Subscribers) are notified and updated automatically.

## 2. Backing App Scenarios
- **Notification Services**: Dispatching emails, SMS notifications, and push messages when a new user registers.
- **Event-Driven Microservices**: Publishing messages to Kafka, RabbitMQ, or Redis Pub/Sub when a resource state shifts.
- **Audit Logging**: Appending tracking logs dynamically to security modules when sensitive database transactions occur.

## 3. When to Apply
- When a change to one object requires changing others, and the quantity of target objects is dynamic or unknown.
- When you want to decouple the event producer from event consumers.

## 4. Drawbacks & Risks
- **Memory Leaks**: If subscribers are not correctly deregistered, they can remain in memory causing leaks (especially in long-lived backend processes).
- **Notification Ordering**: Observers are notified in arbitrary order. If order is critical, the basic pattern fails.
- **Debugging Indoors**: Indirection makes tracking down the execution trace difficult during debugging.

## 5. Language-Agnostic Design

```
Interface EventSubscriber {
    onEvent(eventData: Map)
}

Class EmailNotifier implements EventSubscriber {
    public onEvent(eventData: Map) {
        // Send email notification
    }
}

Class AuditLogger implements EventSubscriber {
    public onEvent(eventData: Map) {
        // Append log to secure database
    }
}

Class OrderManager {
    private subscribers: List<EventSubscriber> = new List()

    public subscribe(sub: EventSubscriber) {
        this.subscribers.add(sub)
    }

    public completeOrder(orderId: String) {
        // Perform order processing...
        
        Map eventData = new Map()
        eventData.put("orderId", orderId)
        eventData.put("status", "completed")

        for (EventSubscriber sub : this.subscribers) {
            sub.onEvent(eventData)
        }
    }
}
```

## 6. Decision Matrix

| Dimension | Observer Pub/Sub | Direct Procedure Calls |
|---|---|---|
| **Coupling** | Loose (Manager does not know concrete subscriber types) | Tight (Manager is imports-dependent on notify services) |
| **Scalability** | Easy (Add new listeners without modifying event class) | Hard (Requires adding lines of code to event class) |
| **Execution Flow** | Async/Indirected (Harder to trace execution stack) | Synchronous, linear (Straightforward flow) |
