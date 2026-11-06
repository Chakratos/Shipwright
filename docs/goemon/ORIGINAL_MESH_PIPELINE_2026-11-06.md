# Original Goemon mesh integration: local static reference stage (2026-11-06)

## Why the first renderer uses a separate static mesh format

The user's genuine, hash-verified NTSC-U NG5E ROM contains four original
character resource groups, each occupying four file-table entries:

| Numeric character ID | Name (externally corroborated) | Original resource IDs |
| ---: | --- | --- |
| 0 | Goemon | 288–291 |
| 1 | Ebisumaru | 292–295 |
| 2 | Sasuke | 296–299 |
| 3 | Yae | 300–303 |

The validated original ROM was examined **on the private Windows runner**.
All 16 resource files were independently scanned for direct F3DEX vertex
DMA instructions, triangle streams and valid in-file skeleton headers.
**None contains a source-verified directly readable mesh/display list.**
The +1 resources contain PIC0000 data; other resource payloads still
require original file-format/graphics decompressor analysis. Random bytes
resembling triangle opcodes do not establish mesh data.

We have implemented a strict decoder for F3DEX display lists for when
the original graphics stream has been located and decoded:

- `tools/goemon/re/original_f3dex_geometry.py` (original N64 opcodes,
  big-endian vertex/triangle records, strict pointer bounds)
- `tools/goemon/re/original_graphics_scan.py` (read-only ROM evidence)
- synthetic F3DEX and ROM regression tests.

As a **rendering bridge, not a substitute for original animation**, the
four publicly available static N64-model rips from *The Models Resource*
are supported. They retain the recognizable source-game geometry/textures,
but their geometry has **not** been bitwise matched against the owned ROM,
and they have **no original skeleton or animation**.

Original source pages:

- Goemon: https://models.spriters-resource.com/nintendo_64/mysticalninjastarringgoemon/asset/291117/
- Ebisumaru: https://models.spriters-resource.com/nintendo_64/mysticalninjastarringgoemon/asset/291027/
- Sasuke: https://models.spriters-resource.com/nintendo_64/mysticalninjastarringgoemon/asset/291233/
- Yae: https://models.spriters-resource.com/nintendo_64/mysticalninjastarringgoemon/asset/291015/

## Local import pipeline (no full Ship build)

`tools/goemon/re/prepare_reference_models.py` downloads and caches the four
ZIPs outside the repository. It converts source OBJ/MTL/PNG data using
`tools/goemon/re/import_reference_models.py` into local `GOMESH01` files
with source metadata and companion textures. No binary model or texture is
ever added to GitHub, its Actions artifacts, or source control.

One-time use is automated on the private Windows runner by a push commit
containing **`[goemon-models]`**. It writes to:

```text
C:\actions-runner-goemon\character-models\
    source-zips\Goemon.zip
    source-zips\Ebisumaru.zip
    source-zips\Sasuke.zip
    source-zips\Yae.zip
    Goemon\model.gomesh
    Goemon\manifest.json
    Goemon\texture_000.png
    Ebisumaru\...
    Sasuke\...
    Yae\...
    local-reference-summary.json
```

The import is independently runnable via:

```powershell
py -3 tools\goemon\re\prepare_reference_models.py --output-dir "C:\actions-runner-goemon\character-models"
```

`OriginalReferenceMesh.hpp` is the matching standalone C++20 reader of
this versioned static geometry format. The Python exporter and C++ reader
both have native/synthetic tests, no heavyweight Ship compile necessary.

## Still required for a real playable Goemon

1. Finish linking the **verified static model and texture data** into a
   Ship rendering component, using local-only assets and respecting the
   existing scene / renderer lifecycles. The current bridge is not yet
   a rendered, playable character.
2. Reverse-engineer the original model compression, animated skeleton,
   correct scale and limb matrices from the owned ROM and actual graphics
   renderer. Replace static reference geometry with verified ROM-derived
   meshes and authentic animations; *The Models Resource* rips cannot
   supply original animation.
3. Connect original movement and controls to a proper playable actor,
   Zelda collision, scene exits and interactions. The diagnostic actor and
   its gold marker were a **feasibility study only** and are not being
   cosmetically patched into the finished player.
4. Integrate all four characters' weapons, special skills, scenes and
   Randomizer.

Avoid expensive Windows Ship builds until a complete engine-visible
rendering milestone is implemented. Keep binary assets local on the PC.
