# The deck

"Shared spaces on Cyberplex": 25 slides with speaker notes. It covers the problem, the goal and the model, the demonstration and its team, the Cyberplex workspace page for the tenant owner, what the demo showed, the limits, and this repository.

- `shared-spaces-on-cyberplex.pdf` is the deck as a 16:9 PDF, one slide per page, without the speaker notes. It was rendered locally from the sources below, in a standard sans-serif font, and the small icons are drawn as plain dots.
- `deck.json` lists the slides in order, with the sections and the fonts.
- `slides/<id>.html` is one slide each: a single `<section>` on a 1920 x 1080 canvas, styled inline, with the speaker notes in its `<aside>`.

The slides are written in the restricted HTML format of a slide-deck tool: custom elements such as `<x-icon>` and `<x-shape>` and an `<aside>` for notes. A browser will show the text and layout, but not the icons or arrows; use the PDF to read it as intended. The two screen pictures are sketches drawn from the workspace page's source, not screenshots.

The slides refer to OAA, the Organizational Agent Architecture: https://github.com/Chuck3PointZero/OAA. See the main README for the version and install.
