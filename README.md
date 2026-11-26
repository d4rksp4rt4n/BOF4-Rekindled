# BOF4 Rekindled – Breath of Fire IV uncut content, fixes and enhancements (GOG PC)

*Formerly "Breath of Fire IV – English Uncut". Installs made with the old installer are picked up as they are.*

> **This page describes the version in development.** Widescreen and the Controller options are not in
> the current release (1.2) yet; they are still being tested.

A patcher for the English GOG release of *Breath of Fire IV* that restores content cut from the Western
release and fixes several problems of the PC port. It comes as a small Windows installer with a GUI. Every
option can be switched on or off, and "Restore original files" undoes everything. 

The options come in four groups. Content and fixes are on by default; enhancements and controller options
are experimental and off by default.

| Group | Option | What it does |
|---|---|---|
| Restored content | Restore cut content | Everything the English release removed: the four cut scenes (Ryu and Ursula at the checkpoint, Ursula on Zig's ship, Emperor Soniel's attack on Fou-Lu, the Saldine Island bath scene) with English text; the Japan-only Dengeki Store, with its original English (US PlayStation) text and the graphics the English port dropped; and Scias' Identify ability at level 3, with element icons for the weakness/resistance list as in the PS1 hack |
| | Better Descriptions (by Naro) | Naro's descriptions of hidden item, equipment and master effects and resistances |
| Fixes | PC port fixes | Stutter: the per-frame screen clear runs on the GPU instead of forcing a GPU readback in GOG's ddraw wrapper (random hitches). Wobble: in rooms with lighting effects (North Chamba and a few others) the PC port snaps the 3D to whole PS1 pixels, so walls and floors swim like on a PlayStation; this keeps the exact positions it already has |
| | Correct music loops | Songs loop from their real loop point instead of replaying the intro, and without the click/gap the PC player makes at every restart |
| | PlayStation reverb | The PC music is dry MP3 recordings; this adds the PS1 sound chip's reverb back at runtime, using the PS1 game's own setting |
| Enhancements (experimental) | 60 fps | The game runs at 30 fps; this draws an in-between frame for each one (camera and characters move smoothly). Scroll Lock switches it off and on while playing |
| | Widescreen | At a 16:9 resolution the game stretches its 4:3 picture to the full width. This keeps the proportions right and shows more of the 3D scene at the sides instead; menus, text and the HUD stay in the centred 4:3 area, and movies play in 4:3 with black bars. Choose the resolution in the game: Camp → Settings → Screen adjust |
| | Sprite depth scaling | Characters are fixed-size sprites while the 3D around them shrinks with distance, so a villager up the street looks like it grows next to the floor under it. This shrinks characters further away than the player like the 3D around them (the player and everyone closer keep their size). Insert switches between shrink only, full perspective and off while playing |
| Controller (experimental) | Start/Back as Start/Select | A controller's Start and Back (View/Select) buttons work as the PS1's Start and Select. The PC port leaves them on the stick clicks and its Key/Pad Setting screen can't move them. A new key setup also puts the camera on LB/RB and Change Rank on the right stick click. Button hints (the world map's Menu panel, battle's Menu and Enemy(s) labels, buttons named in help text) show keyboard keys even with a controller; with this their keycaps show the controller's button while you play with it (A, B, LB… in their colours, ✕ ○ □ △…, or numbers, as chosen under Button icons), and keys again once you press a key |
| | Button icons | Numbers (original), Xbox or PlayStation. The game names controller buttons with circled numbers ①–⑩ on the Key/Pad Setting screen. Xbox and PlayStation show the button itself instead: A, B, X, Y, LB, RB, View, Menu, LS, RS, or ✕, ○, □, △, L1, R1, Select, Start, L3, R3 |

The installer explains each option when you point at it.

## For players

1. You need the English GOG version of Breath of Fire IV. The installer checks every file and refuses
   to change anything that isn't the original English GOG data.
