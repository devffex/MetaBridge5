# Unit of Work Pattern

## 1. Overview & Purpose
The Unit of Work pattern maintains a list of business transactions. It tracks all updates, creations, and deletions during a single transaction lifecycle, then commits all changes to the database at once.

## 2. Backing App Scenarios
- **Multi-Repository Updates**: Modifying `UserRepository` and `InventoryRepository` in a single transaction during account registration.
- **Batch Processing**: Grouping a sequence of operations into a single atomic commit to minimize database network round trips.
- **Rollback Operations**: Ensuring that if one operation fails in a workflow (e.g., inventory update fails after payment), all previous changes are rolled back.

## 3. When to Apply
- When multiple database queries or updates must succeed or fail together as a single atomic transaction.
- When you want to minimize open connection times by queuing operations locally and committing them in a single batch.

## 4. Drawbacks & Risks
- **Concurrency Locks**: Stalling database engines if transactions remain open too long due to slow non-database tasks (e.g. calling an external API inside the transaction).
- **Complexity**: Managing state changes (new, dirty, clean, deleted) in application memory before saving requires a robust management library or implementation.

## 5. Language-Agnostic Design

```
Class UnitOfWork {
    private dbTransaction: Transaction
    private pendingUpdates: List<Entity> = new List()

    public registerDirty(entity: Entity) {
        this.pendingUpdates.add(entity)
    }

    public commit() {
        this.dbTransaction.begin()
        try {
            for (Entity entity : this.pendingUpdates) {
                // Determine save strategy per repository
                saveToDatabase(entity, this.dbTransaction)
            }
            this.dbTransaction.commit()
            this.pendingUpdates.clear()
        } catch (Exception ex) {
            this.dbTransaction.rollback()
            throw ex
        }
    }
}
```

## 6. Decision Matrix

| Dimension | Unit of Work | Manual Database Commits |
|---|---|---|
| **Atomicity** | High (Guaranteed single transactional block commit) | Low (Risk of partial updates on system failures) |
| **Connection Usage** | Efficient (Database connections are occupied briefly during commit) | Inefficient (Hold database connections open during execution steps) |
| **Logic Overhead** | High (Requires tracking changes in application memory) | Low (Execute queries immediately) |
