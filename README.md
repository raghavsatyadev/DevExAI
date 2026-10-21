# DevExAI — The Company AI Toolsmith

> Anyone in a company drops an idea into their team chat. An AI team reads it, checks it is safe,
> researches it, builds a ready-to-install tool for the AI coding assistants the company uses, and
> publishes a short post so everyone can use it. The person who had the idea gets the credit.

Status: **Phase 1 pilot built; Phase 2 mostly built** (see section 12).
A first unsigned Windows build exists (`uv run --group build python tools/build.py`); the Linux build comes next.
First slice of Phase 2: after approval the bot writes the tool's files and Opus reviews them
(`[build] by = "bot"`); the files are saved, not run, until the sandbox exists.

DevExAI is a **product** sold to companies. Our company uses it first. Each customer hosts it themselves,
on their own network, server and GPUs, with their own chat platform and AI accounts (see section 9).
It ships as an installable package for Windows and Linux that walks the admin through setup in the
web dashboard and keeps itself up to date from our update server.

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
| **Admins** | One or two people | Set DevExAI up, and add or remove maintainers in the web dashboard. An admin is also a maintainer. |
| **Maintainers** | A small group (several people) | Approve paid resources and logins, approve releases, handle anything the AI is unsure about, and keep the project summaries up to date. One maintainer is assigned per idea. |
| **The bot** | DevExAI | Does the safety check, research, planning, building, testing, publishing and all notifications. |
| **Readers** | Everyone | Read the blog post and install the tool into their project or their whole machine. |

Maintainers sign in to the **web dashboard** with email and password (Slack sign-in later) to see every
idea, act on it, and keep project summaries up to date. Everything they can do there they can also do
in chat.

**Picking a maintainer for each idea:** by topic area if one matches (e.g. Android, backend, security),
otherwise round-robin. If the assigned maintainer does not respond within 24 hours, the bot reassigns to the next maintainer and tells everyone involved.

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

**Built live, if the poster wants.** Once the safety gate passes, the bot asks the poster whether the tool
should be built **live, in public**. If yes, the bot's questions go to the poster in the idea's thread
and the poster can steer it with their own suggestions; each suggestion passes the safety gate before
the bot uses it. If no (or no answer), the maintainer handles the questions. Work never waits for the
answer.

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
- The bot writes a **short blog post** as a Markdown file: what it does, who it helps, a 30-second
  install, an example, and "**Idea by @poster**". Any website, wiki or Git host can show it.
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

One idea (one Slack thread) is one tool with one name, the one its blog post shows. `devex` is a single
Python file (standard library only) that the server hands out at `/blog/devex.py`; each post shows the
commands. It installs the tool's files under `.claude/`, `.gemini/` and `.codex/` at the same path in the
project or home folder, never runs anything from the tool and never edits settings files (it prints
those steps instead). It refuses to overwrite a file that is not the tool's unless asked (`--force`, which
keeps the old file to put back), and records what it wrote in `.devex/<tool>.json`, so uninstall removes
exactly that and keeps any file edited since.

## 8. Which AI does what (and why)

| Job | Model | Why |
|---|---|---|
| Safety gate | A strong model (Claude Opus today) + standard malware/secret scanners (to add) | Safety mistakes are expensive. |
| Research and planning | Claude Opus | Best reasoning; used only for thinking, not bulk typing. |
| Writing code | Claude Opus today (`[llm.models] builder`); Gemini Flash or a local model planned (DeepSeek off for now) | Cheap and fast for following a clear plan. |
| Code review | **Claude Opus only** | Catches mistakes the builder made. A cheaper model never reviews code, and never reviews its own work. |
| Blog post | Written from the approved plan; no extra model | Short text, low risk. |
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
| **Blog / website** | Posts are Markdown files, so any site can show them: a static site, a wiki, or the Git host's own file view. |
| **Where the bot runs** | The company's own server on its own network (with in-house GPUs for local models), installed from a Windows or Linux package that updates itself from our server; a container also works. The dashboard is shared on the company network over HTTPS. |

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
- DeepSeek, for cheap extra building capacity. Off for now; it may later be offered as a self-hosted
  option in the setup.
- One machine with a 24 GB GPU for local models and testing.

Also needed: a bot app on the chat platform (usually free), a small always-on server or cloud VM to run
the bot, a company Git repository for the tools, and a place to show the Markdown blog posts.

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

| Phase | What | Status |
|---|---|---|
| 1. Pilot | Slack intake (our platform), safety gate, plan + human-built tool, blog post written as a Markdown file. One team. | built |
| 2. Automate building | Cheap-model builder, tests, Opus review, auto blog post, install command, account pool. | mostly built: builder, Opus review and blog post work; tests in a sandbox, install command and account pool come next |
| 3. Company-wide | All teams, multiple maintainers with rotation, more AI assistants supported. | next |
| 4. Product | Installable package for Windows and Linux with guided setup in the dashboard and a built-in updater; second chat platform (e.g. Microsoft Teams); self-hosted models (such as DeepSeek) as a setup option. | started: Windows package, dashboard setup and updater exist |
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

Decided:
- DeepSeek is off for now. Self-hosted models may become a setup option.
- Blog posts are Markdown files.
- Each company hosts DevExAI itself, on its own network, from an installable package for Windows and
  Linux with guided setup and self-update.
- The pilot's admin and first maintainer is Raghav; the other maintainers are placeholders for now.
- The poster chooses whether their tool is built live in public.
- Dashboard sign-in is email and password for now; Slack sign-in later.
- Maintainers answer within 24 hours; after that the bot reassigns the idea.
- The Windows package will be code-signed; the certificate is bought later, so early builds are unsigned.
- Updates come from our own server, since DevExAI is a paid service: only licensed customers can
  download them. On Windows and Linux alike the app updates itself: it checks our server with the
  customer's licence key.

No questions are open right now.
