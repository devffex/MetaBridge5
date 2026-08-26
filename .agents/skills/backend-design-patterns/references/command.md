# Command Pattern

## 1. Overview & Purpose
The Command pattern encapsulates a request as a standalone object containing all information about the request. This transformation lets you parameterize methods with different requests, delay or queue a request's execution, and support undoable operations.

## 2. Backing App Scenarios
- **Background Job Queues**: Serializing commands (e.g., SendReportCommand) and pushing them to Redis/Sidekiq/Celery to run asynchronously.
- **Transactional Rollbacks**: Maintaining a stack of commands with inverse operations to support manual transaction rollback structures.
- **REST Request Handlers**: Mapping endpoints to command objects (e.g., CreateUserCommand) to isolate validation and processing logic.

## 3. When to Apply
- When you want to queue operations, schedule execution, or trigger tasks asynchronously.
- When you want to decouple the object that triggers the operation from the one that knows how to perform it.
- When you need to implement a history of operations or supports transactional undo steps.

## 4. Drawbacks & Risks
- **Class Bloat**: Each specific request requires creating a separate concrete command class.
- **Serialization complexity**: If commands must span network boundaries (e.g. distributed queues), complex serialization and deserialization processes are required.

## 5. Language-Agnostic Design

```
Interface Command {
    execute(): Boolean
}

Class SendWelcomingEmailCommand implements Command {
    private emailService: EmailService
    private userEmail: String

    public constructor(service: EmailService, email: String) {
        this.emailService = service
        this.userEmail = email
    }

    public execute(): Boolean {
        return this.emailService.sendDirect(this.userEmail, "Welcome template")
    }
}

Class JobQueueManager {
    private queue: List<Command> = new List()

    public addJob(cmd: Command) {
        this.queue.add(cmd)
    }

    public processNextJob() {
        if (this.queue.size() > 0) {
            Command cmd = this.queue.popFirst()
            cmd.execute()
        }
    }
}
```

## 6. Decision Matrix

| Dimension | Command Object Encapsulation | Direct Function Invocation |
|---|---|---|
| **Scheduling** | Simple (Commands can be stored, queued, or run later) | Impossible (Functions execute immediately upon call) |
| **Cohesion** | High (All arguments and context remain inside the command object) | Low (Arguments must be passed across calling scopes) |
| **Boilerplate** | High (Requires interfaces and custom class definitions) | None (Immediate inline execution) |
