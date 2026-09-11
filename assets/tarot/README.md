# Optional Tarot Artwork

Tarot does not require images. Leave this directory empty and readings remain text-only.

When custom art is ready, add one image per card using the stable keys documented in `docs/tarot.md`, for example:

```text
major/00_the_fool.png
major/01_the_magician.png
cups/ace_of_cups.png
cups/king_of_cups.png
swords/ace_of_swords.png
wands/ace_of_wands.png
pentacles/ace_of_pentacles.png
```

Accepted extensions: PNG, JPG/JPEG, WEBP.

Keep master artwork upright. When Pillow is installed through the optional `tarot-artwork` extra, reversed draws are rotated at render time; a second set of reversed assets is not required.
