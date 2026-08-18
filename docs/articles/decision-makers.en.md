# Digitizing procedures without getting locked in: a third way

When an institution decides to digitize its formal procedures, the conversation usually narrows to two options. The first: buy a commercial BPM suite — expensive licenses, vendor consultants for every change, and a dependency that deepens over the years. The second: commission custom software — which solves today's process but ages badly, because every regulatory change again requires programmers touching the heart of the system.

There is a third way: **sinpapel** (Spanish for "paperless"), an open-source toolset designed specifically for case-processing and permit systems, built around one separation: what never changes (the engine) versus what changes all the time (the rules of each process).

## What your institution gets

**Complete traceability.** Every movement of every case file is immutably recorded: who did it, when, from where, with what justification and — where applicable — with which electronic signature. This is not an optional module someone can skip: the engine itself writes the record as part of the same operation. When an audit or a transparency request arrives, the evidence already exists.

**Legally meaningful electronic signature.** The system ships with support for Mexico's FIEL (the SAT's advanced electronic signature), so critical decisions — an approval, a rejection — can require the responsible official's cryptographically verified signature, bound to the case file. Other signature schemes can be plugged in where a procedure requires them.

**Rules that change without reprogramming.** The steps of a procedure, who may authorize what, the documents required at each stage, and the amounts or conditions that block a decision are not written into the code: they are configuration. When the regulation changes, a new version of the flow is published. And something auditors appreciate: cases opened under the previous rules keep their rules — the system knows exactly which regulation governed each file.

**Deadlines that enforce themselves.** Each stage carries a maximum time. When it expires, the system acts automatically: it notifies the person responsible, escalates the case to the next level, or resolves it the way your institution configures. Response times stop depending on someone checking an inbox.

**Documents that generate themselves.** Official letters, receipts and certificates are produced automatically from institutional templates, filled with the case data. Less manual capture, fewer errors, uniform formatting.

**Integration with what already exists.** The system notifies other systems in real time — payments, citizen notifications, institutional archives — through standard, secure mechanisms, instead of living in isolation.

**Visual process design.** Flows are drawn in a visual tool — boxes and arrows that the legal or compliance office can read and validate — and that diagram is what the system executes. The documented process and the real process are the same artifact.

## Cost, control and permanence

sinpapel is free software (GPL-3.0 license). That has three practical consequences:

- **No licensing cost.** The investment goes into implementation and into your own team, not into recurring per-user or per-process fees.
- **No vendor lock-in.** The code is public and auditable; any competent team can maintain, extend or audit it. If you change implementation partners, the system remains yours.
- **Verifiable transparency.** For a public institution, being able to demonstrate how its software decides is not a luxury — it is an obligation that open source turns into a verifiable fact.

## What adoption takes

Being realistic is part of the pitch. sinpapel is not a turnkey product that installs itself: it is the professional foundation on which a development team builds your institution's system — in weeks rather than years, and without reinventing the hard parts.

You need a team (in-house or contracted) experienced in Python/Django — one of the most widely available skill sets in the market — and a serious mapping of your processes, which is the most valuable part of any digitization effort anyway.

## The next step

The project, its documentation in Spanish and English, and all its components are publicly available at [github.com/aprendomx/sinpapel](https://github.com/aprendomx/sinpapel). A proof of concept on one real procedure — one of those that today takes weeks and nobody knows where it stands — is the best way to find out whether this third way is your institution's way.
