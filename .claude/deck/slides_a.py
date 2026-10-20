"""Slides 1-9: intro, idea, people, flow, safety, resources, review, updates."""
from helpers import (H, ACCENT, ACCENT_SOFT, AMBER, AMBER_SOFT, GREEN, GREEN_SOFT, INK,
                     LIGHT, MARGIN, MUTED, NAVY, RED, RED_SOFT, SKY, WHITE, W, arrow,
                     blank, card, chip, header, notes, photo, rect, shade, step,
                     text)

CW = W - 2 * MARGIN  # content width


def cols(n, gap=0.3, width=CW, x0=MARGIN):
    w = (width - gap * (n - 1)) / n
    return [(x0 + i * (w + gap), w) for i in range(n)]


def s01_title(prs):
    s = blank(prs, NAVY)
    photo(s, "title", 0, 0, W, H)
    shade(s, NAVY, 0.82)
    notes(s, "Photo: Annie Spratt on Unsplash (Unsplash License), unsplash.com/photos/QckxruozjRg")
    step(1)
    text(s, MARGIN, 1.5, 10, 0.4, "PROPOSAL · DRAFT FOR REVIEW", size=14, bold=True,
         color=SKY)
    text(s, MARGIN, 2.0, 12, 1.0, "DevExAI — the company AI toolsmith", size=44,
         bold=True, color=WHITE)
    step(2)
    text(s, MARGIN, 3.2, 10.5, 1.4,
         "Anyone drops an idea into team chat. AI checks it is safe, researches it, builds "
         "a ready-to-install tool for our AI coding assistants, and publishes a short post. "
         "The person with the idea gets the credit.", size=20, color=LIGHT, line=1.2)
    step(3)
    for (x, w), label in zip(cols(3, 0.25, 11.0),
                             ["Claude · Gemini · ChatGPT", "Any chat platform",
                              "Built as a product"]):
        chip(s, x, 5.3, w, 0.55, label, fill=ACCENT, color=WHITE, size=16)


def s02_problem(prs, n):
    s = blank(prs)
    header(s, "01 · The problem", "Good AI tricks get lost in chat", n)
    items = [
        ("Found every week", "A blog post, a GitHub repo, a new prompt, a new MCP server "
         "that makes AI coding or code review better."),
        ("Then lost", "The knowledge stays in one person's head or disappears in a "
         "chat thread."),
        ("Never shared", "Nobody has time to turn it into something the whole company "
         "can install in one step."),
    ]
    pw = 3.3
    lw = CW - pw - 0.3
    photo(s, "problem", W - MARGIN - pw, 1.75, pw, 4.85)
    notes(s, "Photo: Arif Riyanto on Unsplash (Unsplash License), unsplash.com/photos/G1N9kDHqBrQ")
    for i, (t, b) in enumerate(items):
        step(i + 1)
        y = 1.75 + i * 1.3
        rect(s, MARGIN, y, lw, 1.15, fill=LIGHT)
        rect(s, MARGIN, y + 0.18, 0.07, 0.79, fill=ACCENT, radius=0)
        text(s, MARGIN + 0.3, y, 0.5, 1.15, str(i + 1), size=26, bold=True, color=ACCENT,
             anchor="m")
        text(s, MARGIN + 0.9, y, lw - 1.15, 1.15,
             [[(t, {"bold": True, "color": NAVY, "size": 18})], b], size=16, color=MUTED,
             anchor="m", spacing=2)
    step(4)
    rect(s, MARGIN, 5.75, lw, 0.85, fill=ACCENT_SOFT)
    text(s, MARGIN + 0.35, 5.75, lw - 0.7, 0.85,
         [[("DevExAI's answer: ", {"bold": True, "color": ACCENT}),
           "a chat bot that turns a shared idea into a safe, reviewed tool everyone "
           "installs with one command."]], size=18, color=NAVY, anchor="m")


