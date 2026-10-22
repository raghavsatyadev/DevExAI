"""Loads settings.toml (non-secret settings) and .env (secrets) into typed objects."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Maintainer:
    name: str
    topics: tuple[str, ...] = ()
    email: str = ""      # dashboard sign-in name; settings only seed the first start
    admin: bool = False


@dataclass(frozen=True)
class FetchSettings:
    max_links: int = 5
    max_bytes: int = 1_000_000
    timeout_seconds: int = 15
    max_chars_per_page: int = 20_000


@dataclass(frozen=True)
class LLMSettings:
    provider: str = "claude_cli"
    claude_bin: str = "claude"
    timeout_seconds: int = 900
    recordings: str = ""  # folder: claude_cli saves its replies there, provider "replay" answers from it
    models: dict[str, str] = field(
        default_factory=lambda: {"gate": "claude-opus-5-5", "planner": "claude-opus-5-5",
                                 "builder": "claude-opus-5-5", "reviewer": "claude-opus-5-5"}
    )

    def model_for(self, role: str) -> str:
        try:
            return self.models[role]
        except KeyError:
            raise KeyError(f"no model configured for role {role!r} under [llm.models]") from None


@dataclass(frozen=True)
class WebSettings:
    enabled: bool = True
    host: str = "127.0.0.1"           # "0.0.0.0" or a LAN address to share it on the company network
    port: int = 8765
    allowed_hosts: tuple[str, ...] = ()  # names people type to reach it, e.g. "devexai.corp.local"
    tls_cert: str = ""                # PEM files; needed to serve beyond this machine
    tls_key: str = ""
    insecure_http: bool = False       # serve the network without TLS (passwords travel in clear)
    public_url: str = ""              # address a tunnel (e.g. ngrok) gives it on the internet; links use it

    @property
    def tls(self) -> bool:
        return bool(self.tls_cert and self.tls_key)


@dataclass(frozen=True)
class BlogSettings:
    dir: Path = Path("data/blog")   # published posts are HTML files here
    base_url: str = ""              # if set, chat links are base_url + file name

    def link(self, name: str) -> str:
        return f"{self.base_url.rstrip('/')}/{name}" if self.base_url else (self.dir / name).as_posix()


@dataclass(frozen=True)
class UpdateSettings:
    url: str = ""            # our update server; empty = never check. The licence key is in .env
    check_hours: float = 24

    @property
    def licence(self) -> str:
        return os.environ.get("DEVEXAI_LICENCE_KEY", "").strip()


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path("data/devexai.db")
    ideas_channel: str = "#ai-ideas"
    public_channel: str = "#ai-tools"
    maintainer_timeout_hours: float = 24
    chat_adapter: str = "console"
    llm: LLMSettings = field(default_factory=LLMSettings)
    fetch: FetchSettings = field(default_factory=FetchSettings)
    web: WebSettings = field(default_factory=WebSettings)
    blog: BlogSettings = field(default_factory=BlogSettings)
    update: UpdateSettings = field(default_factory=UpdateSettings)
    maintainers: tuple[Maintainer, ...] = ()
    build_by: str = "bot"  # "bot": the AI writes the tool after approval; "person": a person builds it

    @property
    def builds_dir(self) -> Path:
        """The built tools' files, one folder per idea, next to the database."""
        return self.db_path.parent / "builds"


def load_dotenv(path: Path) -> None:
    """Minimal .env reader: KEY=VALUE lines; existing environment variables win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def save_env(path: Path, updates: dict[str, str]) -> None:
    """Set KEY=VALUE lines in .env (in place, other lines and comments kept) and in this process."""
    for key, value in updates.items():
        if not key.isidentifier() or any(c in value for c in "\r\n\"'#") or value != value.strip():
            raise ValueError(f"refusing to write {key} to .env: unexpected characters")
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    left = dict(updates)
    for n, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and key in left:
            lines[n] = f"{key}={left.pop(key)}"
    lines += [f"{k}={v}" for k, v in left.items()]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    os.environ.update(updates)


def _web(raw: dict) -> WebSettings:
    return WebSettings(**{**raw, "allowed_hosts": tuple(h.lower() for h in raw.get("allowed_hosts", ())),
                          "public_url": raw.get("public_url", "").strip().rstrip("/")})


def load_settings(path: Path) -> Settings:
    data = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    bot = data.get("bot", {})
    llm = data.get("llm", {})
    blog = data.get("blog", {})
    maintainers = tuple(
        Maintainer(name=m["name"], topics=tuple(t.lower() for t in m.get("topics", ())),
                   email=m.get("email", ""), admin=bool(m.get("admin", False)))
        for m in data.get("maintainers", ())
    )
    if not maintainers:
        raise ValueError(f"{path}: at least one [[maintainers]] entry is required")
    defaults = LLMSettings()
    build_by = data.get("build", {}).get("by", "bot")
    if build_by not in ("bot", "person"):
        raise ValueError(f'{path}: [build] by must be "bot" or "person", not {build_by!r}')
    return Settings(
        db_path=Path(bot.get("db_path", "data/devexai.db")),
        ideas_channel=bot.get("ideas_channel", "#ai-ideas"),
        public_channel=bot.get("public_channel", "#ai-tools"),
        maintainer_timeout_hours=float(bot.get("maintainer_timeout_hours", 24)),
        chat_adapter=data.get("chat", {}).get("adapter", "console"),
        llm=LLMSettings(
            provider=llm.get("provider", defaults.provider),
            claude_bin=llm.get("claude_bin", defaults.claude_bin),
            timeout_seconds=int(llm.get("timeout_seconds", defaults.timeout_seconds)),
            recordings=str(llm.get("recordings", "")),
            models={**defaults.models, **llm.get("models", {})},
        ),
        fetch=FetchSettings(**data.get("fetch", {})),
        web=_web(data.get("web", {})),
        blog=BlogSettings(dir=Path(blog.get("dir", "data/blog")), base_url=blog.get("base_url", "")),
        update=UpdateSettings(**data.get("update", {})),
        maintainers=maintainers,
        build_by=build_by,
    )
