# "Where is my paperwork?" The open-source project that wants to kill that question

Everyone knows the scene. You hand in an application at a government counter — a permit, a license, a scholarship, a pension — and in exchange you get a file number and a vague promise: "it's being processed." Weeks later, nobody can tell you which desk your file is sleeping on, who has it, what it's missing, or why the legal deadline came and went without anything happening. Your paperwork enters a black box, and on your side of the counter all that's left is waiting.

That black box is not an inevitable flaw of bureaucracy. It is, to a large extent, a software problem. And a Mexican open-source project proposes to fix it at the root.

## A file that cannot get lost

It's called **sinpapel** — Spanish for "paperless" — and it isn't an app citizens download. It's something more foundational: the engine institutions can use to build their case-processing systems. Its premise is simple to state and demanding to honor: **every step of every file must be recorded in a way that nobody — not even the institution itself — can later erase or alter**.

In a system built on sinpapel, when an official receives, approves, rejects or forwards an application, the system automatically records who did it, when, and on what grounds. Important decisions additionally require the responsible official's electronic signature — in Mexico, the same e.firma (FIEL) millions of people already use with the tax authority — so that an "approved" or a "rejected" carries a name and cryptographic proof behind it.

The practical consequence: the question "where is my paperwork?" always has an answer. And the uncomfortable question — "who stopped it, and why?" — has one too.

## Deadlines that no longer run on goodwill

Almost every formal procedure has legal deadlines. Almost no system watches them. sinpapel turns them into automatic alarms: if a file sits too long on someone's desk, the system notifies the person responsible, alerts their superior, or flags the oversight office — on its own, without anyone having to remember. Where regulations allow it, it can even resolve the case the way the law prescribes when the authority fails to answer in time.

For the person doing the paperwork, that means something concrete: response times stop depending on insisting, on knowing somebody, or on being lucky.

## Rules out in the open

There's another detail that sets the project apart: it is free software. Its code is published on the internet for anyone to see, and institutions can use it without paying licenses. That matters for two reasons that go beyond the technical.

The first is public money: no expensive commercial suites to buy, no single vendor to be chained to for years.

The second runs deeper. When the software that decides on public procedures is itself public, anyone — a journalist, an auditor, a civil-society watchdog — can examine how it works. The rules of the procedure stop being a mystery of the counter and become, literally, verifiable. Even the processes themselves are designed as box-and-arrow diagrams that a lawyer or a citizen can read — and that same diagram is what the system executes. What's documented and what actually happens are the same thing.

## What it does — and what it doesn't

It's worth saying plainly: sinpapel doesn't eliminate procedures, doesn't make them automatic, and doesn't replace the officials who must decide them. A bad process, digitized, is still a bad process. What the project attacks is opacity: the impossibility of knowing, the ease of misplacing, the silent expiry of deadlines, the decision with no name attached.

Nor is it something a citizen can install: it's institutions — a ministry, a city government, a university — that must adopt it to build their systems. The project, fully documented, is publicly available at [github.com/aprendomx/sinpapel](https://github.com/aprendomx/sinpapel).

That's why the public's role isn't technical. It's simpler, and more powerful: knowing this exists, and demanding it. The next time a piece of paperwork disappears into the black box, it's worth remembering that the black box is now optional.
