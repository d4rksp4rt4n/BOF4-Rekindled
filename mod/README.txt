Breath of Fire IV - English Uncut 1.2 (GOG; Steam experimental)
============================================================

Run BOF4_Uncut_EN.exe, check the game folder, tick the options you want and press Apply.
Options:
  - Restore cut scenes: Ryu/Ursula checkpoint, Ursula on Zig's ship, Emperor Soniel's attack
    on Fou-Lu, and the Saldine Island bath scene (event script + English text)
  - Unlock the Dengeki Store, with its original English (US PlayStation) text
  - Stutter fix: the per-frame screen clear no longer forces a GPU readback in GOG's ddraw wrapper
  - PlayStation reverb: the PC music is plain MP3 recordings without the reverb the PS1 sound
    chip adds. This adds it back while the game plays (bof4_reverb.dll), using the PS1 game's own
    setting ("Studio Medium", depth 64 of 127). To make it stronger or weaker, create
    BOF4_reverb.ini next to BOF4.exe:
        [reverb]
        wet=100        ; percent of the PS1 level (0 = off)
  - Correct music loops: the PC version restarts every song from the beginning, so intros
    replay on each loop. With this, songs loop from their real loop point (taken from the PS1
    version and checked against the PC recordings) for most music. Every looping track also
    loses the click and short dropout the PC version has at each restart (its MP3 player plays
    a garbled last frame and silent padding). Some PC recordings stop before the song's loop
    end; those still restart from the beginning, but without the click.
  - Scias learns Identify: the English release removed Scias' Identify ability (it shows an
    enemy's HP, drops and weaknesses). This puts it back at level 3, as navarchos' PS1 hack
    does, so a new game starts Scias with it. The weakness/resistance names, which the PC
    port draws on top of each other, become element icons as in the PS1 hack (red = weak,
    blue = strong).
  - Better Descriptions: item, equipment and master descriptions show hidden effects
  - 60 fps (EXPERIMENTAL, off by default): the game runs at 30 fps. This draws an in-between
    frame for each one, so the camera and characters move smoothly (bof4_reverb.dll). Menus and
    text that jump stay as they are. Scroll Lock switches it off and on while playing.
    If something flickers, jumps or tears only with it on, please report it. To capture it, add
    to BOF4_reverb.ini:
        [fps60]
        dump=1         ; Pause saves the last second of frames to fps60_dump\ (~6 MB per frame)
    press Pause right after the glitch and attach the fps60_dump folder (zipped) to the report.
  - No PS1 wobble: in rooms with lighting effects (North Chamba and a few others) the PC port
    snapped the 3D to whole PS1 pixels, so walls and floors swam like on a PlayStation. This
    keeps the exact positions.
  - Sprite depth scaling (off by default): characters are fixed-size sprites while the 3D
    around them shrinks with distance, so far-away ones seem to grow. This shrinks characters
    further away than the player like the 3D around them (bof4_reverb.dll). Insert switches
    between shrink only, full perspective and off while playing (shown in the window title).
    To change the starting mode or the strength, add to BOF4_reverb.ini:
        [sprites]
        strength=100   ; % of the full perspective size change
        grow=1         ; characters closer to the camera get bigger too (default 0)
  - Widescreen (EXPERIMENTAL, off by default): at a 16:9 resolution the game stretches its
    4:3 picture. With this, the proportions stay right and the 3D scene fills the sides
    (bof4_reverb.dll); menus and text stay in the centred 4:3 area, HUD panels (compass,
    fishing, world map and battle enemy list) move to the screen edges, movies keep
    their own aspect (a 16:9 replacement video fills the screen). Choose the
    resolution in the game: Camp -> Settings -> Screen adjust (e.g. 1920 x 1080). At a 4:3
    resolution nothing changes. Please report anything cut off at the sides, with a screenshot.
  - Controller Start/Back (NEW, EXPERIMENTAL, off by default): a controller's Start and Back
    (View) buttons work as the PS1's Start and Select (the PC port leaves them on the stick
    clicks, and its Key/Pad Setting screen can't move them). A new key setup (no bof4.cfg yet)
    also puts the camera on LB/RB and Change Rank on the right stick click. With an existing
    setup that has the camera or anything else on Back/Start, those buttons do both: move it in
    Camp -> Setting -> Key/Pad Setting.
  - Xbox / PlayStation button icons (NEW, EXPERIMENTAL, off by default): the game names pad
    buttons with circled numbers 1-10 on the Key/Pad Setting screen and in help text
    ("1: Confirm"). These show the buttons instead: A, B, X, Y, LB, RB, View, Menu, LS, RS, or
    cross, circle, square, triangle, L1, R1, Select, Start, L3, R3. One set at a time.

Needs only the English GOG version. No d3d9.dll or other patch is required.
Steam version: experimental, not yet tested on a real Steam install. Its BOF4.exe is protected
(encrypted), so the installer leaves it untouched and adds version.dll and BOF4_Uncut_EN.mem
instead: version.dll applies the same changes in memory when the game starts and writes the
result to BOF4_Uncut_EN.log. Please report how it went (with that log) on the GitHub page.
Other versions are refused: the installer recognises only the GOG and Steam files.

Still being tested: not every song's loop has been heard yet. (The Dengeki Store's signs stay Japanese:
they are part of its textures, and the store never had an English release.) Please report
problems on the GitHub page (where you were, and a save file if you can).

Existing saves: if a save was made in the unmodded English game after the party reached the
Saldine Island creek, the restored bath scene still counts as "not seen". Entering the creek
then starts it in the wrong state and the game freezes. Use a save from before the creek, or
install without "Restore cut scenes" for that playthrough.

On start, the installer asks GitHub whether a newer release is out and shows a link if so.
You can run it again at any time to change the options. "Restore original files" undoes
everything; originals are kept in BOF4_Uncut_EN_backup.
The installer checks every file before changing anything. It refuses to run on files that
aren't the original English GOG ones, e.g. if the German patch's DAT files are installed.

Files changed: BOF4.exe (Steam: version.dll and BOF4_Uncut_EN.mem added instead), bof4_reverb.dll (added) and DAT\ AREAM027, AREAD157, AREAD145 (scenes), AREAD068, AREAS052
(store), INIT, AB000_00, BTLEND (Identify), AB000_00, CAMP, COMMU03, MASTER, MSHOP, SGAMEN, SHOP
(descriptions), INIT (button icons).

Credits
  - Restored scene scripts and English lines: navarchos' "Breath of Fire IV Uncensored" PS1 hack
  - Identify: navarchos' "Working Identify Ability" PS1 hack (level-up entry, icon idea, the
    Wind/Holy/Mind icon shapes)
  - Better Descriptions: Naro (https://www.romhacking.net/hacks/9575/; PC version included unchanged)
  - Dengeki Store portrait and palette: from the Japanese GOG release, where the English port dropped them
  - PlayStation reverb: the SPU reverb as documented in psx-spx (nocash)
  - Installer art (SteamGridDB): background by "Ar,,", logo by Llisandur, icon by Rebochan
  Breath of Fire IV is (c) Capcom. This is an unofficial fan patch.

License: personal use only; do not re-upload or redistribute this mod anywhere (including Nexus
Mods) without permission. Link to the GitHub repository instead. See LICENSE in the repository.
