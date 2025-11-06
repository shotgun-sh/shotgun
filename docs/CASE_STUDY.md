# Developer Case Study: Cursor and Claude Code Suggested Building a Proxy. Shotgun CLI Found LiteLLM Instead.

*Cursor, Claude Code, and Copilot all suggested building a custom LLM proxy to track usage and enforce budgets - 3–4 weeks of work. Shotgun's codebase-aware research found LiteLLM Proxy instead, which we integrated with Stripe and some glue code for payments. Implementation took 5 days. First paying customer arrived 14 hours after deployment. 80% less development time vs building a custom proxy. Near-zero technical debt.*

**Shotgun is a Spec Driven Development CLI Tool for Developers and AI Agents.** It does the prep work your AI coding agent needs but can't do itself: reads your entire codebase, researches how features should fit, writes specs with full context, then hands that to your AI agent. Works for greenfield projects and existing codebases.

**Shotgun is open source.** Built in public with 150+ developers who want to make research-first development standard practice instead of rebuilding what exists. Bring your own key (BYOK) or use a Shotgun subscription - $10 for $10 in usage.

---

## What Teams Do Now vs. What Works

**What teams do now:** Describe problem to AI coding agent → AI suggests custom build → start coding → miss existing solutions → accumulate technical debt.

**What works:** Research with codebase context first → find what exists and understand the logic → build the right and best thing → ship faster with less debt.

### AI coding agents made us fast at building. They also made us fast at building the wrong things.

Cursor, Claude Code, Copilot - they suggest code immediately. You describe a problem, they generate solutions. Custom proxy? Here's the boilerplate. Payment infrastructure? Here's the architecture. They're ready to write thousands of lines before you've confirmed the problem needs solving.

**They never ask: does this already exist?**

This case study: usage tracking and budget enforcement for our AI agent platform's LLM calls. Traditional approach: 3–4 weeks to build a custom LLM proxy. Every AI coding agent we tried said the same: build it custom.

Shotgun researched first. Found LiteLLM Proxy in 30 minutes. An existing solution we didn't know existed. Implementation: 5 days instead of 3–4 weeks. First paying customer: 14 hours after deployment.

- 80% reduction in development time
- 90% less testing
- Near-zero technical debt
- ~$100/month infrastructure instead of thousands in development labor

**The mechanism:** research with full codebase context before writing any code.

---

## The Challenge

We were building an AI agents platform. Users run LLM API calls through our system. We needed to charge them for usage without exposing our API keys.

### Requirements:
- Real-time usage tracking for LLM calls
- Usage-based billing for LLM calls
- API key protection (users never see our keys)
- Budget limits at global, team, and user levels
- Works with our existing Pydantic AI setup

### Traditional build approach:
- 3–4 weeks development
- Double our code surface area (security + event management)
- Custom proxy server
- Dedicated API infrastructure
- Ongoing maintenance overhead

We consulted Cursor, Claude, and GitHub Copilot. Same answer from all three: **build a custom proxy.**

The suggestions made technical sense. WebSocket connections for real-time tracking. Event queues for usage aggregation. Database schema for budget enforcement. Rate limiting middleware. Authentication layers.

**None of them asked: does this already exist?**

They were ready to help us write thousands of lines of proxy code. Start with the authentication layer, then add the billing logic, then the budget checks, then the API key rotation system. Each suggestion added complexity. Each layer meant more testing, more security review, more maintenance.

We were about to spend a month building infrastructure that would double our codebase and create ongoing operational burden.

**Then we stopped and asked Shotgun CLI to research first.**

---

## How Shotgun's Research Phase Works

We gave Shotgun an unbiased problem statement. No prescribed solution, no architectural assumptions. Just requirements:

> We need usage-based billing for LLM API calls. Must protect our API keys. Must enforce budgets at team and user level. Must work with our Pydantic AI infrastructure.

Shotgun's research phase runs in four parallel tracks:

1. **Codebase analysis:** Reads your entire repository. Understands your existing patterns, dependencies, architecture. In our case: found our Pydantic AI setup, identified how we structure API calls, discovered our authentication patterns.

2. **External research:** Searches for existing solutions. Proxy systems, budget management tools, LLM infrastructure. Free and paid options. Battle-tested vs experimental.

3. **Interactive clarification:** Asks questions to narrow the search. "Do you need real-time usage tracking or is batch processing acceptable?" "What's your budget constraint - developer time or infrastructure cost?" "Do you need audit logs for compliance?"

4. **Evaluation of options:** Compares free and paid infrastructure options against your constraints.

**Total research time: 30 minutes.**

Most of that was Shotgun reading documentation for solutions we'd never heard of.

---

## Shotgun Found LiteLLM Proxy in 30 Minutes

**LiteLLM Proxy.** None of us had heard of it.

It sits between your application and LLM providers. Handles everything we were about to build:

- **Usage tracking** for all LLM calls. Real-time spending metrics per request. Built-in.
- **Budget enforcement** at global, team, and user levels. Set limits, requests stop when hit. Built-in.
- **API key protection** through virtual keys. Users never see your actual OpenAI/Anthropic keys.
- **Pydantic AI compatible.** Change the endpoint URL. Everything else stays the same.
- **Infrastructure cost:** ~$100/month self-hosted. No development needed.
- **Code we had to write:** 58-line configuration file (precisely).

