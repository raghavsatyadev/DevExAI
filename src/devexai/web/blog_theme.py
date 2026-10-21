"""The blog's own Material 3 Expressive styles, on top of the dashboard's (theme.py).

A hero surface per page (48 px corners, a slow cookie shape), posts as cards whose corners morph on hover,
display-size titles, a reading column for the post and an install panel beside it on wide screens.
Colours only through the dashboard's role variables, so light and dark both follow the device.
"""

BLOG_CSS = """
main{max-width:1240px}
.blog-hero{position:relative;overflow:hidden;isolation:isolate;background:var(--primary-container);
color:var(--on-primary-container);border-radius:48px;padding:44px 48px 40px;margin:12px 0 28px;
animation:pop var(--default-effects)}
.blog-hero .shape{position:absolute;z-index:-1;right:-70px;top:-90px;width:320px;aspect-ratio:1;background:var(--primary);
opacity:.16;clip-path:var(--cookie);animation:drift 90s linear infinite}
.blog-hero .shape.two{right:auto;left:55%;top:auto;bottom:-150px;width:220px;background:var(--tertiary);opacity:.12;
animation-direction:reverse}
.eyebrow{font:700 13px/20px var(--font);letter-spacing:.1em;text-transform:uppercase;margin:0 0 10px;opacity:.8}
.blog-hero h1{font-size:45px;line-height:52px;font-weight:700;letter-spacing:-.02em;margin:0 0 14px;max-width:24ch;
text-wrap:balance}
.lede,.blog-hero .byline{font-size:18px;line-height:28px;max-width:62ch;margin:0}
.blog-hero .byline strong{font-weight:700}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px}
.chip{display:inline-flex;align-items:center;gap:6px;min-height:32px;padding:4px 14px;border-radius:8px;
font:600 13px/20px var(--font);background:color-mix(in srgb,var(--on-primary-container) 10%,transparent)}
.blog-hero .row{margin:24px 0 0}
.blog-hero a.btn.tonal{background:var(--surface-lowest);color:var(--primary)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}
.post-card{display:flex;flex-direction:column;gap:8px;min-height:200px;padding:24px 26px;border-radius:28px;
background:var(--surface-low);color:var(--on-surface);text-decoration:none;
transition:border-radius var(--default-spatial),background var(--default-effects),transform var(--default-spatial)}
.post-card:hover{border-radius:44px;background:var(--surface-high)}
.post-card:active{transform:scale(.98)}
.post-card .chip{align-self:flex-start;background:var(--secondary-container);color:var(--on-secondary-container)}
.post-card h2{font-size:24px;line-height:32px;margin:4px 0 0;text-wrap:balance}
.post-card .go{margin-top:auto;font-weight:700;color:var(--primary)}
.layout{display:grid;grid-template-columns:minmax(0,1fr) 400px;gap:24px;align-items:start}
.layout.single{grid-template-columns:minmax(0,860px)}
.side{position:sticky;top:84px;display:flex;flex-direction:column;gap:16px}
.post section,.panel{background:var(--surface-low);border-radius:28px;padding:24px 28px;margin:0 0 16px}
.side .panel{margin:0}
.panel.lift{background:var(--surface-lowest);border-radius:32px;
box-shadow:0 1px 3px var(--shadow),0 8px 28px -8px var(--shadow)}
.post h2,.panel h2{display:flex;align-items:center;gap:12px;font-size:24px;line-height:32px;margin:0 0 12px}
.post h2::before,.panel h2::before{content:"";flex:none;width:14px;height:14px;background:var(--primary);
clip-path:var(--cookie)}
.panel h3{font-size:18px;margin:20px 0 6px}
.post p,.post li,.panel p,.panel li{font-size:16px;line-height:26px;max-width:72ch}
.post p{margin:0 0 12px}.post p:last-child{margin-bottom:0}
.post ul,.post ol,.panel ul,.panel ol{margin:4px 0 8px;padding-left:24px}
.post li,.panel li{margin:4px 0;padding-left:4px}
.post li::marker,.panel li::marker{color:var(--primary);font-weight:700}
.files-list li{font-family:var(--mono);font-size:14px}
ol.steps{list-style:none;counter-reset:step;padding:0;margin:8px 0 12px}
ol.steps>li{counter-increment:step;position:relative;padding:0 0 18px 48px;margin:0}
ol.steps>li::before{content:counter(step);position:absolute;left:0;top:-2px;width:32px;height:32px;border-radius:50%;
display:grid;place-items:center;background:var(--primary);color:var(--on-primary);font:700 15px/1 var(--font)}
ol.steps .row{margin:10px 0 0}
.note{border-left:4px solid var(--tertiary);padding:2px 0 2px 14px;margin:12px 0}
.code{position:relative}.code pre{padding-right:96px}
.code button.copy{position:absolute;top:6px;right:6px;min-height:32px;padding:4px 14px}
code{font:13px/1.4 var(--mono);background:var(--surface-container);padding:1px 6px;border-radius:6px;cursor:copy}
code.copied,button.copied{background:var(--success-container);color:var(--on-success-container)}
a.btn{display:inline-flex;align-items:center;justify-content:center;font:600 14px/20px var(--font);min-height:40px;
padding:10px 22px;border-radius:999px;background:var(--primary);color:var(--on-primary);text-decoration:none;
transition:border-radius var(--fast-spatial),transform var(--fast-spatial)}
a.btn:active{border-radius:12px;transform:scale(.96)}
a.btn.tonal{background:var(--secondary-container);color:var(--on-secondary-container)}
a.btn.big{min-height:56px;width:100%;font-size:16px}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:12px 0}
details.file{background:var(--surface-container);border-radius:16px;padding:6px 14px;margin:8px 0}
details.file>summary{font:14px/1.5 var(--mono);padding:6px 0}
details.file pre{background:var(--surface-lowest)}
.empty-blog{padding:48px 16px;text-align:center;background:var(--surface-low);border-radius:28px}
@media (max-width:1000px){.layout{grid-template-columns:minmax(0,1fr)}.side{position:static}}
@media (max-width:760px){.blog-hero{border-radius:32px;padding:28px 24px}.blog-hero h1{font-size:34px;line-height:42px}
.post section,.panel{padding:20px}}
"""
