# DevExAI ideas from X bookmarks (2026-10-20)

Source: x-digest's bookmark pass, `x-digest/plans/2026-10-18-bookmarks-plan.md` and its follow-up
studies. Each idea is written the way a person would post it in #ai-ideas, so it can be pasted into
DevExAI as is (console prompt or `/devex-idea <text>`). OpenQodex is left out on purpose.

Left out as not company tooling: PixelBoard, Claude desktop second instance, omarchy-apple-dev,
HydraFusion, free/open model announcements, the agent control plane (too large for one tool), and
Decision 2.0 (our eval found it no better than the current local filter).

## 1. Prompt-cache meter for Claude Code (tooling)

> A Claude Code mod that shows how warm the prompt cache is: hit %, tokens read/written, and a
> countdown to when the cache lapses, with a tip to /compact or /clear before rewriting a big cold
> context. It makes no model calls and adds no tokens. Ship a reviewed, pinned copy instead of the
> live `npx` installer (it pulls from GitHub main). Based on
> https://github.com/davila7/claude-code-templates (mods/observability/prompt-cache-control).

Why us: cuts token spend for everyone on large sessions. Our study: zero extra cost, no network, no
file writes. Needs Claude Code 2.1.287+; terminal band only, Desktop shows it as a pane.

## 2. Cheap-first model escalation skill (ai, tooling)

> A shared skill that tells the coding assistant to try the cheapest model that can do a subtask
> first (small/local model for yes/no checks, a fast model for reading and mechanical edits) and
> escalate to Opus only for design-heavy work or when stuck, using Claude Code's advisor. Each team
> records which setup worked for which task in the skill. Docs: https://code.claude.com/docs/en/advisor

Why us: same quality for less money, and one company default instead of everyone guessing.
Check the tweet's settings keys against the docs; they looked embellished.

## 3. 500-line file rule with a check (tooling)

> A CLAUDE.md / AGENTS.md rule plus a Stop hook: keep every source file at or under 500 lines; if a
> change pushes a file past it, split it by responsibility before finishing. Generated files,
> lockfiles and vendored code are exempt. Inspired by https://x.com/count_slopula/status/2111734252219818363

Why us: smaller files mean cheaper, more accurate agent edits. We already use the rule by hand;
the hook makes it automatic for every repo.

## 4. Android end-to-end test skill using e2e (android)

> A skill that sets up tester.army's e2e (Apache-2.0, https://tester.army/e2e) for a Compose app and
> writes the first test for its main flow. It pins the test device (never a TV or phone that happens
> to be on adb), uses the release APK when the debug build has a second launcher (LeakCanary), and
> flags buttons with no accessible name, suggesting merged semantics or testTag.

Why us: our spike ran natively on Windows and passed 3/3 on GrammarFix in about 20 s per run. The
gotchas it found (device pinning, LeakCanary launcher, unlabelled Compose buttons) are exactly what a
skill should know so nobody hits them again.

## 5. Material 3 Expressive UI skill (android, mobile)

> A skill holding a directed design prompt (with a Specifications section) so the assistant builds
> Material 3 Expressive screens in one shot instead of generic Material 2 looks. Source prompts:
> https://x.com/csinco/status/2109692275530055848 and https://x.com/csinco/status/2107362177049104853

Why us: Android teams get consistent, current-looking UI from the assistant. The prompt text is in
the linked posts and needs copying out before building.

## 6. Company skills pulled from a git repo (tooling)

> Keep the company's assistant skills in one git repo that Claude Code (and other assistants) pull
> from, instead of copying them into every machine and project. Teams get updates with a pull, and
> changes are reviewed like code. Idea from https://x.com/kevinasrx/status/2108969972785668515

Why us: this is how DevExAI's own released tools should reach people; one source of truth, and
smaller per-project context.

## 7. Fast Mermaid diagrams in generated docs (tooling, web)

> A skill or doc-pipeline step that renders Mermaid diagrams with Pele (MIT, no dependencies,
> 100-500x faster than mermaid-cli) so assistant-written docs and reports ship real diagrams instead of
> code blocks. https://x.com/kepano/status/2111472054293913749

Why us: cheap and local; useful for README, plans and DevExAI's own blog posts.
