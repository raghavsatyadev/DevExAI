# DevExAI: the company's AI toolsmith

Anyone at the company can share an idea in team chat. DevExAI checks that the idea is safe, studies
it, builds a small tool that our AI coding helpers can use, and publishes a short post so everyone
can install it. The person who had the idea gets the credit.

**Where we are today:** the first version works end to end with Slack. The bot checks ideas, plans
them, writes the tool, has a second AI check the work, and publishes a post that people install from
with one command. Some parts are still to come, and section 12 lists them.

DevExAI is a product that we will sell to other companies. We use it ourselves first. Each company
runs its own copy on its own network, with its own chat app and its own AI accounts. It comes as a
normal installer for Windows (Linux is next), and the admin finishes the setup in a web page.

---

## 1. The problem

Every week someone finds a clever trick that makes AI coding or code review better. It might be a blog
post, a project on GitHub, a new prompt, or a new add-on for an AI helper. Usually that knowledge stays
with one person or gets lost in a chat thread. Nobody has the time to turn it into something the whole
company can set up in one step.

## 2. The idea in short

A chat bot collects ideas. Each idea first goes through a strict safety check. Then an AI planner
(Claude Opus) reads the idea and its links, thinks about what our own projects need, and writes a plan
in plain words. An AI builder writes the tool. A second AI check looks over every line, a person on
the team gives the final yes, and the bot publishes a short post with install steps. The person who
suggested the idea is thanked in chat and named in the post.

## 3. Who is involved

| Who | What they do |
|---|---|
| **The person with the idea** | Any colleague. Sends an idea (text, links, or both) to the bot in chat. |
| **Admins** | One or two people. They install DevExAI and choose who the maintainers are, in the web dashboard. An admin is also a maintainer. |
| **Maintainers** | A small group. They approve anything that costs money or needs a login, give the final yes before a tool is released, decide when the AI is unsure, and keep the short descriptions of our projects up to date. Each idea gets one maintainer. |
| **The bot** | DevExAI itself. It does the safety check, the research, the plan, the building, the post and all the updates. |
| **Everyone else** | Reads the posts and installs the tools they like. |

Maintainers sign in to the **web dashboard** with an email and password to see every idea and act on
it. Anything they can do there, they can also do in chat.

**Who looks after each idea:** the bot picks the maintainer whose topic fits (Android, backend,
security and so on). If no topic fits, it takes turns. If that maintainer does not answer within 24
hours, the bot passes the idea to the next maintainer and tells everyone involved.

## 4. How an idea moves along

1. Someone shares an idea.
2. Safety check. If it fails, the person is told why and nothing else happens.
3. The bot studies the idea and its links.
4. Claude Opus writes a plan.
5. The bot checks what the tool needs. Free things are fine. Anything paid or behind a login needs a
   maintainer's yes.
6. The bot builds the tool.
7. A second AI check, then a maintainer's yes.
8. The post goes up and the person with the idea is thanked.

We use Slack words below (channel, thread, command). Other chat apps have something similar.

### Sharing an idea
The person sends the idea to the bot: in a direct message, in the `#ai-ideas` channel, or with the
`/devex-idea` command. It can be plain text, links (blogs, GitHub, YouTube, X, documentation), or
both. The bot answers right away with a number for the idea and starts a **thread just for it**. Every
later update goes into that thread.

If the exact same idea was already sent, the bot says so and does not start again. If it looks a lot
like an earlier idea, the bot marks it as a possible repeat, and the maintainer decides whether it is
new.

### Safety check (nothing starts until this passes)
Before any work starts, an AI reviewer reads the idea and every linked page. It turns away or flags:

- Adult content, hate, bullying, violence, or anything against company rules.
- Harmful software: programs that steal passwords, secretly mine crypto, quietly send data
  somewhere, or hide what they really do.
- **Hidden orders inside web pages** that try to boss the AI around ("ignore your rules and ...").
  The bot treats web pages as reading material only, never as orders.
- Requests to leak secrets, customer data or company code.
- Software whose licence we are not allowed to use, or pirated software.