### Compare to what we almost built:

| What We Almost Built | What We Actually Did |
|---------------------|---------------------|
| Custom proxy: 3–4 weeks | LiteLLM config: 2 hours |
| Usage tracking system | built-in |
| Event management system | built-in |
| Budget logic (global/team/user) | built-in |
| Security review of custom code | battle-tested open source |

**We were about to double our codebase to build what already existed.**

---

## Results: 5 Days to Revenue vs 4 Weeks to Custom Build

- **Day 1–5:** Implementation and testing complete
- **Day 5, 9:00 PM:** Deployed to production
- **Day 6, 11:00 AM:** First paying customer (14 hours after deployment)
- **Week 2:** Multiple paying customers

### What We Saved

- **Development time:** 5 days vs 3–4 weeks (80% reduction)
- **Testing:** 90% less testing needed (using proven infrastructure instead of custom code)
- **Code added:** 58-line config vs doubling our codebase
- **Infrastructure cost:** ~$100/month vs thousands in development + ongoing maintenance
- **Security surface:** Zero new attack vectors (LiteLLM is battle-tested)
- **Technical debt:** Near-zero vs maintaining a custom proxy long-term

### What This Freed Up

Engineering team focused on core product features instead of infrastructure. First revenue 14 hours after deployment instead of waiting a month. Zero time spent on proxy maintenance, security patches, or scaling issues.

---

## When to Research Before Building: 5 Use Cases

**What developers do now:** Describe problem to AI coding agent → AI suggests custom build → start coding → discover existing solution exists (or doesn't discover it at all).

**What works:** Research with codebase context first → find what exists → build only what's actually missing.

### The question that changes everything: "Does this already exist?"

Most AI coding tools never ask this. Cursor, Claude Code, Copilot - they're built to generate code, not prevent unnecessary work. You describe a problem, they start architecting solutions. Custom proxy? Here's the boilerplate. Real-time sync? Here's the WebSocket setup. They assume you need to build.

### This pattern works for any major architectural decision:

1. **Onboarding** - New developer? Shotgun maps your entire architecture and generates docs that actually match the code. Not outdated wikis - current documentation pulled from the actual codebase.

2. **Refactoring** - Understand all dependencies before touching anything. Keep your refactor from becoming a rewrite. Research shows what will break before you change it.

3. **Greenfield Projects** - Research existing solutions globally before writing line one. Like we did with LiteLLM - find what exists before building.

4. **Adding Features** - Know exactly where your feature fits. Prevent duplicate functionality. Research finds similar patterns already in your codebase.

5. **Migration** - Map the old, plan the new, track the delta. Break migration into safe stages instead of big-bang rewrites that fail.

### When to research first:
- Any decision that affects multiple parts of your codebase
- Any infrastructure choice that creates ongoing maintenance
- Any feature that might have existing solutions
- Any time you're about to write more than 500 lines of new code

### When you don't need this:
- Fixing bugs in existing code you understand
- Minor UI tweaks
- Configuration changes
- Straightforward CRUD implementations

**The mechanism:** read your entire codebase to understand what you have, research external landscape to find what exists, write specs with full context, then hand them to your AI coding agent.

Most teams skip step one (codebase context), step two (external research) and step three (exporting proper specs for their AI agent). They go straight to building. Fast execution of the wrong solution.

---

## Conclusion

LLM usage tracking and billing project. Every AI coding agent said: build custom LLM proxy, 3–4 weeks.

Shotgun researched first with full codebase context. Found LiteLLM Proxy in 30 minutes. Combined with Stripe and glue code for payments. 5 days to deployment. First customer 14 hours later.

> "This would have never been possible without Shotgun. The solution it discovered was so well-tailored to our problem that we were able to get paying customers in days."

**Translation:** "We didn't know LiteLLM existed. We were about to spend a month building a worse version. Shotgun found it in 30 minutes because it actually looked."

### The lesson: AI coding tools make you fast at building. They don't make you fast at knowing what to build.

Before your next feature, ask: **"Does this exist already? How would it integrate with what we have?"**

Most teams don't ask because they don't have the mechanism. You'd need to manually read your entire codebase, then research every possible solution, then figure out integration paths. That takes longer than just building.

**Shotgun automates that research.** Reads your repository, researches external solutions, asks clarifying questions, shows you what exists that matches your constraints.

---

## Help Us Build in Public

Shotgun is open source. We're building research-first spec-driven development as a new category. The more developers discover it, the faster we can make it standard practice.

GitHub stars matter for visibility. Trending repositories get discovered by thousands of developers daily. More developers testing means faster iterations, better feedback, more use cases covered.

**If this case study resonated, ⭐ [Star Shotgun on GitHub](https://github.com/shotgun-sh/shotgun)**

> GitHub - shotgun-sh/shotgun: Spec Driven Development 🤠 Write codebase-aware specs for AI coding agents so they don't derail.

Questions? Email us at contact@shotgun.sh

*This project happened in October 2025. We're a 3-person team.*

---

**Tags:** #ai-coding-agents #developer-productivity #codebase-indexing #litellm #cursor #claudecode #copilot #technical-debt #software-engineering #case-study #spec-driven-development