2. Download `BOF4_Rekindled.exe` from this repository's **Releases** page, put it next to `BOF4.exe`
   and run it. Switch on the options you want and press **Apply**.
3. Originals are kept in `BOF4_Rekindled_backup`. Run the installer again any time to change options or
   to restore the original files. On start it checks GitHub for a newer release and shows a link if
   there is one (nothing is downloaded or sent).

Notes:
- **Saves past Saldine:** a save made in the unmodded game after the party reached the Saldine Island
  creek will freeze when it enters the creek with "Restore cut content" on, because the bath scene still
  counts as unseen. Use an earlier save, or play that save without that option.
- **Windows warnings:** the installer is unsigned, edits `BOF4.exe` and adds a DLL, so Windows SmartScreen
  or antivirus software may warn about it. The full source is here; you can build it yourself.
- **Music tuning:** optional `BOF4_reverb.ini` next to `BOF4.exe`:
  ```ini
  [reverb]
  wet=100   ; reverb level in % of the PS1's (0 = off)
  ```
- **60 fps bug reports:** add to `BOF4_reverb.ini`:
  ```ini
  [fps60]
  dump=1    ; Pause saves the last second of frames to fps60_dump\ (about 6 MB per frame)
  log=1     ; per-second statistics in BOF4_fps60.log
  ```
  Press Pause right after a glitch and attach the `fps60_dump` folder (zipped) to the issue.
- **Sprite depth scaling tuning:** in `BOF4_reverb.ini`:
  ```ini
  [sprites]
  strength=100  ; % of the full perspective size change
  grow=0        ; 1 = characters closer to the camera than the player get bigger too (full perspective)
  ```
  Insert cycles shrink only, full and off while playing, starting from this setting; the window title shows
  the current mode.
- **Controller Start/Back with an existing key setup:** the fix works with any `bof4.cfg`, but if your
  Key/Pad Setting has the camera (or anything else) on Back or Start, those buttons do both. Move it in
  Camp → Setting → Key/Pad Setting, e.g. the camera to LB/RB. Only a new `bof4.cfg` gets the new defaults.

## Status – testing wanted

This is a young project tested on one machine. Reports are very welcome. Open an issue with what you
did, where you were in the game, and, if possible, a save file.

