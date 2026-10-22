# DevExAI deck generator

Builds `DevExAI.pptx` (22 slides) from the proposal in the root `README.md`.
Slides 6 to 8 are a demo: a one-minute video and screenshots from a test run in `demo/`.
The video `demo/DevExAI-flow.mp4` is not in git (it is on Drive); without it slide 6 shows the poster image.

Needs Python with `python-pptx`, plus Windows with PowerPoint for the animation and render steps.
Build into `out/`, not a temp folder: PowerPoint opens temp files in Protected View and cannot edit them.

```
python build.py out/v2.pptx                 # slides, photos, speaker notes
powershell -File anim.ps1 -Pptx <abs path>  # fade transitions + build animations
python scrub.py out/v2.pptx                 # clear author names PowerPoint writes
powershell -File render.ps1 -Pptx <abs path> -OutDir <dir>   # PNG per slide, for checking
```

Then copy `out/v2.pptx` to `../../DevExAI.pptx`.

Photos in `photos/` are from Unsplash under the Unsplash License; credits are in each slide's speaker notes.