def s03_idea(prs, n):
    s = blank(prs)
    header(s, "02 · The idea", "From a chat message to a ready tool", n)
    steps = [
        ("Idea", "Any colleague posts text or links in chat."),
        ("Safety gate", "Strict check before any work starts."),
        ("Plan", "Claude Opus researches with our project context."),
        ("Build", "A cheaper model writes code and tests."),
        ("Review", "Opus reviews every line; a human approves."),
        ("Publish", "Short post with install steps; idea credited."),
    ]
    bw, gap = 1.62, 0.48
    for i, (t, b) in enumerate(steps):
        step(i + 1)
        x = MARGIN + i * (bw + gap)
        accent = GREEN if i == 5 else (RED if i == 1 else ACCENT)
        rect(s, x, 1.8, bw, 2.75, fill=LIGHT)
        rect(s, x, 1.8, bw, 0.09, fill=accent, radius=0)
        text(s, x + 0.18, 2.05, bw - 0.3, 0.4, str(i + 1), size=22, bold=True, color=accent)
        text(s, x + 0.18, 2.55, bw - 0.3, 0.4, t, size=17, bold=True, color=NAVY)
        text(s, x + 0.18, 3.05, bw - 0.3, 1.45, b, size=14, color=MUTED)
        if i < 5:
            arrow(s, x + bw + 0.08, 3.0, 0.32, 0.32)
    step(7)
    for (x, w), label in zip(cols(3, 0.25),
                             ["Opus plans · cheaper models build",
                              "No release without a human yes",
                              "The poster is named in the post"]):
        chip(s, x, 5.1, w, 0.65, label, size=16)


def s04_people(prs, n):
    s = blank(prs)
    header(s, "03 · Who is involved", "Four roles, one thread per idea", n)
    roles = [
        ("Poster", "Any colleague. Sends an idea — text, links, or both — to the bot."),
        ("Maintainers", "A small group. Approve paid resources and releases, decide unsure "
         "cases, own the project summaries."),
        ("The bot", "Safety check, research, planning, building, testing, publishing "
         "and every update."),
        ("Readers", "Everyone. Read the post and install the tool for a project or "
         "their whole machine."),
    ]
    for i, ((x, w), (t, b)) in enumerate(zip(cols(4), roles)):
        step(i + 1)
        card(s, x, 1.75, w, 2.55, t, b, title_size=20)
    step(5)
    text(s, MARGIN, 4.6, CW, 0.4, "Picking a maintainer for each idea", size=18, bold=True,
         color=NAVY)
    flow = ["Topic match (e.g. Android, backend, security)", "Otherwise round-robin",
            "No reply in time (e.g. one working day) → next maintainer, everyone told"]
    widths = [3.6, 2.6, 5.0]
    x = MARGIN
    for i, (label, w) in enumerate(zip(flow, widths)):
        chip(s, x, 5.15, w, 0.8, label, fill=LIGHT, color=INK, size=14, bold=False)
        x += w
        if i < 2:
            arrow(s, x + 0.1, 5.4, 0.28, 0.3)
            x += 0.48