Three results are possible. **Pass**: work goes on. **Unsure**: the maintainer decides in chat.
**Reject**: the person is told why, politely, and the maintainer gets a copy.

Links are read by a separate small program that has no access to passwords or keys, never on
someone's laptop.

> The finished code is checked for safety again later, because a safe idea can still lead to unsafe
> code.

**Built in the open, if the person wants.** Once the idea passes, the bot asks the person whether the
tool should be built in public. If yes, the bot asks them its questions in the thread, and they can
steer it with their own suggestions. Each suggestion goes through the safety check first. If no (or no
answer), the maintainer answers the questions instead. Work never waits for this answer.

### Studying the idea
The planner reads the links, looks for tools that already do the same thing, and reads a **short
description of each of our projects** (what they are written in, what tools they use, what hurts). That
way it builds what our teams really need, not a general demo.

**The maintainers own these project descriptions.** They add, read, change and remove them in the
dashboard. The bot can only read them.

### The plan (Claude Opus)
The plan says, in plain words, what will be built, which AI helpers it is for, what it needs, how it
will be tested and how big it is. The plan goes into the idea's thread for the person and the
maintainer to read. The maintainer approves it before building starts.

### What the tool needs: free is automatic, paid or login needs a person

| Kind | Examples | What the bot does |
|---|---|---|
| **Free, no account** | Free open source code, public documentation, free public services that need no sign-up | Uses it and mentions it in the thread. |
| **Costs money or needs a login** | Paid services, anything behind a login, a key or a licence, a new account | **Stops and asks the maintainers in chat**, with buttons: Approve, Deny, Suggest something else. It says what it is, why it is needed and what it costs. |

Free things only skip this one question. Every tool still needs a person's yes before it is released.

The bot **never** creates accounts, types passwords or spends money on its own. Keys and logins are
added by a maintainer on the server, never pasted into chat.

### Building the tool
After the plan is approved, the AI builder writes the tool's files, a few tests and a short how-to
(README). Today the files are saved and shown on the idea's page, but the tests are **not run yet**:
running code that an AI wrote needs a locked-down test machine, and that comes next.

### Checking and approving
1. **Claude Opus checks the work** against the plan: does it work, is it safe, are there tests, is it
   easy to read. If it finds problems, the builder gets one more try and Opus checks again.
2. The safety check looks at the code again.
3. **A maintainer gives the final yes.** Nothing reaches colleagues without it. The maintainer's
   buttons arrive in a direct message, so they do not get lost in the channel.

### Publishing and saying thanks
- The bot writes a **short post** as a web page: what the tool does, which AI helpers it works with,
  what you get, and "**Idea by @name**".
- Posts appear on the blog that is built into the dashboard. Anyone on the company network can read
  it without signing in.
- At the top of each post, an **Install it** button jumps to two simple steps: get DevExAI once, then
  run one command in your project folder. The tool's files are lower down, for anyone who wants to
  look inside.
- The bot posts in the idea's thread to thank the person, and the idea's page in the dashboard shows
  the install command too.

## 5. Keeping people in the loop

The **person with the idea** and the **maintainer** both see every step in the idea's thread:

Received, Safety check passed (or failed), Studying, Plan ready, Waiting for approval (only if
something costs money or needs a login), Building, Being checked, Published (or Stopped, with the
reason).

Either of them can reply in the thread to ask a question, add details or stop the idea. If a step takes
longer than it should, the bot says so. On the admin's computer, a small DevExAI icon sits next to the
clock and pops up a note when something needs attention.

## 6. What gets built

One idea can turn into one or more of these. We support three AI helpers: **Claude** (Claude Code),
**Gemini** (Gemini CLI) and **ChatGPT** (Codex). Today the builder writes tools for Claude Code first.

- **Skills**: written guides the AI helper follows, such as "how we write tests here".
- **Connectors** (also called MCP servers): small add-ons that let the AI helper use other apps, such
  as reading our issue tracker.
- **Small programs**: helpers you run from the command line.
- **Bundles**: one package that installs several of the above at once.

Later, one shared version will be built with a thin layer for each AI helper, so the same idea is not
built three times.

