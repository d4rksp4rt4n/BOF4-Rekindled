# Breath of Fire IV – English Uncut & fixes (GOG PC)

A patcher for the English GOG release of *Breath of Fire IV* that restores content cut from the Western
release and fixes several problems of the PC port. It comes as a small Windows installer with a GUI. Every
option can be switched on or off, and "Restore original files" undoes everything. 

| Option | What it does |
|---|---|
| Restore cut scenes | Ryu/Ursula at the checkpoint, Ursula on Zig's ship, Emperor Soniel's attack on Fou-Lu and the Saldine Island bath scene, with English text |
| Unlock the Dengeki Store | The Japan-only store, with its original English (US PlayStation) text and the graphics the English port dropped |
| Stutter fix | The per-frame screen clear runs on the GPU instead of forcing a GPU readback in GOG's ddraw wrapper (random hitches) |
| PlayStation reverb | The PC music is dry MP3 recordings; this adds the PS1 sound chip's reverb back at runtime, using the PS1 game's own setting |
| Correct music loops | Songs loop from their real loop point instead of replaying the intro, and without the click/gap the PC player makes at every restart |
| Scias learns Identify | Restores the cut Identify ability at level 3, with element icons for the weakness/resistance list as in the PS1 hack |
| Better Descriptions | Naro's descriptions of hidden item, equipment and master effects |
| 60 fps (experimental) | The game runs at 30 fps; this draws an in-between frame for each one (camera and characters move smoothly). Off by default; Scroll Lock switches it off and on while playing |
| No PS1 wobble | In rooms with lighting effects (North Chamba and a few others) the PC port snaps the 3D to whole PS1 pixels, so walls and floors swim like on a PlayStation; this keeps the exact positions it already has |
| Sprite depth scaling | Characters are fixed-size sprites while the 3D around them shrinks with distance, so a villager up the street looks like it grows next to the floor under it. This shrinks characters further away than the player like the 3D around them (the player and everyone closer keep their size). Off by default; Insert switches between shrink only, full perspective and off while playing |
| Widescreen (experimental) | At a 16:9 resolution the game stretches its 4:3 picture to the full width. This keeps the proportions right and shows more of the 3D scene at the sides instead; menus, text and the HUD stay in the centred 4:3 area, and movies play in 4:3 with black bars. Choose the resolution in the game: Camp → Settings → Screen adjust. Off by default |

## For players

1. You need the English GOG version of Breath of Fire IV. The installer checks every file and refuses
   to change anything that isn't the original English GOG data.
2. Download `BOF4_Uncut_EN.exe` from this repository's **Releases** page, put it next to `BOF4.exe`
   and run it. Tick the options you want and press **Apply**.
3. Originals are kept in `BOF4_Uncut_EN_backup`. Run the installer again any time to change options or
   to restore the original files. On start it checks GitHub for a newer release and shows a link if
   there is one (nothing is downloaded or sent).

Notes:
- **Saves past Saldine:** a save made in the unmodded game after the party reached the Saldine Island
  creek will freeze when it enters the creek with "Restore cut scenes" on, because the bath scene still
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

## Status – testing wanted

This is a young project tested on one machine. Reports are very welcome. Open an issue with what you
did, where you were in the game, and, if possible, a save file.

