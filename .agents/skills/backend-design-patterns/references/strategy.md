# Strategy Pattern

## 1. Overview & Purpose
The Strategy pattern defines a family of algorithms, encapsulates each one, and makes them interchangeable. Strategy lets the algorithm vary independently from clients that use it, enabling runtime selection of behavior.

## 2. Backing App Scenarios
- **Payment Processing**: Swapping concrete processors (Stripe, PayPal, Adyen) depending on the user's checkout selection.
- **Tax Calculation**: Applying different tax evaluation strategies (EU VAT, US Sales Tax, Canada GST) based on buyer location.
- **Data Exporting**: Formatting dataset dumps into different outputs (JSON, CSV, XML) based on query parameters.

## 3. When to Apply
- When a class has multiple conditional branches that select different versions of an algorithm (e.g., `if (country == "US") { ... } else if ...`).
- When you need different variants of an algorithm, and the client code should not be coupled to the implementation details of those variants.

## 4. Drawbacks & Risks
- **Client Awareness**: Clients must be aware of the different strategies to select the appropriate one.
- **Class Count**: Increases the overall number of classes/modules in the codebase.
- **Context Overhead**: Some strategies might not use all of the parameters passed by the calling context, leading to unused data attributes.

## 5. Language-Agnostic Design

```
Interface TaxStrategy {
    calculateTax(amount: Float): Float
}

Class USTaxStrategy implements TaxStrategy {
    public calculateTax(amount: Float): Float {
        return amount * 0.08 // Simple US sales tax mock
    }
}

Class EUTaxStrategy implements TaxStrategy {
    public calculateTax(amount: Float): Float {
        return amount * 0.20 // Simple EU VAT mock
    }
}

Class InvoiceCalculator {
    private strategy: TaxStrategy

    public constructor(strategy: TaxStrategy) {
        this.strategy = strategy
    }

    public calculateInvoiceTotal(subtotal: Float): Float {
        Float tax = this.strategy.calculateTax(subtotal)
        return subtotal + tax
    }
}
```

## 6. Decision Matrix

| Dimension | Strategy Injection | Inline Conditional Branches |
|---|---|---|
| **Extensibility** | Easy (Create new strategy class without changing core caller code) | Hard (Requires modifying core methods and conditionals) |
| **Testing** | Simple (Unit test each strategy in isolation) | Complex (Requires covering all nested path branches) |
| **Complexity** | Higher (Requires multiple classes and interfaces) | Lower (Single class with internal control blocks) |