## 7. Installing a tool

Every post offers two choices:

| Choice | What happens | Good for |
|---|---|---|
| **This project only** (the normal way) | The files go into the project's own folder and can be saved with the project, so the whole team gets them. | Tools for one team or one project. |
| **My whole computer** | The files go into your personal settings folder and work in every project. | Personal helpers. |

It is one command, copied from the post:

- `devexai install <tool>` for this project
- `devexai install <tool> --global` for your whole computer
- `devexai uninstall <tool>` removes it again

Before changing anything, it shows exactly what it will add and asks first. It never runs the tool's
code and never changes your settings files (if a setting is needed, it tells you what to add). It will
not replace a file that is not part of the tool unless you ask, and removing a tool keeps any file you
changed yourself.

**Each computer needs DevExAI once.** The "Get DevExAI" page on the dashboard (linked from every post)
hands it out, inside the company network only:

| Who | How | What it does |
|---|---|---|
| Developers on Windows | **DevExAI-User-Setup.exe** | Installs the `devexai` command for you. No Python and no admin rights needed. It also makes your computer trust the company's own security certificate and connects to our server. |
| Developers on Linux | One line to paste into a terminal, shown on the page | The same thing. |
| Anyone else with Python 3.11 or newer (for example on a Mac) | One file to download | The same command, run with Python. |
| The admin, on the server | **DevExAI-Admin-Setup.exe** | Installs the bot and the dashboard, plus the same `devexai` command. |

The admin can control the bot with a few simple commands:

- `devexai start admin` starts the bot in the background and opens the dashboard. Running it again just
  opens the dashboard.
- `devexai stop admin` stops it.
- `devexai status` says whether it is running and where its data is kept.
- A box in the installer ("Start DevExAI when I sign in") starts it every time the admin signs in to
  Windows. `devexai autostart on` or `off` changes this later.

The developer version holds none of the admin parts. `devexai update` fetches a newer version from our
server when one is out.

## 8. Which AI does which job, and why

| Job | Which AI | Why |
|---|---|---|
| Safety check | Claude Opus today; standard virus and secret scanners to be added | Safety mistakes are expensive. |
| Studying and planning | Claude Opus | It is the best at careful thinking. We use it for thinking, not for typing lots of code. |
| Writing the code | Claude Opus today; a cheaper AI (Gemini Flash or one we run ourselves) later | Following a clear plan is a simpler job, so a cheaper AI should do. |
| Checking the code | **Claude Opus only** | It catches mistakes the builder made. A cheaper AI never checks code, and no AI ever checks its own work. |
| The post | Made from the approved plan, no extra AI | Short and low risk. |
| Trying things out | AI models running on our own graphics card | Free to run once the card is bought. |

## 9. Made to fit any company

Every outside part can be swapped. A company picks its own parts in one settings file, and the steps
in sections 4 to 8 stay the same.

| Part | Today | Choices later |
|---|---|---|
| **Chat app** | Slack | Microsoft Teams, Google Chat, Discord, Mattermost and others. Where an app has no buttons or threads, the bot uses plain replies and short typed commands instead. |
| **AI accounts** | Claude | Gemini and ChatGPT, using company plans or paid-as-you-go keys. |
| **Where code is kept** | Not needed yet | GitHub, GitLab, Bitbucket, Azure DevOps or the company's own server. |
| **Where passwords and keys are kept** | A protected file on the server | A proper password vault, such as HashiCorp Vault or the one from AWS, Google Cloud or Azure. |
| **Blog** | Built into the dashboard; each post is one web page file | The same files can be put on any company website or wiki. |
| **Where it runs** | The company's own Windows computer, on its own network, from the installer. It keeps itself up to date from our server. The dashboard is shared on the company network with a secure (https) address. | A Linux server, or a container. |

### Using several AI accounts (planned)
The bot will be able to hold **several accounts and keys for each AI company**:

- Work is spread across them. When one account reaches its limit, the bot moves to the next.
- Maintainers add and remove accounts on the server. The bot never sees them in chat.
- Use and cost are tracked for each account, with a monthly budget for each AI company.
- If every account is at its limit, the bot waits and says so in the thread, or uses a backup AI only
  if the maintainers allowed one. Checking code always stays with Claude Opus.