| Area | Status |
|---|---|
| Restored scenes | All four tested in game: the checkpoint, Ursula on Zig's ship, Soniel vs. Fou-Lu and the Saldine bath scene |
| Dengeki Store | Tested in game: shop and lottery work, with English text and the clerk's portrait. The signs on the building and in the shop stay Japanese: they are painted into the textures, and the store never had an English release |
| PC port fixes (stutter), reverb | Tested over long play sessions |
| Music loops | Many songs checked by ear and sample-exact in game; not every song in every area has been heard. Report any song whose loop sounds off (jump, gap, replayed intro), with the area |
| Identify (in Restore cut content) | Tested in game: HP, Exp, treasure, info, and the element icons with their weak/normal/strong colours |
| **60 fps** | **Experimental.** Tested in towns, fields, the world map, battles, menus, dialogue and the fishing minigame. Report anything that flickers, jumps or tears only with the option on (Scroll Lock compares), ideally with a capture (see above) |
| **Widescreen** | **Experimental.** Tested at 1920×1080 and 3840×2160 on the world map, in fields (camera turned all the way round), battles (battle swirl, targeting, Gigaflare, Blizzard, all summons, the dragon Breath attacks), the fishing minigame, the Sand Flier race, busy towns (Synesta), the plains, every map and field of the game (walked with random encounters off), shops, dungeons with 2D effects (the Shrine's lasers and lamps, the Tomb's ghost blocks, waterfall mist), menus and the intro movie, also together with 60 fps and sprite depth scaling. HUD at the screen edges: the fishing minigame's panels, the field compass, the world map's Menu panel and road box, battle's Enemy(s) box; other panels (menus, dialogue, the battle command menu and party status) keep their 4:3 positions. Known limits: the game's own draw distance shows more at the far corners (the Sand Flier race's distant walls and grass pop in at the sides too); some sprites still vanish at the 4:3 edge (the fish in Flood Tide). Report anything cut off at the sides, popping in near the edges, or stuck in the 4:3 area when it should cover the screen, with a screenshot |
| **Controller Start/Back, button icons** | **New, experimental.** Icons checked in game on the Key/Pad Setting screen (both sets, normal and selected colours). Start/Back tested with an Xbox-order controller. Controller button hints tested with a real controller (Xbox set): the world map's Menu panels, battle's Menu and Enemy(s) labels and buttons named in help text, switching back to keys and forth to the pad. GOG's input wrapper reports pads in Xbox order, so other pads should show the right icons too; report a pad whose icons don't match its buttons |
| PC port fixes (wobble), sprite depth scaling | **New.** Tested in North Chamba and Synesta. Known limit: the Tomb's translucent puzzle blocks still snap to whole pixels (their own renderer draws them in 2D and keeps no exact positions). Report rooms that still swim, or characters whose size looks wrong or jumps |
| **Steam version** | **Experimental, not yet tested on a real Steam install.** Its `BOF4.exe` is the GOG exe inside an Enigma wrapper (encrypted on disk); every other file equals GOG's. The installer leaves the exe untouched and adds `dsound.dll`, which forwards sound to the system `dsound.dll` and, at the game's first DirectSound call (after it has unpacked), applies the same exe changes in memory and logs the result to `BOF4_Rekindled.log`. Apply and Restore remove the `version.dll` of an earlier test build. Reports from Steam owners (with that log) are very welcome |

## Building from source

Requirements (Windows):
- Python 3 with `numpy` and `Pillow`
- Visual Studio Build Tools with the C++ x86 compiler (for `bof4_reverb.dll`)
- the .NET Framework 4 C# compiler that ships with Windows (for the installer)

Inputs (never committed; set the paths in `config.py` or with environment variables):

| Setting | Default | What |
|---|---|---|
| `BOF4_GAME` | parent of this folder | the game folder |
| `BOF4_CLEAN_EXE` | `backup\BOF4.exe` | an untouched GOG `BOF4.exe` |
| `BOF4_CLEAN_DAT` | `<game>\DAT_backup` | untouched English GOG `DAT` files |
| `BOF4_DESC_ZIP` | `<game>\Breath of Fire IV - Better Descriptions-*.zip` | Naro's PC release |

Build:
```bat
reverb\build.bat
steam\build.bat
py build_mod.py
```
`build_mod.py` writes `mod\BOF4_Rekindled.exe`. The installer embeds only the differences from the original
files, plus SHA-256 checks, for every combination of options.

The loop analysis in `loops\` (only needed to regenerate `reverb\loops_table.h`) also needs `ffmpeg`
(`FFMPEG`) and the extracted US PS1 disc (`BOF4_PS1_BGM`). Run it as `analyze.py`, then `measure.py`,
`final.py` and `make_table.py`.

`derive_scenes.py` (only needed to re-check the scene redirects) also needs the clean US PS1 disc image
(`BOF4_PS1_US_BIN`, Track 1 `.bin`) and navarchos' Uncensored hack applied and extracted
(`BOF4_PS1_HACK_WORLD`, its `BIN\WORLD` folder).

## Repository layout

| Path | Contents |
|---|---|
| `build_mod.py` | builds the installer (variants, diffs, art, C# compile) |
| `patch_uncut_en.py` | the game patches: exe code caves, restored text, Dengeki Store, Identify. Its command line is an older local patcher |
| `identify_icons.py` | the Identify screen's element icons (font glyphs, labels); run it for a preview image |
| `button_icons.py` | Xbox/PlayStation button icons in place of the circled numbers (font glyphs); run it for a preview image |
| `derive_scenes.py` | derives the scene redirects from the US PS1 disc and the Uncensored hack |
| `installer.cs` | the GUI installer (WinForms) |
| `steam\` | Steam loader: `dsound.dll` proxy (`bof4_loader.c`, no C runtime) that patches the unpacked exe in memory; `mem_list.py` makes its patch list |
| `reverb\` | `bof4_reverb.dll`: PS1 SPU reverb (`bof4_reverb.c`), loop engine (`loops.c`, `loops_table.h`), 60 fps interpolation (`fps60.c`; built with `/DFPS_TEST` it is an offline tester for frame captures), sprite depth scaling (`sprites.c`) and widescreen (`widescreen.c`) |
| `loops\` | analysis that derives loop points from the PS1 sequences and the PC recordings |
| `lzhuf.py` | codec for the PC DAT files' compressed chunks |
| `art\` | installer artwork (see credits) |
| `mod\README.txt` | the readme shipped with releases |

## How it works (short)

- **Restored scenes:** the US release cut three scenes in the event scripts (early script ends and
  skips). `derive_scenes.py` diffs the US PS1 disc against navarchos' Uncensored hack and maps the
  changes onto the script data in `BOF4.exe`; a hook on the script interpreter (code caves in unused
  `.text` padding) then runs the hack's script code at those points. The Saldine bath setup the US build
  dropped is re-added as x86 code. The restored English lines are appended to the areas' text tables.
- **Dengeki Store:** two event flags held every frame, the US PS1 English text, and the two chunks the
  English port dropped (from the Japanese GOG release).
- **Identify:** Scias' level-3 entry gets the ability back. Its Data panel draws the 12 element names one
  Japanese character (12 px) apart, so the English names overlap. As in navarchos' PS1 hack they become
  icons: 12 glyphs added to the game's text font (`INIT.DAT`), drawn from the PS1 element icons, so the
  panel's red/grey/blue resistance colours tint them like letters. The labels in the battle text
  (`AB000_00`, `BTLEND`) become those characters, and the HP separator, which shared the unknown-item
  "?", becomes "/" (the hack's v1.1 fix). An unseen item's "?" marks are drawn 8 px apart instead of
  12, so long names stay inside the Treasure panel.
- **Controller:** GOG's input wrapper reports every pad in Xbox order (button 1 = A ... 7 = Back,
  8 = Start, 9/10 = stick clicks). The game ORs the `bof4.cfg` joystick entries into PS1 pad bits each frame;
  a hook at the end of that loop also sets Start for button 8 and Select for button 7. The default joystick
  table (used for a new `bof4.cfg`) moves the camera from 7/8 to LB/RB, Change Rank (L2) from 6 to RS, and
  Start/Select from the stick clicks to 8/7.
  The same hook remembers the last device used (controller when it sets any bit, keyboard when any key is
  down). A hint is a keycap with the key's name in a small font (`0x62A1B0` draws it, `0x62A680` measures it in
  text). In controller mode the name lookup returns a 1- or 2-character placeholder that sizes the keycap, and
  the keycap's letter loop draws the button's label instead: 2 glyphs per button appended to both keycap fonts
  in `INIT.DAT` (`button_icons.patch_labels`), drawn with palette 14, which has the green, red, blue, yellow
  and pink. The label art comes with the chosen icon set, so the exe needs no setting.
- **Button icons:** the circled numbers are font glyphs 0x5E–0x67 (text chars 0x7E–0x87, the PS1's button
  symbol codes). `button_icons.py` redraws them inside the game's own ring at 8× and reduces them to the
  font's 8 ink levels, so they take the text colours (red when selected) like letters.
- **Music:** the PC version streams MP3s. A stub in the exe loads `bof4_reverb.dll`, which wraps the MP3
  decoder:
  - **Loops:** it jumps from each recording's loop end to its loop start, sample-exact, skipping the final
    frame that the game's decoder garbles.
  - **Reverb:** it runs the PS1 reverb ("Studio Medium", depth 64/127, as the PS1 sound driver sets it) on
    the decoded music.

- **60 fps** (`reverb\fps60.c`): the game draws each 30 fps frame as one batch of pre-transformed vertices
  and presents it one vblank later. Two calls in the exe (the frame's screen pass and the present) go
  through `bof4_reverb.dll`, which draws a blend of the previous and the current frame in that skipped vblank:
  - 3D geometry carries its view depth, so it is unprojected and moved by half the camera change (the camera
    matrix the game keeps at `0xBAD7F4`); things that move on their own are found in the previous frame by
    texture and UVs and blended on screen.
  - Sprites and 2D layers are matched to the previous frame (texture, UVs, colour, nearest position, only
    unambiguous matches); a character's parts move as one; UI that jumps (menu lists, text) is not blended.
  - Corners shared by neighbouring polygons move together (no cracks). Cuts, loading and screens at other
    frame rates show the frame twice, as before.
  - Frame pacing: the game's limiter alternated 32 and 34 ms frames for whole seconds; with the option on,
    frames are paced to exactly 33.3 ms and the in-between frame goes out halfway.
- **No PS1 wobble:** the map renderer keeps each polygon's screen corners both rounded (what the PS1 drew) and
  exact (what the PC port draws). On maps with a per-vertex lighting effect it rebuilt the exact corners from
  the rounded ones after running the effect, which snaps them by up to 4 screen pixels. The patch keeps the
  exact corners and adds only what the effect itself changed.
- **Sprite depth scaling** (`reverb\sprites.c`): every character is drawn around one anchor, its projected feet,
  and its sprite packets already carry a scale factor (always 1). The DLL records each anchor's view depth when
  the game projects it and, at draw time, scales the character by the player's depth over its own (only when
  that shrinks it, unless `grow=1`). The camera follows the player, so the player keeps its size.
- **Widescreen** (`reverb\widescreen.c`): the game scales the PS1's 320×240 picture to the chosen resolution, so at
  16:9 everything is a third too wide. Right before each frame is drawn, the DLL squeezes it back to 4:3 proportions
  around the centre; the 3D scene then fills the sides. For that the exe draws what the PS1 left out:
  - the polygon culls (`x + 16 < 352`, `y + 16 < 272`) get a 112-pixel margin left and top (about 20:9) and a
    much wider one right and bottom, so a polygon reaching past both sides of the screen (a tall pillar) still
    passes by its far corners;
  - maps draw only the blocks within a radius of the camera focus (14 × 8 blocks by default, a diamond on some maps);
    the radius is doubled, both for the list of block rows and for the per-block test;
  - map polygons beyond the depth-sorting table's last slot go into that slot instead of being dropped.
  - the frame's buffers (8192 vertices, 2048 draw commands, two pools of 2048 map polygons, all unchecked with the
    game's variables right after them) are too small for a busy town seen this wide (Synesta needs about 2250
    polygons) and overflowing them closed the game. The exe reads their addresses from variables, and the DLL
    points those at bigger buffers; the polygon pools must lie below 16 MB (PS1 packets link by 24-bit
    address), so they reuse the game's freed vertex buffer and both old pools as one.

  Full-screen fades, the battle swirl (a capture of the screen), dark masks (the world map's vignette, the
  targeting scope) and pictures made for the 4:3 frame (the Sand Flier race's backdrop, summon and spell skies,
  cloud layers) are stretched to cover the whole screen; sky panoramas and spell effects wider than the screen (the
  plains, Gigaflare, Blizzard), the plains' far ground and haze (drawn in 2D below the sky) and drifting effects
  (Blizzard's snow) fill the sides. A big backdrop in pieces that pans or zooms (the Breath attacks' skies, Kaiser
  Breath's Earth) is squeezed only as far as it still covers the screen and slid to close any gap, so it never
  jumps between the two. Menus and text are cut at the 4:3 edge, as on a 4:3 screen. Some HUD panels move to the
  screen edges with their text and icons: all of them in the fishing minigame (recognised by its data, which the
  game loads at a fixed address), the compass in towns and fields, the world map's bottom panels and battle's
  Enemy(s) box (by the game's program number); boxes across the centre stay. Full-screen menu backgrounds (Camp,
  Settings, the battle results) are stretched behind the centred windows. It shares the 60 fps option's hook and
  works with or without it. Movies are drawn by their own routine, outside the frame, at the video's pixel size;
  the DLL fits them to the screen at the video's own aspect instead (a 4:3 movie gets black bars, a 16:9
  replacement video of any resolution fills the screen).

## Credits

- Restored scene scripts and text: **navarchos** – [Breath of Fire IV Uncensored (PS1)](https://www.romhacking.net/hacks/7192/)
- Identify (level-up entry, element icon idea and the Wind/Holy/Mind icon shapes): **navarchos** – Breath of Fire IV: Working Identify Ability Hack (PS1)
- Better Descriptions: **Naro** – [Better Descriptions](https://www.romhacking.net/hacks/9575/)
- PS1 reverb algorithm: [psx-spx](https://psx-spx.consoledev.net/soundprocessingunitspu/) (nocash)
- Installer art (SteamGridDB): background by **Ar,,**, logo by **Llisandur**, icon by **Rebochan**
- Dengeki Store graphics: the Japanese GOG release of Breath of Fire IV

*Breath of Fire IV* is © Capcom. This is an unofficial fan project, not affiliated with Capcom or GOG.

## AI use

## AI use

This mod was developed with substantial assistance from an AI coding assistant (Claude Code / Claude).

**What the AI did**
- Wrote and iterated large amounts of the supporting tooling: Python scripts for scene derivation (`derive_scenes.py`), icon generation (`identify_icons.py`, `button_icons.py`), DAT handling (`lzhuf.py`), the build system (`build_mod.py`), loop analysis, and the Steam loader helper scripts.
- Generated and refined the C code for the runtime DLL (`bof4_reverb.c`, `loops.c`, `fps60.c`, `sprites.c`, `widescreen.c`) and the installer (`installer.cs`), including the code caves, hooks, buffer management, and the various experimental features (60 fps interpolation, widescreen culling/margins, sprite depth scaling, controller remapping and button icons).
- Helped reverse-engineer structures, locate relevant code paths in the GOG executable, and propose approaches for restoring cut scenes, fixing the Identify layout, re-adding Dengeki Store data, and implementing the PS1-style reverb and loop points.
- Produced documentation drafts, commit messages, and explanatory comments that were then edited.

**What I did**
- Directed the overall design, priorities, and feature set (which cut content to restore, which PC-port problems to fix, which experimental options to expose, default on/off states, etc.).
- Supplied the game files, PS1 disc images, existing hacks (navarchos’ Uncensored and Identify), and the Better Descriptions package as ground truth.
- Tested every change in-game across multiple areas, battles, menus, and the fishing minigame; reported bugs, edge cases, visual/audio problems, and performance issues back to the AI for further iteration.
- Reviewed, edited, simplified, or rewrote AI-generated code and text for correctness, style, safety (SHA-256 checks, backup handling, option independence), and maintainability.
- Made the final decisions on what shipped, what stayed experimental, the installer UX, the tuning options in `BOF4_reverb.ini`, and the wording of this README.

In short: the AI accelerated the coding and exploration work dramatically; the design, verification, and final product remain human-directed.

## License

See [LICENSE](LICENSE). In short: personal use, modification and GitHub forks are fine. **Re-uploading or
redistributing it anywhere else, including Nexus Mods, is not allowed without permission.** Link to this
repository instead. Third-party material stays with its owners.
