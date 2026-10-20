"""Material 3 Expressive styling for the dashboard, as plain CSS (the page policy allows no scripts or fonts).

Colour roles, shapes, type and motion follow the M3 Expressive rules: colours only through role variables
(light and dark), pill buttons that morph to a rounded square while pressed, 24 px cards and 32 px hero
surfaces, spatial springs for containers and non-overshooting curves for colour and opacity, and one slow
decorative shape per bare page. Everything that moves stops when the device asks for reduced motion.
"""

from __future__ import annotations

import math


def _cookie(lobes: int = 9, depth: float = 0.07, steps: int = 144) -> str:
    """A MaterialShapes-style cookie outline as a CSS polygon."""
    points = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        r = 0.5 * (1 - depth + depth * math.cos(lobes * t))
        points.append(f"{50 + 100 * r * math.cos(t):.2f}% {50 + 100 * r * math.sin(t):.2f}%")
    return "polygon(" + ",".join(points) + ")"


COOKIE = _cookie()

_LIGHT = """
--primary:#4355b9;--on-primary:#fff;--primary-container:#dee0ff;--on-primary-container:#00105c;
--secondary:#5b5d72;--secondary-container:#e0e1f9;--on-secondary-container:#181a2c;
--tertiary:#77536d;--tertiary-container:#ffd7f1;--on-tertiary-container:#2d1228;
--error:#ba1a1a;--error-container:#ffdad6;--on-error-container:#410002;
--success-container:#b6f1b0;--on-success-container:#002204;
--surface:#fbf8ff;--surface-lowest:#fff;--surface-low:#f5f2fa;--surface-container:#efedf4;
--surface-high:#e9e7ef;--surface-highest:#e4e1e9;--on-surface:#1b1b21;--on-surface-variant:#46464f;
--outline:#767680;--outline-variant:#c6c5d0;--shadow:rgba(0,0,0,.14)"""

_DARK = """
--primary:#bac3ff;--on-primary:#08218a;--primary-container:#293ca0;--on-primary-container:#dee0ff;
--secondary:#c4c5dd;--secondary-container:#434659;--on-secondary-container:#e0e1f9;
--tertiary:#e6bad7;--tertiary-container:#5d3c55;--on-tertiary-container:#ffd7f1;
--error:#ffb4ab;--error-container:#93000a;--on-error-container:#ffdad6;
--success-container:#1d5420;--on-success-container:#b6f1b0;
--surface:#121318;--surface-lowest:#0d0e13;--surface-low:#1b1b21;--surface-container:#1f1f25;
--surface-high:#29292f;--surface-highest:#34343a;--on-surface:#e4e1e9;--on-surface-variant:#c6c5d0;
--outline:#90909a;--outline-variant:#46464f;--shadow:rgba(0,0,0,.5)"""

_TOKENS = f"""
:root{{color-scheme:light dark;{_LIGHT};
--fast-spatial:350ms cubic-bezier(.42,1.67,.21,.9);--default-spatial:500ms cubic-bezier(.38,1.21,.22,1);
--fast-effects:150ms cubic-bezier(.31,.94,.34,1);--default-effects:200ms cubic-bezier(.34,.8,.34,1);
--emphasized-decelerate:cubic-bezier(.05,.7,.1,1);
--font:"Google Sans Flex","Google Sans Text","Google Sans","Roboto Flex",Roboto,"Segoe UI Variable Text",
"Segoe UI",system-ui,sans-serif;--mono:"Roboto Mono","Cascadia Mono",Consolas,ui-monospace,monospace}}
@media (prefers-color-scheme:dark){{:root{{{_DARK}}}}}
"""

_BASE = """
*{box-sizing:border-box}
body{font:400 15px/1.5 var(--font);margin:0;color:var(--on-surface);background:var(--surface);
-webkit-font-smoothing:antialiased}
a{color:var(--primary);text-underline-offset:3px;text-decoration-thickness:1px}
main{max-width:1180px;margin:0 auto;padding:24px}
h1{font-size:32px;line-height:40px;font-weight:700;letter-spacing:-.01em;margin:8px 0 18px;
font-feature-settings:"tnum"}
h2{font-size:22px;line-height:28px;font-weight:600;margin:32px 0 12px}
h3{font-size:16px;font-weight:600;margin:18px 0 6px}
b{font-weight:600}
.muted{color:var(--on-surface-variant)}
.late,.err{color:var(--error);font-weight:700}
:focus-visible{outline:3px solid var(--primary);outline-offset:2px;border-radius:12px}
"""

