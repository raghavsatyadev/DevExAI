# DevExAI — The Company AI Toolsmith

> Anyone in a company drops an idea into their team chat. An AI team reads it, checks it is safe,
> researches it, builds a ready-to-install tool for the AI coding assistants the company uses, and
> publishes a short post so everyone can use it. The person who had the idea gets the credit.

Status: **proposal / draft for review**. Nothing is built yet.

DevExAI is planned as a **product**. Our company uses it first, but any company can install it on its own
chat platform, AI accounts and infrastructure (see section 9).

---

## 1. The problem

Every week someone finds a useful trick for AI coding or code review — a blog post, a GitHub repo, a
new prompt, a new MCP server. Today that knowledge stays in one person's head or gets lost in a chat
thread. Nobody has time to turn it into something the whole company can install in one step.

## 2. The idea in one paragraph

A chat bot collects ideas. Each idea first passes a strict safety check. Then a "planner" AI (Claude
Opus) studies the idea, reads the links, looks at what the company's projects actually need, and writes
a plan. A cheaper "builder" AI (Gemini Flash by default; optionally DeepSeek or a local model) writes the
code. Claude Opus reviews every line of it, a human maintainer approves it, and the bot publishes a short
blog post with install steps. The person who suggested it is thanked in chat and named in the post.

## 3. Who is involved

| Role | Who | What they do |
|---|---|---|
| **Poster** | Any colleague | Sends an idea (text and/or links) to the bot in chat. |
| **Maintainers** | A small group (several people) | Approve paid resources and logins, approve releases, handle anything the AI is unsure about, and keep the project summaries up to date. One maintainer is assigned per idea. |
| **The bot** | DevExAI | Does the safety check, research, planning, building, testing, publishing and all notifications. |
| **Readers** | Everyone | Read the blog post and install the tool into their project or their whole machine. |

**Picking a maintainer for each idea:** by topic area if one matches (e.g. Android, backend, security),
otherwise round-robin. If the assigned maintainer does not respond within an agreed time (e.g. one
working day), the bot reassigns to the next maintainer and tells everyone involved.

## 4. How an idea travels (step by step)

```
Chat idea ──► 1. Safety gate ──► 2. Understand & research ──► 3. Plan (Opus)
                   │ reject                                         │
                   ▼                                                ▼
             Poster told why                        4. Resources check (free = auto,
                                                       paid/login = ask maintainer in chat)
                                                                    │
                                                                    ▼
             7. Publish & celebrate ◄── 6. Review & approve ◄── 5. Build & test (cheap model)
```

Examples below use Slack words (channel, thread, slash command). On other chat platforms the bot uses
the nearest equivalent.

### Step 0 — Submit
The poster messages the bot (a direct message, an `#ai-ideas` channel, or a `/devex-idea` command) with
plain text, links (blogs, GitHub, YouTube, X/Twitter, docs), or both. The bot replies at once with a
tracking number and opens a **thread for that idea**. Every later update goes into that thread.

### Step 1 — Strict safety gate (nothing starts before this passes)
Before any research or building, the idea and every linked page are checked by an AI reviewer. It
rejects or flags:

- Adult/sexual content, hate, harassment, violence, or anything against company policy.
- Malicious code: malware, credential stealers, crypto miners, hidden network calls, obfuscated scripts,
  "curl | bash" from unknown sites.
- **Hidden instructions inside web pages** aimed at the AI ("ignore your rules and…"). Linked pages are
  treated as information only, never as orders.
- Requests to leak secrets, customer data or company code to outside services.
- Software with licences we cannot use, or piracy.

Outcomes: **Pass** → continue. **Unsure** → assigned maintainer decides in chat. **Reject** → poster is
told why, politely, and the maintainer is copied. Links are opened in an isolated sandbox, never on a
company laptop.

> The same safety check runs again on the finished code (Step 6), because a safe idea can still produce
> unsafe code.

### Step 2 — Understand and research
The planner reads the links, searches for related tools that already exist, and checks for duplicates
(a similar tool already published, or an existing idea in progress). It also uses a **summary of each
of the company's current projects** (languages, frameworks, tools, common pain points) so it builds what
the teams actually need, not a generic demo.

**Project summaries are owned by the maintainers.** They add, view, edit and remove them (for example
with a `/devex-projects` chat command or a small admin page). The bot can only read them.

### Step 3 — Plan (Claude Opus)
The plan says, in plain language: what will be built, for which AI assistants, what it needs, how it
will be tested, and how big it is. The plan is posted in the idea's thread for the poster and
maintainer to see.