def s05_steps(prs, n):
    s = blank(prs)
    header(s, "04 · How an idea travels", "Eight steps, all visible in the idea's thread", n)
    steps = [
        ("Submit", "Text and/or links to the bot. Gets a tracking number and a thread."),
        ("Safety gate", "Nothing starts until the idea and every link pass."),
        ("Research", "Reads links, checks for duplicates, uses project summaries."),
        ("Plan", "Claude Opus posts a plain-language plan in the thread."),
        ("Resources", "Free is automatic. Paid or login goes to a maintainer."),
        ("Build & test", "Cheaper model, in a sandbox, with tests and a README."),
        ("Review", "Opus review, safety check again, human final yes."),
        ("Publish", "Versioned release, short blog post, poster credited."),
    ]
    grid = cols(4, 0.25)
    for i, (t, b) in enumerate(steps):
        x, w = grid[i % 4]
        y = 1.7 + (i // 4) * 2.45
        step(i + 1)
        accent = RED if i == 1 else (AMBER if i == 4 else (GREEN if i == 7 else ACCENT))
        card(s, x, y, w, 2.2, t, b, accent=accent, badge=f"Step {i}")


def s06_safety(prs, n):
    s = blank(prs)
    header(s, "05 · Strict safety gate", "Nothing starts before this passes", n)
    step(1)
    text(s, MARGIN, 1.7, 6.5, 0.4, "Rejected or flagged", size=18, bold=True, color=NAVY)
    risks = ["Adult content, hate, harassment, violence, policy breaches",
             "Malware, credential stealers, miners, hidden network calls",
             "Hidden instructions in web pages aimed at the AI",
             "Requests to leak secrets, customer data or company code",
             "Licences we cannot use, or piracy"]
    for i, r in enumerate(risks):
        y = 2.2 + i * 0.72
        rect(s, MARGIN, y + 0.2, 0.22, 0.22, fill=RED, radius=0.5)
        text(s, MARGIN + 0.4, y, 6.3, 0.62, r, size=15, color=INK, anchor="m")
    step(2)
    x0 = 7.75
    text(s, x0, 1.7, 5, 0.4, "Three outcomes", size=18, bold=True, color=NAVY)
    outcomes = [("Pass", "Work continues.", GREEN, GREEN_SOFT),
                ("Unsure", "The assigned maintainer decides in chat.", AMBER, AMBER_SOFT),
                ("Reject", "Poster told why, politely; maintainer copied.", RED, RED_SOFT)]
    for i, (t, b, c, soft) in enumerate(outcomes):
        y = 2.2 + i * 1.1
        rect(s, x0, y, 4.98, 0.95, fill=soft)
        text(s, x0 + 0.25, y, 1.2, 0.95, t, size=18, bold=True, color=c, anchor="m")
        text(s, x0 + 1.45, y, 3.4, 0.95, b, size=15, color=INK, anchor="m")
    step(3)
    rect(s, MARGIN, 5.85, CW, 0.75, fill=NAVY)
    text(s, MARGIN + 0.3, 5.85, CW - 0.6, 0.75,
         "Links open in an isolated sandbox, never on a laptop. The same check runs again "
         "on the finished code.", size=16, color=WHITE, anchor="m")


def s07_resources(prs, n):
    s = blank(prs)
    header(s, "06 · Resources", "Free is automatic. Paid or login goes to a human.", n)
    lanes = [
        ("Fast lane", GREEN, GREEN_SOFT,
         "Free and needs no account: open-source libraries, public docs, free public "
         "APIs without a key.",
         "Uses it automatically and notes it in the thread."),
        ("Escalation lane", AMBER, AMBER_SOFT,
         "Paid, behind a login, or needs an API key, a licence or a new account.",
         "Stops and asks the maintainers in chat: what it is, why, and the cost."),
    ]
    for (x, w), (t, c, soft, what, does) in zip(cols(2, 0.4), lanes):
        step(1 if t == "Fast lane" else 2)
        rect(s, x, 1.7, w, 3.55, fill=soft)
        text(s, x + 0.35, 1.9, w - 0.7, 0.5, t, size=22, bold=True, color=c)
        text(s, x + 0.35, 2.5, w - 0.7, 1.1,
             [[("When: ", {"bold": True, "color": NAVY}), what]], size=16, color=INK)
        text(s, x + 0.35, 3.6, w - 0.7, 0.8,
             [[("Bot: ", {"bold": True, "color": NAVY}), does]], size=16, color=INK)
        if t == "Escalation lane":
            for i, b in enumerate(["Approve", "Deny", "Suggest alternative"]):
                chip(s, x + 0.35 + (0, 1.55, 3.0)[i], 4.5, (1.4, 1.3, 2.4)[i], 0.5, b,
                     fill=WHITE, color=c, size=14)
    step(3)
    rect(s, MARGIN, 5.55, CW, 1.05, fill=NAVY)
    text(s, MARGIN + 0.3, 5.55, CW - 0.6, 1.05,
         ["The bot never creates accounts, enters passwords or spends money. Keys go into "
          "a secret store, never into chat.",
          "The fast lane only skips resource approval — every release still needs a human yes."],
         size=15, color=WHITE, anchor="m")


def s08_review(prs, n):
    s = blank(prs)
    header(s, "07 · Review and approve", "Three checks before anything ships", n)
    gates = [
        ("Opus code review", "Correctness, security, tests, readability. Problems "
         "go back to the builder, then Opus reviews again."),
        ("Safety check again", "On the finished code and every dependency. A safe idea "
         "can still produce unsafe code."),
        ("A human says yes", "A maintainer gives the final approval. Nothing "
         "reaches colleagues without it."),
    ]
    bw, gap = 3.6, 0.665
    for i, (t, b) in enumerate(gates):
        step(i + 1)
        x = MARGIN + i * (bw + gap)
        card(s, x, 1.75, bw, 2.9, t, b, badge=str(i + 1),
             accent=GREEN if i == 2 else ACCENT, title_size=19, body_size=15)
        if i < 2:
            arrow(s, x + bw + 0.15, 3.05, 0.36, 0.34)
    step(4)
    pw = 2.7
    photo(s, "review", W - MARGIN - pw, 4.95, pw, 1.8)
    notes(s, "Photo: X (@disruptxn) on Unsplash (Unsplash License), unsplash.com/photos/kwzWjTnDPLk")
    rect(s, MARGIN, 4.95, CW - pw - 0.3, 1.8, fill=ACCENT_SOFT)
    text(s, MARGIN + 0.4, 4.95, CW - pw - 1.1, 1.8,
         [[("Only Opus reviews code. ", {"bold": True, "color": ACCENT}),
           "The cheaper builder never approves code, and never reviews its own work."]],
         size=18, color=NAVY, anchor="m")


def s09_updates(prs, n):
    s = blank(prs)
    header(s, "08 · Keeping people informed", "The poster and maintainer see every stage", n)
    stages = ["Received", "Safety check", "Researching", "Plan ready",
              "Waiting for approval", "Building", "Testing", "Under review",
              "Published or stopped"]
    rows = [stages[:5], stages[5:]]
    for r, row in enumerate(rows):
        step(r + 1)
        x, y = MARGIN, 1.85 + r * 1.05
        for i, st in enumerate(row):
            w = 1.95 if len(st) < 14 else 2.6
            last = r == 1 and i == len(row) - 1
            chip(s, x, y, w, 0.6, st, fill=GREEN_SOFT if last else ACCENT_SOFT,
                 color=GREEN if last else ACCENT, size=14)
            x += w
            if i < len(row) - 1:
                arrow(s, x + 0.07, y + 0.16, 0.26, 0.28)
                x += 0.36
    text(s, MARGIN, 3.65, CW, 0.4, "“Waiting for approval” appears only when a paid "
         "resource or login is needed.", size=14, color=MUTED)
    step(3)
    pw = 2.93
    photo(s, "phone", W - MARGIN - pw, 4.3, pw, 1.95)
    notes(s, "Photo: freestocks on Unsplash (Unsplash License), unsplash.com/photos/mw6Onwg4frY")
    for (x, w), (t, b) in zip(cols(2, 0.3, CW - pw - 0.3), [
            ("Where", "Everything goes into the idea's own thread, so anyone can see what "
             "happened and why."),
            ("What they can do", "Reply to ask a question, add details, or stop the idea. "
             "If a step runs long, the bot says so.")]):
        card(s, x, 4.3, w, 1.95, t, b, title_size=19, body_size=15)


SLIDES = [s02_problem, s03_idea, s04_people, s05_steps, s06_safety, s07_resources,
          s08_review, s09_updates]