_BAR = """
header{position:sticky;top:0;z-index:5;display:flex;gap:6px;align-items:center;flex-wrap:wrap;
padding:10px 20px;background:var(--surface-container);border-radius:0 0 28px 28px}
header .brand{display:flex;align-items:center;gap:10px;margin-right:14px;font-size:18px;font-weight:700;
color:var(--on-surface);text-decoration:none}
header .mark{width:30px;height:30px;background:var(--primary);clip-path:var(--cookie)}
header nav{display:flex;gap:4px;flex-wrap:wrap}
header nav a,header .who a{color:var(--on-surface-variant);text-decoration:none;font-weight:600;
padding:8px 16px;border-radius:999px;transition:background var(--fast-effects),color var(--fast-effects)}
header nav a:hover,header .who a:hover{background:color-mix(in srgb,var(--on-surface) 8%,transparent)}
header nav a[aria-current],header .who a[aria-current]{background:var(--secondary-container);
color:var(--on-secondary-container)}
header .grow{flex:1}
header .who{color:var(--on-surface-variant);font-size:14px}
header form{margin:0}
"""

_CONTROLS = """
button,summary.btn{font:600 14px/20px var(--font);letter-spacing:.01em;min-height:40px;padding:10px 22px;
border:0;border-radius:999px;cursor:pointer;background:var(--primary);color:var(--on-primary);
transition:border-radius var(--fast-spatial),transform var(--fast-spatial),background var(--fast-effects),
box-shadow var(--fast-effects);display:inline-flex;align-items:center;justify-content:center;gap:8px}
button:hover,summary.btn:hover{box-shadow:inset 0 0 0 100px color-mix(in srgb,currentColor 8%,transparent)}
button:active,summary.btn:active{border-radius:12px;transform:scale(.96)}
button.tonal,summary.btn.tonal{background:var(--secondary-container);color:var(--on-secondary-container)}
button.danger,summary.btn.danger{background:var(--error-container);color:var(--on-error-container)}
button.danger.strong{background:var(--error);color:var(--surface-lowest)}
button.text{background:transparent;color:var(--primary);padding:10px 14px}
button.big{min-height:56px;width:100%;font-size:16px;border-radius:999px}
button.big:active{border-radius:16px}
summary.btn{list-style:none;user-select:none}summary.btn::-webkit-details-marker{display:none}
details.confirm{display:inline-block}
details.confirm[open] summary.btn{background:var(--surface-highest);color:var(--on-surface)}
details.confirm form{display:flex;gap:8px;align-items:center;margin-top:8px;animation:pop var(--default-effects)}
input[type=text],input[type=email],input[type=password],select{font:400 15px var(--font);width:100%;
min-height:48px;padding:10px 16px;margin:6px 0 14px;color:var(--on-surface);background:var(--surface-lowest);
border:1px solid var(--outline);border-radius:16px;transition:border-color var(--fast-effects),
box-shadow var(--fast-effects)}
select{width:auto;min-width:160px}select.wide{width:100%}
input:hover,select:hover{border-color:var(--on-surface)}
input:focus,select:focus{outline:0;border-color:var(--primary);box-shadow:inset 0 0 0 1px var(--primary)}
input:user-invalid{border-color:var(--error);box-shadow:inset 0 0 0 1px var(--error)}
form b{display:inline-block;margin:4px 6px 0 0;font-size:13px;letter-spacing:.02em;color:var(--on-surface-variant)}
"""