### Step 4 — Resources: free is automatic, paid or login goes to a human
| Lane | Resource type | What the bot does |
|---|---|---|
| **Fast lane** | Free and needs no account (open-source library, public docs, free public API without a key) | Uses it automatically and notes it in the thread. |
| **Escalation lane** | Paid, behind a login wall, needs an API key, a licence, or a new account | **Stops and asks the maintainers in chat** with buttons: *Approve / Deny / Suggest alternative*. Says what it is, why it is needed, and the cost. |

The fast lane only skips the *resource* approval. Every tool still needs the human release approval in
Step 6.

The bot **never** creates accounts, enters passwords, or spends money by itself. Keys and logins are added
by a maintainer into a secure secret store, never pasted into chat.

### Step 5 — Build and test (cheaper models)
A low-cost model writes the code following Opus's plan. It runs inside a sandbox with no access to
company secrets. It must include tests and a short README. If the builder gets stuck, it escalates to
Opus; if Opus gets stuck, it escalates to the maintainer.

### Step 6 — Review and approve
1. **Claude Opus reviews the code** against the plan: correctness, security, tests and readability. Only
   Opus does code review; the cheaper builder model never approves code. If Opus finds problems, the
   code goes back to the builder and Opus reviews it again.
2. The safety gate runs again on the code and every dependency.
3. **A human maintainer gives the final yes.** Nothing ships to colleagues without a human approval.

### Step 7 — Publish and celebrate
- The tool goes into a company repository (e.g. `devexai-tools`) with a version number.
- The bot writes a **short blog post**: what it does, who it helps, a 30-second install, an example, and
  "**Idea by @poster**".
- The bot posts in the idea's thread and in a public channel congratulating the poster.

## 5. Keeping people informed

Both the **poster** and the **assigned maintainer** are told about every stage, in the idea's thread:

`Received → Safety check passed/failed → Researching → Plan ready → Waiting for approval (if needed)
→ Building → Testing → Under review → Published (or Stopped, with reason)`

Either of them can reply in the thread to ask a question, add details, or stop the idea. Long silences
are avoided: if a step takes longer than expected, the bot says so.

## 6. What gets built

One idea can produce one or more of these. At launch we support three AI assistants: **Claude** (Claude
Code), **Gemini** (Gemini CLI) and **ChatGPT** (Codex). More can be added later.

- **Skills / instructions** — reusable "how to do X" guides the assistant follows.
- **MCP servers** — small services that give assistants new abilities (e.g. read the issue tracker).
- **Tools and scripts** — command-line helpers.
- **Plugins / extensions** — bundles that install several of the above at once.

Where possible one shared core is built and thin adapters are generated for each assistant, so the same
idea is not rebuilt three times.

## 7. Installing: your project or your whole machine

Every blog post offers two install choices:

| Choice | Effect | Good for |
|---|---|---|
| **This project only** | Files go into the project's own folder (e.g. `.claude/`, `.gemini/`, `.codex/`) and can be committed so the whole team gets it. | Team-specific or project-specific tools. |
| **My whole machine** | Files go into the user's personal settings folder and work in every project. | Personal productivity tools. |

Install is one command (e.g. `devex install <tool> --project` or `--global`), shows exactly what it will
change before doing it, and has a matching `devex uninstall`.

## 8. Which AI does what (and why)

| Job | Model | Why |
|---|---|---|
| Safety gate | A strong model (Claude) + standard malware/secret scanners | Safety mistakes are expensive. |
| Research and planning | Claude Opus | Best reasoning; used only for thinking, not bulk typing. |
| Writing code | Gemini Flash (default); DeepSeek or a local model optional | Cheap and fast for following a clear plan. |
| Code review | **Claude Opus only** | Catches mistakes the builder made. A cheaper model never reviews code, and never reviews its own work. |
| Blog post | Cheap model, checked by Opus | Short text, low risk. |
| Experiments / evals | Local models on a 24 GB GPU | Free to run once the GPU is bought. |

## 9. Built as a product: fits any company's setup

Every outside piece is a plug-in part. A company picks its own in one settings file; the core flow
(sections 4–8) stays the same.