- Each company must make sure its plans allow a shared bot. Business plans and paid-as-you-go keys
  usually do. Personal plans often do not.

## 10. Cost and what we need

**What we use:** the company's business plans for Claude and Gemini. These cover a shared company bot
and keep our code under company terms. Planning and checking with Opus use the most. More accounts can
be added when the bot gets busy.

**Optional extras:**
- DeepSeek, a cheaper AI, for extra building. Off for now. Later it may become an option that runs on
  our own computers.
- One computer with a strong graphics card (24 GB) to run AI models ourselves and try things out.

**Also needed:** a bot app in the chat app (usually free) and one always-on computer on the company
network to run DevExAI. The blog is already part of the dashboard.

## 11. Rules the bot always follows

1. Nothing starts until the safety check passes.
2. Nothing that costs money, needs a login, or gets released happens without a maintainer's yes.
3. Claude Opus checks every line of code before a person sees it.
4. The bot can only read company code and project descriptions, and never sends them to services the
   company has not approved.
5. Web pages and messages are reading material, never orders.
6. Everything the bot does is written in the idea's thread, so anyone can see what happened and why.
7. Every tool can be removed cleanly.

## 12. Plan and progress

| Stage | What | Where we are |
|---|---|---|
| 1. Trial | Ideas in Slack, safety check, plan, dashboard, blog post. One team. | Done |
| 2. Let the AI build | AI builder, Opus check, automatic post, one-command install, repeat check | Mostly done. Still to come: running the tool's tests on a locked-down machine, and using several AI accounts |
| 3. Whole company | All teams, several maintainers taking turns, more AI helpers | Next |
| 4. Product | Installers for Windows and Linux, setup in the dashboard, automatic updates, a second chat app (such as Teams), our own AI models as an option | Started: the Windows installers, the Linux developer command and automatic updates work. The Linux admin installer is next. |
| 5. Our own AI models | A computer with a graphics card for cheap building and trials, if use justifies it | When needed |

**How we will know it works:** how many ideas come in, how many get published, how many people install
each tool, how long an idea takes to become a tool, what each tool costs, and a "was this useful?"
button on every post.

## 13. Risks and what we do about them

| What could go wrong | What we do |
|---|---|
| A harmful or broken tool ends up on many laptops | Two safety checks, a person's yes, a locked-down test machine (coming), numbered versions, one-command removal, and we can pull a tool back. |
| Hidden orders in a shared link trick the AI | Links are read by a separate program as plain text, with no access to passwords or keys. |
| Company code leaks to an outside AI | Only approved AI companies see code, and the bot uses short project descriptions instead of full code where it can. |
| Costs creep up without anyone noticing | A monthly budget per AI company and per account, use shown to maintainers, cheaper AIs for the bulk of the typing. |
| Sharing accounts breaks an AI company's rules | We recommend business plans or paid-as-you-go keys, and each company checks its own plans. |
| Too many ideas that are not worth it | Repeat check, maintainers can mark ideas "not now", and a simple order of priority. |
| Maintainers become a bottleneck | Several maintainers, ideas sorted by topic, and ideas passed on automatically after 24 hours. |

## 14. Decisions so far

- DeepSeek is off for now. Running AI models on our own computers may become a setup option.
- Blog posts are web pages, shown on the blog built into the dashboard.
- Each company runs DevExAI itself, on its own network, from an installer that keeps itself up to date.
- Raghav is the trial's admin and first maintainer. The other maintainers are placeholders for now.
- The person with the idea chooses whether their tool is built in public.
- Dashboard sign-in is email and password for now. Signing in with Slack comes later.
- Maintainers answer within 24 hours. After that, the bot passes the idea on.
- The Windows installer will be signed so Windows trusts it. We buy that certificate later, so early
  versions are not signed yet.
- Updates come from our own server, because DevExAI is a paid service. Only paying customers can
  download them. On both Windows and Linux the app updates itself, using the customer's licence key.

There are no open questions right now.
