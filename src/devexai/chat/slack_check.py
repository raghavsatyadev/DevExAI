"""Test a Slack setup step by step and say, in plain words, what to fix. Never shows a token."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Check:
    ok: bool
    text: str


def _err(e: Exception) -> str:
    resp = getattr(e, "response", None)
    return str(resp.get("error")) if resp is not None and hasattr(resp, "get") else type(e).__name__


def check_slack(bot_token: str, app_token: str, ideas: str, public: str, people, *, web=None) -> list[Check]:
    """bot token, app token, both channels (exist, bot is in them), and which maintainers Slack knows."""
    out: list[Check] = []
    if not bot_token.startswith("xoxb-"):
        out.append(Check(False, "The bot token is missing or is not a Bot User OAuth Token (it starts with xoxb-)."))
    if not app_token.startswith("xapp-"):
        out.append(Check(False, "The app token is missing or is not an App-Level Token (it starts with xapp-)."))
    if out:
        return out
    from slack_sdk import WebClient

    web = web or WebClient(token=bot_token)
    try:
        auth = web.auth_test()
        out.append(Check(True, f"Bot token works: signed in as @{auth.get('user')} in {auth.get('team')}."))
    except Exception as e:
        return [Check(False, f"Slack refused the bot token ({_err(e)}). Copy it again from Install App.")]
    try:
        WebClient().apps_connections_open(app_token=app_token)
        out.append(Check(True, "App token works: Socket Mode can connect."))
    except Exception as e:
        out.append(Check(False, f"Slack refused the app token ({_err(e)}). Generate one with the "
                                "connections:write scope under Basic Information > App-Level Tokens."))
    from .slack_ids import SlackIds

    ids = SlackIds(web, None)
    for label, name in (("Ideas channel", ideas), ("Announcements channel", public)):
        try:
            cid = ids.channel_id(name)
            member = web.conversations_info(channel=cid)["channel"].get("is_member")
            out.append(Check(bool(member), f"{label} {name}: " + (
                "the bot is in it." if member else f"type /invite @DevExAI in {name} so the bot can read and post.")))
        except LookupError:
            have = ", ".join(sorted(ids._channels)[:15]) or "none"
            out.append(Check(False, f"{label} {name}: no public channel with that name. Create it in Slack or "
                                    f"pick one of: {have}."))
        except Exception as e:
            out.append(Check(False, f"{label} {name}: could not check ({_err(e)})."))
    missing = []
    for p in people:
        if not p.email:
            missing.append(f"{p.name} (no email on the People page)")
            continue
        try:
            web.users_lookupByEmail(email=p.email)
        except Exception:
            missing.append(f"{p.name} ({p.email} is not in this Slack workspace)")
    out.append(Check(not missing, "Every maintainer is on Slack with the same email." if not missing else
                     "Not matched on Slack, so they act as ordinary users there: " + "; ".join(missing)))
    return out
