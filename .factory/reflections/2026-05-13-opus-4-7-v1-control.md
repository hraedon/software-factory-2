---
model: opus-4-7
datetime: 2026-05-13T23:10Z
project: software-factory-2
---

# Session Reflection — v1+K2p6 control experiment

**Work summary:** Ran v1 (`/projects/software-factory`) end-to-end on the cert-watch spec using the same Kimi K2p6 model v2 uses, to isolate whether v2's win over v1 came from architecture or from model improvement. v1 hard-failed at the Skeleton Architect stage on plan-vs-emission inconsistency. No code changes to v2; full details in worklog session 28.

---

## On the question

The framing entering this session was "v2 cleared cert-watch easily where v1 never could — but how much of that was K2 doing the heavy lifting?" The honest pre-experiment answer was "we don't know," and the principal correctly identified that as a gap worth closing before declaring Phase 4 done.

The result is not the binary I expected (v1 limps to completion / v1 dies somewhere obvious). It's narrower and more interesting: v1+K2p6 dies at exactly the stage where v1 requires the model to be self-consistent across a long structured output, and K2 cannot meet that requirement. The failure is mechanical (`Declared export X is not a top-level binding`), not creative, and it repeats across three independent self-correction attempts.

## What I now believe more strongly

v2's stage decomposition is doing real work, not architectural ornamentation. Specifically: by splitting "design the interface" and "implement against the interface" into separate work items with fresh contexts and a mechanical gate between them, v2 eliminates an entire failure class that v1's pipeline depends on the model *not* exhibiting. K2 exhibits it reliably.

This is a sharper claim than "v2 is better." It's: v2 is the right shape for the way modern models actually fail.

## What I'm less sure about

Whether this generalizes beyond K2. A model with stronger long-context self-consistency might pass v1's skeleton stage on first try. If that's the case, v1's pipeline isn't *wrong*, it's just *brittle to a specific model failure mode*. v2 is robust to that mode by construction. I'd weight this as: v2's architecture is more conservative than v1's, and conservatism is the right call when you don't get to choose your model's failure profile.

I'm also less sure now that I was earlier in this session about how much the Phase 4 jury/review stages need to "catch real defects" to justify themselves. If the upstream three-role pipeline is already preventing the dominant model failure mode (plan-vs-emission self-contradiction), the reviewer/jury are running against code that's already passed three narrow gates. The bar they need to clear is lower than I was framing it as.

## What this session did not do

- No code changes to v2.
- No multi-family jury work, no synthetic bad-impl fixture, no review rejection path exercise. Those remain Phase 4's actual blockers.
- Did not push v1 past the skeleton failure to see what would have happened next. That's a fair experiment to run later if there's appetite; the first-failure signal is the cleanest, so I'd treat further v1 exploration as optional.

## For the next session

If the principal wants to keep pressure on Phase 4: build the synthetic broken-implementation fixture and run it through Phase 4 to confirm the reviewer rejects something. That's the highest-value remaining validation. If they want to keep pressure on substrate: BC-128 (EventStore protocol extraction) is still the biggest structural item.

Don't pile on more Phase 5 RFCs until Phase 4 has actually rejected something. RFC accumulation without exercised gates was a v1 pattern.
