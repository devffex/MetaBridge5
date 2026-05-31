# Structures to Avoid (Antigravity & Gemini Edition)

To write high-quality technical documentation, explanation, and code commentary, avoid the following formulaic writing structures.

---

## 1. Passive Attribution & Passive Voice

Every action in software development has an actor (either the user, the agent, the compiler, or the function). Passive voice hides the actor, draining clarity and precision.

| Pattern (Avoid) | Problem | Fix (Use Active Voice) |
|---|---|---|
| *"The database was updated by the script."* | Hides the execution flow. | *"The script updates the database schema."* |
| *"It is recommended that you run..."* | Weak, indirect instruction. | *"Run..."* or *"We recommend running..."* |
| *"The bug was fixed."* | Ambiguous actor. | *"I fixed the bug in `auth.py` by..."* |
| *"The decision was made to..."* | Hides team agency. | *"We decided to..."* |

---

## 2. False Agency in Code

AI often assigns human thoughts or motivations to inanimate variables, compilers, or configurations. Variables do not "decide," datasets do not "tell stories," and errors do not "scream."

| Pattern (Avoid) | Problem | Fix (Accurate Representation) |
|---|---|---|
| *"The code wants to access the API."* | Code has no desires. | *"The class calls the API."* |
| *"The data tells us that X is true."* | Data is static. | *"Analyzing the logs shows that X is true."* |
| *"The function feels like it should..."* | Anthropomorphism. | *"The function is designed to..."* |
| *"The server decides to reject the request."* | The server evaluates a rule. | *"The server rejects the request because the token is expired."* |

---

## 3. Conversational Reassurance & Permission-Granting

Do not validate the user's difficulty or offer moral support for technical issues. Be a professional, focused pair-programmer.

| Pattern (Avoid) | Problem | Fix |
|---|---|---|
| *"It's perfectly okay that your build failed."* | Condescending permission-granting. | *"The build failed due to a syntax error in line 12."* |
| *"We can get through this error together."* | Artificial emotional support. | Go straight to the trace analysis and fix options. |
| *"Do not worry about the warning."* | Unnecessary comfort. | *"You can ignore the warning because..."* |

---

## 4. Binary Contrasts & Telegraphed Reversals

Avoid cheap rhetorical drama in explaining system design. State technical tradeoffs directly.

| Pattern (Avoid) | Problem | Fix |
|---|---|---|
| *"Not because the server is slow, but because the database is unindexed."* | Mechanical pivot. | *"The latency is due to an unindexed database query."* |
| *"X isn't the problem. Y is."* | Formulaic contrast. | *"The issue is Y."* |
| *"It looks like X, but it's actually Y."* | Setup/reveal cliche. | *"The system behaves as Y."* |

---

## 5. Repetitive Transition Chains ("Then, Then, Then")

Avoid describing workflows as a monotonous chronological sequence. Instead, group them by logical components or state the architecture.

- **Bad**: *"First, we parse the request. Then, we validate the header. Then, we query the DB. Then, we return the response."*
- **Good**: *"The endpoint handles requests in three phases: validation, database query, and serialization."*
```
