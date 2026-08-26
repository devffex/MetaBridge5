# State Pattern

## 1. Overview & Purpose
The State pattern allows an object to alter its behavior when its internal state changes. The object will appear to change its class, isolating state-specific behavior into individual, interchangeable classes.

## 2. Backing App Scenarios
- **Order Lifecycle**: Moving an order through Pending -> Paid -> Shipped -> Delivered, where transitions control payment capture and shipment APIs.
- **Subscription Engine**: Handling active, past-due, suspended, and canceled subscriptions, routing features depending on subscription state.
- **TCP Connection Managers**: Simulating connection states (Closed, Listen, SynSent, Established) and defining valid operations per state.

## 3. When to Apply
- When an object's behavior depends on its state, and its operations contain complex, nested conditional statements reflecting state-specific branches.
- When you want to decouple state-transition rules from the context object.
- When state transitions are frequent and govern strict validation laws (e.g., you cannot "Ship" an order that is "Canceled").

## 4. Drawbacks & Risks
- **Class Count Overhead**: If a system has many minor states, writing a class for each state leads to significant file overhead.
- **Transition Coupling**: State classes must refer to each other or to the context object to transition, creating tight coupling between the state classes.

## 5. Language-Agnostic Design

```
Interface OrderState {
    pay(order: OrderContext)
    ship(order: OrderContext)
}

Class PaidState implements OrderState {
    public pay(order: OrderContext) {
        throw new IllegalStateException("Already paid")
    }

    public ship(order: OrderContext) {
        order.setShipmentDetails()
        order.setState(new ShippedState())
    }
}

Class PendingState implements OrderState {
    public pay(order: OrderContext) {
        order.executePayment()
        order.setState(new PaidState())
    }

    public ship(order: OrderContext) {
        throw new IllegalStateException("Cannot ship unpaid order")
    }
}

Class OrderContext {
    private currentState: OrderState

    public constructor() {
        this.currentState = new PendingState()
    }

    public setState(state: OrderState) {
        this.currentState = state
    }

    public pay() {
        this.currentState.pay(this)
    }

    public ship() {
        this.currentState.ship(this)
    }
}
```

## 6. Decision Matrix

| Dimension | State Pattern | Enumerated State Switch Blocks |
|---|---|---|
| **State Bloat** | Isolates state operations into separate files | Packs everything inside a single monolithic class |
| **Transition Safety** | Safe (Each class controls valid transitions directly) | Error-prone (Requires complex if/else check loops) |
| **Setup Cost** | Higher (Multiple classes, constructors, interfaces) | Lower (Single enum + switch block) |
