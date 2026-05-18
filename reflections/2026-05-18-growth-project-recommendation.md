# Growth project recommendation — for plm@hraedon.com

*Written 2026-05-18 by an agent reviewing the public footprint at github.com/hraedon and blog.hraedon.com against the in-flight work in sf2/substrate/v1/Socratic-spec.*

## The read

You are a hybrid-infra senior IC who has, in the last cycle, built serious agentic-AI orchestration scaffolding (sf2, substrate, v1, Socratic-spec). You write opinionated practitioner essays. You make your own scope and phasing calls. Python and PowerShell are your hands; AD, certs, NetBox, K8s, UniFi are your domain.

Where you're **not** investing, despite the work being in adjacent reach:

- **Eval rigor.** You have the numbers (GR004 91%, GR005 93%) but no public eval framework, no test-set discipline, no held-out adversarial fixture (your own debate-008 names this). The breadcrumb corpus is your evidence that you *can* be rigorous; the eval gap is a *choice* not a *capability*.
- **Audience / authority.** Zero GitHub stars across everything. A real blog, but not promoted. No talks, no newsletter, no community footprint. Everything is built-in-public-but-nobody-knows.
- **Healthcare domain.** You work at a community health center. You write *nothing* about HIPAA, FHIR, clinical workflow, or healthcare IT realities. That's a wasted vantage point — and it's *yours*, no one else can credibly write from there.
- **Distributed systems & typed-language rigor.** All single-process Python. No Rust/OCaml/TLA+. Given how much sf2 spends on correctness, this absence is a real ceiling.

## Where I'd push you — primary recommendation

### **"Agentic Evals for Infra Changes"** — a public benchmark and harness

Build a reproducible benchmark of ~50 realistic infra-change tasks (AD object lifecycle, VLAN reassignment, cert rotation, NetBox reconciliation, K8s manifest drift). Each task has a deterministic verifier. Run multiple LLMs/agents/configurations against it. Publish the harness, the dataset, and the leaderboard.

**Why this for you specifically:**

1. It converts work you're *already doing inside sf2* into something the outside world can use. The cert-watch fixture is already a one-off version of this; generalize it.
2. It forces the eval rigor you've been avoiding. You'd have to grapple with bias, statistical power, confound control — the exact issues your own RFC-034 (model identity) and debate-008 (fixture representativeness) are raising for sf2.
3. It builds the audience layer. An infra-eval leaderboard with credible numbers attracts the people whose attention is worth having (vendor research teams, infra-tool authors, the systems-engineering-curious side of the AI community).
4. It is *finishable* at a small scale. Twenty tasks in three categories is a viable v1. You are at risk of inventing v3 instead of shipping v1 — be honest about that and ship the small thing.

**What it stretches:** eval methodology, dataset design, statistical thinking, *public distribution* (the part you're most allergic to).

**Where you'd cut scope first:** keep it to infra you already know (AD, certs, NetBox). Resist the urge to make it "general infra." Specific beats broad for v1.

## Alternative if you want a higher ceiling

### **"HIPAA-aware Agent Sandbox"** — an opinionated framework + essay series

A small framework (and a 6-post essay arc on blog.hraedon.com) for safely running coding/ops agents inside a covered entity: data-egress controls, audit logging, prompt-redaction primitives, policy-as-code. Real day-job knowledge, no one else can write it as credibly, and the framing — *bringing agents into regulated environments* — is exactly the conversation nobody competent is anchoring yet.

Higher ceiling because it builds *authority* (durable) instead of *artifacts* (consumable). Lower probability of completion because it requires sustained writing, which your blog cadence suggests is harder for you than building.

## Why not the obvious third option

You could rewrite a substrate component in Rust for the distributed-systems stretch (Erlang-style supervision, real backpressure). It would teach you the most as a programmer. It would also be the project most likely to die in a branch, because the payoff is invisible and the marginal benefit over Python-substrate is uncertain at your current scale. I'm not recommending it — but I'm flagging it so you can argue back if I'm wrong.

## My one-sentence frame

You have built the machine; you have not yet built the evidence that the machine works, or the audience that would care. The growth project should be one or the other. The eval harness does both; pick that.

---

*Sources consulted: github.com/hraedon (10 public repos), blog.hraedon.com (about page + three recent posts), /projects/software-factory-2/spec.md, breadcrumbs/, debate/, reflections/. This recommendation does not assume work I haven't read; if there's a private repo or a draft post that changes the read, the recommendation may shift.*
