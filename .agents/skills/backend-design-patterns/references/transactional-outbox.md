# Transactional Outbox Pattern

## 1. Overview & Purpose
The Transactional Outbox pattern guarantees reliable messaging in distributed systems. Instead of publishing message events directly to a broker (e.g. Kafka, RabbitMQ) during a business transaction—which can fail if the broker is down—the event is written to an "outbox" database table within the same transaction, then dispatched asynchronously by a separate worker.

## 2. Backing App Scenarios
- **Event-Driven Microservices**: Ensuring that when an order is created, the `OrderCreated` event is published to the message bus without fail.
- **Audit Trails**: Guaranteeing security audit logs are dispatched to Elasticsearch even if the log server experiences temporary outages.

## 3. When to Apply
- When you need to achieve "at-least-once" delivery of message events triggered by database updates.
- When publishing to a message broker during a database transaction risks database connection hangs or partial transaction failure (due to broker latency/outages).

## 4. Drawbacks & Risks
- **Message Duplication**: Since the dispatcher worker retries on broker delivery failure, consumers must handle duplicate messages (idempotent consumers are required).
- **Latency**: Events are processed asynchronously, introducing a small propagation delay between database commits and broker publishing.
- **Database Load**: Adds write overhead to the main database and requires polling the outbox table or reading binlogs.

## 5. Language-Agnostic Design

```
// 1. Transactional Write Step (Application Code)
Class OrderService {
    private db: DatabaseConnection

    public createOrder(order: Order) {
        this.db.beginTransaction()
        try {
            this.db.execute("INSERT INTO orders ...")
            
            // Write event to the same database outbox table
            this.db.execute(
                "INSERT INTO outbox (id, event_type, payload, status) VALUES (?, ?, ?, 'PENDING')",
                generateUUID(), "OrderCreated", serialize(order)
            )
            this.db.commit()
        } catch (Exception ex) {
            this.db.rollback()
            throw ex
        }
    }
}

// 2. Message Dispatcher Step (Background Worker)
Class OutboxPublisher {
    private db: DatabaseConnection
    private broker: MessageBroker

    public publishPendingEvents() {
        List<OutboxEntry> pending = this.db.query("SELECT * FROM outbox WHERE status = 'PENDING' LIMIT 100")
        for (OutboxEntry entry : pending) {
            try {
                this.broker.publish(entry.eventType, entry.payload)
                this.db.execute("UPDATE outbox SET status = 'PROCESSED' WHERE id = ?", entry.id)
            } catch (Exception ex) {
                this.db.execute("UPDATE outbox SET status = 'FAILED' WHERE id = ?", entry.id)
            }
        }
    }
}
```

## 6. Decision Matrix

| Dimension | Transactional Outbox | Direct Publishing (Inline) |
|---|---|---|
| **Delivery Guarantee** | High (At-least-once, zero lost events) | Low (Events are lost if broker is down during database commit) |
| **Transaction Boundaries** | Clean (DB write is fully isolated from broker state) | Coupled (DB commit hangs if broker response is slow) |
| **Infrastructure Overhead** | High (Needs outbox table, polling worker, consumer idempotency) | Low (Direct, immediate network call) |
