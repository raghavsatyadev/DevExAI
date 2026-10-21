"""HTML for the admin's Slack page. Tokens are write-only: the page only ever says whether one is set."""

from __future__ import annotations

from .pages import _hidden, e

_SECRET = 'type="password" autocomplete="off" spellcheck="false" maxlength="400"'


def _is_set(flag: bool) -> str:
    return '<span class="pill done">set</span>' if flag else '<span class="pill bad">not set</span>'


def _checks(checks) -> str:
    if checks is None:
        return ""
    rows = "".join(f'<tr><td><span class="pill {"done" if c.ok else "bad"}">{"OK" if c.ok else "Fix"}</span></td>'
                   f"<td>{e(c.text)}</td></tr>" for c in checks)
    return f"<h3>Last test</h3><table>{rows}</table>"


def slack_page(csrf: str, *, connected: bool, platform: str, bot_set: bool, app_set: bool, licence_set: bool,
               ideas: str, public: str, checks=None) -> str:
    if connected:
        state = '<span class="pill done">Connected</span>'
        switch = (f'<form method="post" action="/slack">{_hidden(csrf, op="connect")}'
                  f'<button class="tonal">Reconnect</button></form>'
                  f'<form method="post" action="/slack">{_hidden(csrf, op="disconnect")}'
                  f'<button class="danger">Disconnect</button></form>')
    else:
        state = f'<span class="pill wait">Not connected</span> <span class="muted">(chat now: {e(platform)})</span>'
        switch = (f'<form method="post" action="/slack">{_hidden(csrf, op="connect")}'
                  f'<button{"" if bot_set and app_set else " disabled"}>Connect to Slack</button></form>')
    keep = "leave empty to keep the saved one"
    return f"""<h1>Slack</h1>
<div class="card"><p>Status: {state}</p><div class="actions">{switch}
<form method="post" action="/slack">{_hidden(csrf, op="test")}<button class="tonal">Test connection</button></form>
</div>{_checks(checks)}</div>

<h2>Tokens</h2>
<form class="card" style="max-width:640px" method="post" action="/slack">{_hidden(csrf, op="tokens")}
<b>Bot User OAuth Token (xoxb-...)</b> {_is_set(bot_set)}
<input {_SECRET} name="bot_token" placeholder="{keep if bot_set else "xoxb-..."}" aria-label="Bot token">
<b>App-Level Token (xapp-...)</b> {_is_set(app_set)}
<input {_SECRET} name="app_token" placeholder="{keep if app_set else "xapp-..."}" aria-label="App token">
<button>Save tokens</button>
<p class="muted">Saved in the server's .env file, never shown again. After saving, press Connect (or Reconnect).</p>
</form>

<h2>Channels</h2>
<form class="card" style="max-width:640px" method="post" action="/slack">{_hidden(csrf, op="channels")}
<b>Ideas channel</b><input type="text" name="ideas" value="{e(ideas)}" required maxlength="81"
 pattern="#?[a-z0-9][a-z0-9_\\-]{{0,79}}" aria-label="Ideas channel">
<b>Announcements channel</b><input type="text" name="public" value="{e(public)}" required maxlength="81"
 pattern="#?[a-z0-9][a-z0-9_\\-]{{0,79}}" aria-label="Announcements channel">
<button>Save channels</button>
<p class="muted">Public channels. In each one, type <code>/invite @DevExAI</code> so the bot can read and post.</p>
</form>

<h2>Licence key</h2>
<form class="card" style="max-width:640px" method="post" action="/slack">{_hidden(csrf, op="licence")}
<b>Licence key for updates</b> {_is_set(licence_set)}
<input {_SECRET} name="licence" placeholder="{keep if licence_set else "licence key"}" aria-label="Licence key">
<button>Save licence key</button></form>

<h2>Setting up the Slack app</h2>
<ol class="card">
<li>At api.slack.com/apps: Create New App, From a manifest, pick the workspace and paste
 <code>docs/slack-app-manifest.yaml</code>.</li>
<li>Basic Information, App-Level Tokens: generate one with the <code>connections:write</code> scope. That is the
 xapp- token.</li>
<li>Install App, Install to Workspace. That gives the xoxb- token.</li>
<li>Paste both tokens above, create the two channels, invite the bot, then Test connection and Connect.</li>
<li>Give each maintainer on the People page the same email they use on Slack, so the bot knows them.</li>
</ol>"""
