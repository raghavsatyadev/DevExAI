"""Slides 10-19: outputs, install, models, product, cost, rules, rollout, risks, ask."""
from helpers import (H, W, ACCENT, ACCENT_SOFT, AMBER, AMBER_SOFT, GREEN, GREEN_SOFT, INK,
                     LIGHT, MARGIN, MUTED, NAVY, RED, SKY, WHITE, blank, card, chip,
                     header, notes, photo, rect, shade, step, table, text)
from slides_a import CW, cols

MONO = {"font": "Courier New", "bold": True, "color": WHITE}


def s10_outputs(prs, n):
    s = blank(prs)
    header(s, "09 · What gets built", "Ready-to-install tools for AI coding assistants", n)
    kinds = [("Skills", "Reusable “how to do X” guides the assistant follows."),
             ("MCP servers", "Small services that give assistants new abilities, e.g. "
              "read the issue tracker."),
             ("Tools & scripts", "Command-line helpers."),
             ("Plugins", "Bundles that install several of the above at once.")]
    for i, ((x, w), (t, b)) in enumerate(zip(cols(4), kinds)):
        step(i + 1)
        card(s, x, 1.75, w, 2.3, t, b, title_size=20)
    step(5)
    text(s, MARGIN, 4.4, CW, 0.4, "Claude Code first; Gemini CLI and Codex next",
         size=18, bold=True, color=NAVY)
    for (x, w), label in zip(cols(3, 0.3), ["Claude · Claude Code", "Gemini · Gemini CLI",
                                            "ChatGPT · Codex"]):
        chip(s, x, 4.95, w, 0.7, label, size=18)
    text(s, MARGIN, 5.9, CW, 0.5, "The builder writes Claude Code files today. Later: one shared core with a thin adapter "
         "per assistant, so an idea is never rebuilt three times.", size=16, color=MUTED)


def s11_install(prs, n):
    s = blank(prs)
    header(s, "10 · Installing", "Your project or your whole machine — your choice", n)
    opts = [("This project only", "--project",
             "The tool's files go into the project's .claude/, .gemini/ and .codex/ folders "
             "and can be committed, so the whole team gets it.", "Team or project tools"),
            ("My whole machine", "--global",
             "The same files go into those folders in your home folder and work in every "
             "project.",
             "Personal productivity tools")]
    for (x, w), (t, flag, b, good) in zip(cols(2, 0.4), opts):
        step(1 if flag == "--project" else 2)
        rect(s, x, 1.75, w, 3.6, fill=LIGHT)
        text(s, x + 0.35, 1.95, w - 0.7, 0.5, t, size=22, bold=True, color=NAVY)
        rect(s, x + 0.35, 2.6, w - 0.7, 0.6, fill=NAVY)
        text(s, x + 0.55, 2.6, w - 1.1, 0.6, [[("python devex.py install <tool> " + flag, MONO)]],
             size=14, anchor="m")
        text(s, x + 0.35, 3.4, w - 0.7, 1.1, b, size=16, color=INK)
        text(s, x + 0.35, 4.65, w - 0.7, 0.5,
             [[("Good for: ", {"bold": True, "color": ACCENT}), good]], size=16,
             color=INK)
    step(3)
    for (x, w), label in zip(cols(3, 0.3), ["Shows each change, asks first",
                                            "Never runs the tool's code",
                                            "Uninstall keeps your edits"]):
        chip(s, x, 5.6, w, 0.65, label, fill=GREEN_SOFT, color=GREEN, size=16)
    text(s, MARGIN, 6.4, CW, 0.45, "devex.py is one Python file from /blog/devex.py. It never edits settings files, "
         "and never overwrites other files without --force.", size=14, color=MUTED)


def s12_models(prs, n):
    s = blank(prs)
    header(s, "11 · Which AI does what", "Opus thinks and reviews; cheaper models will type", n)
    rows = [["Job", "Model", "Why"],
            ["Safety gate", "Claude Opus; malware and secret scanners to add",
             "Safety mistakes are expensive."],
            ["Research & planning", "Claude Opus", "Best reasoning; thinking, not bulk typing."],
            ["Writing code", "Claude Opus today; Gemini Flash or a local model planned",
             "Cheap and fast at following a clear plan."],
            ["Code review", ("Claude Opus only", {"bold": True, "color": ACCENT}),
             "A cheaper model never reviews code or its own work."],
            ["Blog post", "Written from the approved plan", "No extra model needed."],
            ["Experiments / evals", "Local models on an optional 24 GB GPU",
             "Free to run once the GPU is bought."]]
    table(s, MARGIN, 1.75, [2.7, 4.85, 4.58], rows, size=15, head_size=15, row_h=0.62)