_SURFACES = """
.card{background:var(--surface-low);border-radius:24px;padding:20px 24px;margin:12px 0}
table{width:100%;border-collapse:separate;border-spacing:0;background:var(--surface-low);border-radius:24px;
overflow:hidden;font-feature-settings:"tnum"}
th,td{text-align:left;padding:12px 16px;vertical-align:top;border-bottom:1px solid var(--outline-variant)}
tr:last-child>td,tr:last-child>th{border-bottom:0}
th{font-weight:600;font-size:13px;letter-spacing:.02em;color:var(--on-surface-variant);
background:var(--surface-container)}
tr:has(td){transition:background var(--fast-effects)}
tr:has(td):hover{background:color-mix(in srgb,var(--on-surface) 5%,transparent)}
td:first-child{white-space:nowrap}
td form{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:0}
td form input,td form select{margin:0;min-height:40px;width:auto;flex:1 1 140px}
.pill{display:inline-flex;align-items:center;gap:6px;padding:4px 12px 4px 10px;border-radius:999px;
font-size:13px;font-weight:600;white-space:nowrap;background:var(--surface-highest);color:var(--on-surface)}
.pill::before{content:"";width:9px;height:9px;background:currentColor;
clip-path:polygon(50% 0,61% 39%,100% 50%,61% 61%,50% 100%,39% 61%,0 50%,39% 39%)}
.pill.wait{background:var(--tertiary-container);color:var(--on-tertiary-container)}
.pill.wait::before{clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%)}
.pill.done{background:var(--success-container);color:var(--on-success-container)}
.pill.done::before{clip-path:circle(50%)}
.pill.bad{background:var(--error-container);color:var(--on-error-container)}
.pill.bad::before{clip-path:inset(8% round 2px)}
.flash{background:var(--secondary-container);color:var(--on-secondary-container);border-radius:20px;
padding:14px 20px;margin:0 0 12px;white-space:pre-wrap;animation:pop var(--default-effects)}
.flash.warn{background:var(--tertiary-container);color:var(--on-tertiary-container)}
pre{font:13px/1.5 var(--mono);white-space:pre-wrap;word-break:break-word;background:var(--surface-container);
padding:14px 16px;border-radius:16px;margin:6px 0}
details{margin:6px 0}details>summary{cursor:pointer;border-radius:12px;padding:4px 0}
.actions{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.actions form{background:var(--surface-low);border-radius:24px;padding:18px 20px;margin:0;
display:flex;flex-direction:column;align-items:flex-start;gap:4px}
.actions form b{font-size:15px;color:var(--on-surface);margin-bottom:4px}
.actions form input,.actions form select{margin:2px 0 10px}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px}
.filters a{padding:6px 16px;border-radius:12px;border:1px solid var(--outline-variant);text-decoration:none;
color:var(--on-surface-variant);font-weight:600;font-size:14px;transition:background var(--fast-effects)}
.filters a:hover{background:color-mix(in srgb,var(--on-surface) 8%,transparent)}
.filters a[aria-current]{background:var(--secondary-container);border-color:transparent;
color:var(--on-secondary-container)}
.empty{display:flex;flex-direction:column;align-items:center;gap:6px;padding:40px 16px;text-align:center;
background:var(--surface-low);border-radius:28px;animation:pop var(--default-effects)}
.empty .shape{width:72px;height:72px;background:var(--primary-container);clip-path:var(--cookie);
margin-bottom:8px}
.empty b{font-size:22px;font-weight:600}
"""

_HERO = """
body.bare{min-height:100vh;display:grid;place-items:center;overflow-x:hidden}
body.bare main{position:relative;width:100%}
.hero{position:fixed;width:min(90vmin,760px);aspect-ratio:1;right:-18vmin;top:-22vmin;z-index:-1;
background:var(--primary-container);clip-path:var(--cookie);opacity:.7;animation:drift 60s linear infinite}
.narrow{max-width:440px;margin:40px auto}
.narrow.card{background:var(--surface-lowest);border-radius:32px;padding:32px;
box-shadow:0 1px 3px var(--shadow),0 8px 24px -6px var(--shadow)}
.narrow.card form{margin-top:10px}
@keyframes drift{to{transform:rotate(360deg)}}
@keyframes pop{from{opacity:0;transform:scale(.98)}to{opacity:1;transform:none}}
@media (max-width:760px){main{padding:16px}table{display:block;overflow-x:auto}h1{font-size:26px;line-height:32px}
header{border-radius:0 0 20px 20px}}
@media (prefers-reduced-motion:reduce){*,*::before{animation:none!important;transition-duration:1ms!important}
button:active,summary.btn:active{transform:none}}
"""

CSS = _TOKENS + f":root{{--cookie:{COOKIE}}}" + _BASE + _BAR + _CONTROLS + _SURFACES + _HERO