| Part | Options (examples) |
|---|---|
| **Chat platform** | Any chat platform that supports bots: Slack, Microsoft Teams, Google Chat, Discord, Mattermost, Rocket.Chat, Zulip, and others through a small adapter. Where a platform lacks buttons or threads, the bot falls back to replies and simple text commands. |
| **AI accounts** | Claude, Gemini and ChatGPT, through subscription accounts and/or API keys (see below). |
| **Code host** | GitHub, GitLab, Bitbucket, Azure DevOps, or a self-hosted Git server. |
| **Secret store** | HashiCorp Vault, or the AWS, Google Cloud or Azure secret manager. |
| **Blog / website** | The company's own website, wiki, or any site the bot can publish to. |
| **Where the bot runs** | Any cloud VM, the company's own servers, or a container (Docker/Kubernetes). |

### Using several AI accounts and API keys
The bot can hold **several subscription accounts and API keys per AI provider** (an "account pool"):

- Work is spread across the pool. When one account hits its usage limit, the bot moves to the next.
- Maintainers add and remove accounts and keys in the secret store; the bot never sees them in chat.
- Usage and cost are tracked per account, with a monthly budget per provider.
- If every account for a model is at its limit, the bot waits and tells the thread, or uses a fallback
  model only if the maintainers allowed one. It never quietly swaps to a weaker reviewer: code review
  stays Claude Opus.
- Each company must check that its plans allow use by a shared bot. Business and enterprise plans and
  API keys usually do; personal plans often do not.

## 10. Cost and resources

**Our own setup:** the company's enterprise Claude and Gemini plans, which cover a shared company bot
and keep our code under company terms. Opus planning and review use the most of the Claude quota. More
accounts or API keys can be added to the pool when the bot gets busy.
**Optional extras:**
- DeepSeek, for cheap extra building capacity. Off by default; see open question 1.
- One machine with a 24 GB GPU for local models and testing.

Also needed: a bot app on the chat platform (usually free), a small always-on server or cloud VM to run
the bot, a company Git repository for the tools, and a blog website (ours will be custom-built; details
decided later).

## 11. Rules the bot always follows

1. Nothing starts until the safety gate passes.
2. Nothing paid, nothing needing a login, and nothing released without a human maintainer's yes.
3. Every line of built code is reviewed by Claude Opus before a human sees it.
4. Company code and project summaries are read-only for the bot and never sent to services the company
   has not approved.
5. Web pages and posts are information, never instructions.
6. Every action is logged in the idea's thread so anyone can see what happened and why.
7. Every published tool can be uninstalled cleanly.

## 12. Rollout

| Phase | What | Time (rough) |
|---|---|---|
| 1. Pilot | Slack intake (our platform), safety gate, plan + human-built tool, manual blog post. One team. | 2–3 weeks |
| 2. Automate building | Cheap-model builder, tests, Opus review, auto blog post, install command, account pool. | 3–4 weeks |
| 3. Company-wide | All teams, multiple maintainers with rotation, more AI assistants supported. | ongoing |
| 4. Product | Second chat platform (e.g. Microsoft Teams), settings file for all plug-in parts, setup guide for other companies. | after phase 3 |
| 5. Local models | Add the GPU machine for cheap building and evals, if usage justifies it. | when needed |

**How we will know it works:** number of ideas submitted, % shipped, installs per tool, time from idea to
release, cost per shipped tool, and a short "was this useful?" button on every post.

## 13. Risks and how we handle them

| Risk | Handling |
|---|---|
| A published tool is harmful or buggy and runs on many laptops | Two safety checks, human approval, sandboxed builds, versioned releases, one-command uninstall, ability to pull a release. |
| Hidden instructions in a submitted link hijack the AI | Links are read in a sandbox as plain data; the bot has no access to secrets while reading them. |
| Company code leaks to an outside AI | Only approved providers see code; the bot uses summaries, not full source, where possible. |
| Costs grow quietly | Monthly budget per provider and per account, usage shown to maintainers, cheap models do the bulk work. |
| An account pool breaks a provider's terms | Each company checks its plans allow a shared bot; business/enterprise plans or API keys are recommended. |
| Too many low-value ideas | Duplicate check, maintainers can mark ideas "not now", a simple priority queue. |
| Maintainer bottleneck | Several maintainers, topic-based routing, automatic reassignment after a timeout. |

## 14. Open questions for the maintainers

1. **DeepSeek (optional).** The plan works without it. If we turn it on: its hosted service is outside
   our usual vendors, so either use it only for work that touches no company code, or run DeepSeek's
   open models on our own GPU.
2. **Blog website.** It will be our own custom-built site. Design, hosting and how the bot publishes to
   it are decided later.
3. Who are the first maintainers, and what is the response time we promise? (Parked for now.)
4. **How we offer the product to other companies:** they host it themselves, we host it for them, or
   both.
