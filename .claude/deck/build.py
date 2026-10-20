"""Build DevExAI.pptx: python build.py <out.pptx>"""
import sys

import slides_a
import slides_b
from helpers import new_deck

prs = new_deck()
slides_a.s01_title(prs)
for i, make in enumerate(slides_a.SLIDES + slides_b.SLIDES, start=2):
    make(prs, i)
slides_b.s19_close(prs)
prs.save(sys.argv[1])
print("saved", sys.argv[1], len(prs.slides), "slides")