| Area | Status |
|---|---|
| Restored scenes | All four tested in game: the checkpoint, Ursula on Zig's ship, Soniel vs. Fou-Lu and the Saldine bath scene |
| Dengeki Store | Tested in game: shop and lottery work, with English text and the clerk's portrait. The signs on the building and in the shop stay Japanese: they are painted into the textures, and the store never had an English release |
| Stutter fix, reverb | Tested over long play sessions |
| Music loops | Many songs checked by ear and sample-exact in game; not every song in every area has been heard. Report any song whose loop sounds off (jump, gap, replayed intro), with the area |
| Scias learns Identify | Tested in game: HP, Exp, treasure, info, and the element icons with their weak/normal/strong colours |
| **60 fps** | **Experimental.** Tested in towns, fields, the world map, battles, menus, dialogue and the fishing minigame. Report anything that flickers, jumps or tears only with the option on (Scroll Lock compares), ideally with a capture (see above) |
| **Widescreen** | **Experimental.** Tested at 1920×1080 on the world map, in fields (camera turned all the way round), battles (battle swirl, targeting, Gigaflare, Blizzard, several summons), the fishing minigame, the Sand Flier race, the plains, menus and the intro movie, also together with 60 fps and sprite depth scaling. Known limits: the HUD and on-screen panels keep their 4:3 positions, so some (the fishing panels) show in the side areas; on wide flat maps (the plains) the ground can end just short of the horizon at the far sides. Report anything cut off at the sides, popping in near the edges, or stuck in the 4:3 area when it should cover the screen, with a screenshot |
| No PS1 wobble, sprite depth scaling | **New.** Tested in North Chamba and Synesta. Report rooms that still swim, or characters whose size looks wrong or jumps |
| **Steam version** | **Experimental, not yet tested on a real Steam install.** Its `BOF4.exe` is the GOG exe inside an Enigma wrapper (encrypted on disk); every other file equals GOG's. The installer leaves the exe untouched and adds `version.dll`, which applies the same exe changes in memory once the game has unpacked, and logs the result to `BOF4_Uncut_EN.log`. Reports from Steam owners (with that log) are very welcome |

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
`build_mod.py` writes `mod\BOF4_Uncut_EN.exe`. The installer embeds only the differences from the original
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
| `derive_scenes.py` | derives the scene redirects from the US PS1 disc and the Uncensored hack |
| `installer.cs` | the GUI installer (WinForms) |
| `steam\` | Steam loader: `version.dll` proxy (`bof4_loader.c`) that patches the unpacked exe in memory; `mem_list.py` makes its patch list |
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
  - the polygon culls (`x + 16 < 352`, `y + 16 < 272`) get a 112-pixel margin on every side (about 20:9);
  - maps draw only the blocks within a radius of the camera focus (14 × 8 blocks by default, a diamond on some maps);
    the radius is doubled, both for the list of block rows and for the per-block test;
  - map polygons beyond the depth-sorting table's last slot go into that slot instead of being dropped.

  Full-screen fades, the battle swirl (a capture of the screen), dark masks (the world map's vignette, the
  targeting scope) and pictures made for the 4:3 frame (the Sand Flier race's backdrop, summon and spell skies,
  cloud layers) are stretched to cover the whole screen; sky panoramas and spell effects wider than the screen (the
  plains, Gigaflare, Blizzard) and drifting effects (Blizzard's snow) fill the sides; menus and text are cut at the 4:3 edge, as on a 4:3 screen. It
  shares the 60 fps option's hook and works with or without it. Movies are drawn by their own routine, outside the
  frame, at the video's pixel size; the DLL fits them to the screen at the video's own aspect instead (a 4:3 movie
  gets black bars, a 16:9 replacement video of any resolution fills the screen).

## Credits

- Restored scene scripts and text: **navarchos** – [Breath of Fire IV Uncensored (PS1)](https://www.romhacking.net/hacks/7192/)
- Identify (level-up entry, element icon idea and the Wind/Holy/Mind icon shapes): **navarchos** – Breath of Fire IV: Working Identify Ability Hack (PS1)
- Better Descriptions: **Naro** – [Better Descriptions](https://www.romhacking.net/hacks/9575/)
- PS1 reverb algorithm: [psx-spx](https://psx-spx.consoledev.net/soundprocessingunitspu/) (nocash)
- Installer art (SteamGridDB): background by **Ar,,**, logo by **Llisandur**, icon by **Rebochan**
- Dengeki Store graphics: the Japanese GOG release of Breath of Fire IV

*Breath of Fire IV* is © Capcom. This is an unofficial fan project, not affiliated with Capcom or GOG.

## AI use

This mod was made with help from an AI coding assistant (Claude Code).

## License

See [LICENSE](LICENSE). In short: personal use, modification and GitHub forks are fine. **Re-uploading or
redistributing it anywhere else, including Nexus Mods, is not allowed without permission.** Link to this
repository instead. Third-party material stays with its owners.