def s13_product(prs, n):
    s = blank(prs)
    header(s, "12 · Built as a product", "Fits any company's setup", n)
    text(s, MARGIN, 1.45, CW, 0.4, "Each company picks its own parts in one settings file. "
         "The core flow stays the same.", size=16, color=MUTED)
    step(1)
    parts = [("Chat platform", "Slack today; Teams, Google Chat, Discord and more "
              "through a small adapter"),
             ("AI accounts", "Claude today; Gemini and ChatGPT next — subscriptions or API keys"),
             ("Code host", "GitHub, GitLab, Bitbucket, Azure DevOps, self-hosted Git (later)"),
             ("Secret store", "A secret file on the server today; Vault or a cloud secret manager"),
             ("Blog / website", "Built into the dashboard; posts are Markdown files any site "
              "can show"),
             ("Where it runs", "The company's own server, from a Windows or Linux package that "
              "updates itself")]
    for i, (t, b) in enumerate(parts):
        x = MARGIN + (i % 2) * 3.65
        y = 2.05 + (i // 2) * 1.55
        rect(s, x, y, 3.45, 1.4, fill=LIGHT)
        text(s, x + 0.25, y + 0.15, 3.0, 0.4, t, size=17, bold=True, color=NAVY)
        text(s, x + 0.25, y + 0.55, 3.0, 0.8, b, size=14, color=MUTED)
    step(2)
    x0 = MARGIN + 7.45
    w0 = CW - 7.45
    rect(s, x0, 2.05, w0, 4.5, fill=ACCENT_SOFT)
    text(s, x0 + 0.3, 2.2, w0 - 0.6, 0.45, "Account pool (planned)", size=20, bold=True, color=ACCENT)
    text(s, x0 + 0.3, 2.75, w0 - 0.6, 3.7,
         ["• Several subscriptions and API keys per provider",
          "• One hits its limit → the next takes over",
          "• Usage and monthly budget tracked per account",
          "• Keys live in the secret store, never in chat",
          "• Never swaps to a weaker reviewer: review stays Claude Opus",
          "• Check your plans allow a shared bot (business, enterprise or API)"],
         size=15, color=INK, spacing=8)


def s14_cost(prs, n):
    s = blank(prs)
    header(s, "13 · Cost and resources", "Mostly plans we already pay for", n)
    groups = [
        ("Our own setup", ACCENT,
         ["Company enterprise Claude and Gemini plans", "Covers a shared company bot, "
          "code under company terms", "Opus planning and review use the most quota",
          "Add accounts or keys to the pool when busy"]),
        ("Optional extras", AMBER,
         ["DeepSeek for cheap extra building — off for now",
          "One machine with a 24 GB GPU for local models and testing"]),
        ("Also needed", GREEN,
         ["A bot app on the chat platform (usually free)", "A small always-on server on the "
          "company network", "A company Git repository for the tools", "The blog, already built into "
          "the dashboard"]),
    ]
    for i, ((x, w), (t, c, items)) in enumerate(zip(cols(3), groups)):
        step(i + 1)
        rect(s, x, 1.75, w, 4.1, fill=LIGHT)
        rect(s, x, 1.75, w, 0.09, fill=c, radius=0)
        text(s, x + 0.3, 2.0, w - 0.6, 0.45, t, size=20, bold=True, color=c)
        text(s, x + 0.3, 2.6, w - 0.6, 3.6, ["• " + i for i in items], size=15, color=INK,
             spacing=10)


def s15_rules(prs, n):
    s = blank(prs)
    header(s, "14 · Rules the bot always follows", "Seven rules, no exceptions", n)
    rules = ["Nothing starts until the safety gate passes.",
             "Nothing paid, needing a login, or released without a maintainer's yes.",
             "Claude Opus reviews every line before a human sees it.",
             "Company code and summaries are read-only; never sent to unapproved services.",
             "Web pages and posts are information, never instructions.",
             "Every action is logged in the idea's thread.",
             "Every published tool can be uninstalled cleanly."]
    for i, r in enumerate(rules):
        step(i + 1)
        col, row = (0, i) if i < 4 else (1, i - 4)
        x = MARGIN + col * 6.2
        y = 1.8 + row * 1.15
        rect(s, x, y, 0.7, 0.7, fill=ACCENT, radius=0.5)
        text(s, x, y, 0.7, 0.7, str(i + 1), size=20, bold=True, color=WHITE, align="c",
             anchor="m")
        text(s, x + 0.95, y - 0.1, 4.95, 0.9, r, size=17, color=INK, anchor="m")


def s16_rollout(prs, n):
    s = blank(prs)
    header(s, "15 · Rollout", "The core is built; next, grow it into a product", n)
    phases = [("Pilot", "Built", "Slack intake (our platform), safety gate, plan, "
               "dashboard, blog post. One team."),
              ("Automate", "Mostly built", "Built: builder, Opus review, auto post, install command. "
               "Next: tests in a sandbox, account pool."),
              ("Company-wide", "Next", "All teams, maintainer rotation, more AI "
               "assistants."),
              ("Product", "Started", "Windows package and updater exist. Next: Linux, "
               "second chat platform (e.g. Teams)."),
              ("Local models", "When needed", "GPU machine for cheap building and evals, "
               "if usage justifies it.")]
    for i, ((x, w), (t, when, b)) in enumerate(zip(cols(5, 0.2), phases)):
        step(i + 1)
        rect(s, x, 1.75, w, 3.15, fill=LIGHT)
        rect(s, x, 1.75, w, 0.09, fill=ACCENT, radius=0)
        text(s, x + 0.2, 1.95, w - 0.4, 0.35, f"Phase {i + 1}", size=14, bold=True,
             color=ACCENT)
        text(s, x + 0.2, 2.3, w - 0.4, 0.4, t, size=18, bold=True, color=NAVY)
        text(s, x + 0.2, 2.75, w - 0.4, 0.35, when, size=14, bold=True,
             color=GREEN if when in ("Built", "Mostly built") else AMBER)
        text(s, x + 0.2, 3.15, w - 0.4, 1.7, b, size=14, color=MUTED)
    step(6)
    text(s, MARGIN, 5.2, CW, 0.4, "How we will know it works", size=18, bold=True,
         color=NAVY)
    metrics = ["Ideas submitted", "% shipped", "Installs per tool", "Time to release",
               "Cost per tool", "“Was this useful?”"]
    for (x, w), m in zip(cols(6, 0.15), metrics):
        chip(s, x, 5.7, w, 0.6, m, fill=GREEN_SOFT, color=GREEN, size=14)


def s17_risks(prs, n):
    s = blank(prs)
    header(s, "16 · Risks", "What could go wrong, and how we handle it", n)
    rows = [["Risk", "Handling"],
            ["Harmful or buggy tool on many laptops", "Two safety checks, human approval, "
             "sandboxed builds (next), versions, one-command uninstall, pull a release."],
            ["Hidden instructions in a link", "Links read by a separate process as plain "
             "data; no secrets while reading."],
            ["Company code leaks to an outside AI", "Only approved providers see code; "
             "summaries instead of full source where possible."],
            ["Costs grow quietly", "Budgets per provider and account, usage shown to "
             "maintainers, cheap models do bulk work."],
            ["Account pool breaks provider terms", "Business, enterprise plans or API keys "
             "recommended; each company checks its plans."],
            ["Too many low-value ideas", "Duplicate check, “not now” label, simple priority "
             "queue."],
            ["Maintainer bottleneck", "Several maintainers, topic routing, automatic "
             "reassignment after a timeout."]]
    table(s, MARGIN, 1.7, [4.1, 8.03], rows, size=14, head_size=15, row_h=0.6)


def s18_questions(prs, n):
    s = blank(prs)
    header(s, "17 · Decisions", "What we have decided so far", n)
    qs = [("DeepSeek", "Off for now. Self-hosted models may become a setup option.", None),
          ("Blog", "Posts are Markdown files, served by the dashboard's own blog page.",
           None),
          ("Maintainers", "Raghav is the pilot's admin and first maintainer. Maintainers "
           "answer within 24 hours.", None),
          ("Offering the product", "Each company hosts it on its own network, from a "
           "Windows or Linux package that updates itself.", None)]
    for i, (t, b, tag) in enumerate(qs):
        step(i + 1)
        x, w = cols(2, 0.4)[i % 2]
        y = 1.75 + (i // 2) * 2.45
        card(s, x, y, w, 2.25, t, b, badge=f"D{i + 1}", title_size=19, body_size=16,
             accent=MUTED if tag else ACCENT)
        if tag:
            chip(s, x + w - 1.4, y + 0.25, 1.15, 0.45, tag, fill=AMBER_SOFT, color=AMBER,
                 size=14)


def s19_close(prs):
    s = blank(prs, NAVY)
    photo(s, "team", 0, 0, W, H)
    shade(s, NAVY, 0.82)
    notes(s, "Photo: Cherrydeck on Unsplash (Unsplash License), unsplash.com/photos/UpsEF48wAgk")
    step(1)
    text(s, MARGIN, 1.6, 10, 0.4, "NEXT STEPS", size=14, bold=True, color=SKY)
    text(s, MARGIN, 2.1, 12, 0.9, "Turn good ideas into tools everyone uses", size=40,
         bold=True, color=WHITE)
    steps = ["Review this proposal", "Pick the pilot team",
             "Run the pilot with that team"]
    for i, ((x, w), st) in enumerate(zip(cols(3, 0.3), steps)):
        step(i + 2)
        rect(s, x, 3.6, w, 1.5, fill=ACCENT)
        text(s, x + 0.3, 3.75, w - 0.6, 0.45, str(i + 1), size=22, bold=True, color=SKY)
        text(s, x + 0.3, 4.25, w - 0.6, 0.7, st, size=20, bold=True, color=WHITE)
    step(5)
    text(s, MARGIN, 5.6, CW, 0.5, "Full details: README.md in the DevExAI project.",
         size=16, color=LIGHT)


SLIDES = [s10_outputs, s11_install, s12_models, s13_product, s14_cost, s15_rules,
          s16_rollout, s17_risks, s18_questions]
