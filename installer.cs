// BOF4 Rekindled installer (Breath of Fire IV, GOG English / Steam). Built by build_mod.py (csc, .NET Framework 4).
// The embedded manifest lists, per file and per combination of options, how to build the patched file from
// the original (copy ranges + literal bytes) and the SHA-256 of both. Originals go to BOF4_Rekindled_backup.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("BOF4 Rekindled installer")]
[assembly: System.Reflection.AssemblyProduct("BOF4 Rekindled")]
[assembly: System.Reflection.AssemblyVersion(Installer.Version + ".0.0")]
[assembly: System.Reflection.AssemblyFileVersion(Installer.Version + ".0.0")]

class Variant { public string Path, Key, Src, Dst; public List<string> Ops = new List<string>(); }

// A CheckBox drawn as a switch (rounded track, knob right and accent red when on). Keyboard, focus and
// accessibility stay the CheckBox's own.
class Toggle : CheckBox
{
    public Toggle()
    {
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer, true);
        Height = 26; Cursor = Cursors.Hand;
    }
    bool hot;
    protected override void OnMouseEnter(EventArgs e) { hot = true; Invalidate(); base.OnMouseEnter(e); }
    protected override void OnMouseLeave(EventArgs e) { hot = false; Invalidate(); base.OnMouseLeave(e); }
    protected override void OnCheckedChanged(EventArgs e) { Invalidate(); base.OnCheckedChanged(e); }
    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.Clear(Parent.BackColor);
        g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
        const int w = 34, h = 18;
        int x = 2, y = (Height - h) / 2;
        using (var track = new System.Drawing.Drawing2D.GraphicsPath())
        {
            track.AddArc(x, y, h, h, 90, 180); track.AddArc(x + w - h, y, h, h, 270, 180); track.CloseFigure();
            Color on = Installer.Accent, off = Color.FromArgb(88, 82, 94);
            if (hot) { on = ControlPaint.Light(on, 0.2f); off = ControlPaint.Light(off, 0.2f); }
            using (var b = new SolidBrush(Checked ? on : off)) g.FillPath(b, track);
        }
        int k = h - 6;
        using (var b = new SolidBrush(Installer.Fg)) g.FillEllipse(b, Checked ? x + w - k - 3 : x + 3, y + 3, k, k);
        var text = new Rectangle(x + w + 8, 0, Width - x - w - 8, Height);
        TextRenderer.DrawText(g, Text, Font, text, ForeColor,
                              TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix);
        if (Focused && ShowFocusCues)
        {
            var s = TextRenderer.MeasureText(g, Text, Font, text.Size, TextFormatFlags.NoPrefix);
            ControlPaint.DrawFocusRectangle(g, new Rectangle(text.X - 2, (Height - s.Height) / 2 - 1, s.Width + 4, s.Height + 2));
        }
    }
}

class Installer : Form
{
    readonly List<string[]> options = new List<string[]>();
    readonly List<Variant> variants = new List<Variant>();
    readonly TextBox folder = new TextBox(), log = new TextBox();
    // manifest option (group|id|label|description|on/off[|choice "id=label"...]) and its toggle or dropdown
    readonly List<Tuple<string[], Control>> inputs = new List<Tuple<string[], Control>>();
    const string Hint = "Point at an option to see what it does.";
    int GroupHeight(string group)
    {
        return 32 + options.Where(o => o[0] == group).Sum(o => o.Length > 5 ? 32 : 28) + 4;
    }
    void Defaults()
    {
        foreach (var t in inputs)
            if (t.Item2 is ComboBox) ((ComboBox)t.Item2).SelectedIndex = 0;
            else ((Toggle)t.Item2).Checked = t.Item1[4] == "on";
    }
    static string[] Ids(string[] o)                       // the variant-key ids an option stands for
    {
        return o.Length > 5 ? o.Skip(5).Select(c => c.Split('=')[0]).ToArray() : new[] { o[1] };
    }
    List<string> Chosen()                                 // in manifest order, as the variant keys are
    {
        var r = new List<string>();
        foreach (var t in inputs)
        {
            var cb = t.Item2 as ComboBox;
            if (cb != null) { string id = Ids(t.Item1)[cb.SelectedIndex]; if (id.Length > 0) r.Add(id); }
            else if (((Toggle)t.Item2).Checked) r.Add(t.Item1[1]);
        }
        return r;
    }
    public const string Version = "1.3";           // release tag on GitHub: "1.3" or "1.3.0"
    const string Repo = "d4rksp4rt4n/bof4-rekindled";
    readonly LinkLabel update = new LinkLabel { Visible = false, AutoSize = true };
    const string BackupDir = "BOF4_Rekindled_backup";
    // BOF4.exe stays untouched (GOG and Steam): dsound.dll applies the exe options in memory, from
    // BOF4_Rekindled.mem, the ones listed in BOF4_Rekindled.ini. Steam's BOF4.exe is the GOG exe inside an Enigma
    // wrapper (encrypted on disk); its other files equal GOG's. Earlier versions patched the GOG exe itself: Apply
    // and Restore put the backed-up original back. version.dll was the loader of an earlier test build; they remove it.
    const string SteamExe = "86f401f951e05458c36de3a1fb90af833a31ed6c947c378600f1a3869cdbef6e";
    const string Ini = "BOF4_Rekindled.ini";
    string gogExe = "";                                   // manifest "E" line: the untouched GOG exe, the exe options
    readonly HashSet<string> exeOpts = new HashSet<string>();
    static bool IsSteam(string game) { return Sha(File.ReadAllBytes(Path.Combine(game, "BOF4.exe"))) == SteamExe; }
    IEnumerable<IGrouping<string, Variant>> Files() { return variants.GroupBy(v => v.Path); }
    static string IniText(IEnumerable<string> opts) { return "[loader]\r\noptions=" + string.Join(",", opts) + "\r\n"; }
    static List<string> IniOptions(string game)
    {
        string p = Path.Combine(game, Ini);
        if (!File.Exists(p)) return new List<string>();
        var l = File.ReadAllLines(p).FirstOrDefault(s => s.Trim().StartsWith("options="));
        return l == null ? new List<string>() : l.Trim().Substring(8).Split(',').Where(s => s.Length > 0).ToList();
    }
    // 0: untouched GOG or Steam exe; 1: GOG exe patched by an earlier version (original in the backup); -1: unknown
    int ExeState(string game, bool steam)
    {
        if (steam) return 0;
        if (Sha(File.ReadAllBytes(Path.Combine(game, "BOF4.exe"))) == gogExe) return 0;
        string bak = Path.Combine(game, BackupDir, "BOF4.exe");
        return File.Exists(bak) && Sha(File.ReadAllBytes(bak)) == gogExe ? 1 : -1;
    }
    static readonly string Empty = Sha(new byte[0]);

    [STAThread]
    static void Main() { Application.EnableVisualStyles(); Application.Run(new Installer()); }

    internal static readonly Color Bg = Color.FromArgb(24, 22, 28), Panel = Color.FromArgb(38, 35, 44),
        Fg = Color.FromArgb(236, 230, 218), Dim = Color.FromArgb(160, 152, 165), Accent = Color.FromArgb(178, 40, 24);

    static Button MakeButton(string text, Color back)
    {
        var b = new Button { Text = text, FlatStyle = FlatStyle.Flat, BackColor = back, ForeColor = Fg, Cursor = Cursors.Hand };
        b.FlatAppearance.BorderColor = Color.FromArgb(90, 80, 95);
        return b;
    }

    Installer()
    {
        LoadManifest();
        Text = "BOF4 Rekindled " + Version; Font = new Font("Segoe UI", 9f);
        BackColor = Bg; ForeColor = Fg;
        FormBorderStyle = FormBorderStyle.FixedSingle; MaximizeBox = false; StartPosition = FormStartPosition.CenterScreen;
        try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }

        var banner = new PictureBox { Location = new Point(0, 0), Size = new Size(640, 180) };
        using (var s = typeof(Installer).Assembly.GetManifestResourceStream("banner.png"))
            banner.Image = Image.FromStream(s);
        int y = 184;
        var lf = new Label { Text = "Game folder (where BOF4.exe is):", Location = new Point(16, y), AutoSize = true, ForeColor = Dim };
        folder.SetBounds(16, y + 20, 510, 24); folder.BackColor = Panel; folder.ForeColor = Fg; folder.BorderStyle = BorderStyle.FixedSingle;
        var browse = MakeButton("Browse...", Panel); browse.SetBounds(534, y + 19, 90, 25);
        browse.Click += delegate {
            using (var d = new FolderBrowserDialog { SelectedPath = folder.Text })
                if (d.ShowDialog(this) == DialogResult.OK) { folder.Text = d.SelectedPath; Detect(); }
        };
        folder.Leave += delegate { Detect(); };
        Controls.AddRange(new Control[] { banner, lf, folder, browse });

        y += 56;
        // option groups in two columns: the first two groups on the left, the rest on the right
        var groups = options.Select(o => o[0]).Distinct().ToList();
        var desc = new Label { Text = Hint, ForeColor = Dim, UseMnemonic = false };
        int bottom = y;
        for (int gi = 0; gi < groups.Count; gi++)
        {
            int col = gi < 2 ? 0 : 1, gy = y;
            foreach (var prev in groups.Take(gi).Where((g, i) => (i < 2 ? 0 : 1) == col)) gy += GroupHeight(prev) + 8;
            var box = new Panel { Location = new Point(16 + col * 308, gy), Size = new Size(300, GroupHeight(groups[gi])), BackColor = Panel };
            box.Controls.Add(new Label { Text = groups[gi], Location = new Point(10, 7), AutoSize = true, UseMnemonic = false,
                                         ForeColor = Color.FromArgb(232, 150, 90), Font = new Font("Segoe UI", 9.5f, FontStyle.Bold) });
            int ry = 32;
            foreach (var o in options.Where(o => o[0] == groups[gi]))
            {
                Control c;
                if (o.Length > 5)                                 // dropdown: label + choices
                {
                    box.Controls.Add(new Label { Text = o[2], Location = new Point(10, ry + 4), AutoSize = true, UseMnemonic = false });
                    var cb = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, FlatStyle = FlatStyle.Flat, BackColor = Bg, ForeColor = Fg,
                                            Location = new Point(110, ry), Width = 178, AccessibleName = o[2].TrimEnd(':') };
                    cb.Items.AddRange(o.Skip(5).Select(ch => ch.Substring(ch.IndexOf('=') + 1)).ToArray());
                    c = cb; ry += 32;
                }
                else { c = new Toggle { Text = o[2], Location = new Point(8, ry), Width = 284 }; ry += 28; }
                c.AccessibleDescription = o[3];
                string text = o[3];
                c.MouseEnter += delegate { desc.Text = text; };
                c.Enter += delegate { desc.Text = text; };
                box.Controls.Add(c); inputs.Add(Tuple.Create(o, c));
            }
            Controls.Add(box); bottom = Math.Max(bottom, box.Bottom);
        }
        Defaults();
        y = bottom + 6;
        desc.SetBounds(16, y, 608, 68); Controls.Add(desc);   // the hovered or focused option's explanation
        y += 68;
        var apply = MakeButton("Apply", Accent); apply.SetBounds(16, y + 6, 130, 32);
        apply.Font = new Font("Segoe UI", 9.5f, FontStyle.Bold);
        var restore = MakeButton("Restore original files", Panel); restore.SetBounds(156, y + 6, 180, 32);
        var about = MakeButton("About / credits", Panel); about.SetBounds(494, y + 6, 130, 32);
        about.Click += delegate { ShowAbout(); };
        Controls.Add(about);
        update.Location = new Point(346, y + 14); update.LinkColor = Color.FromArgb(232, 150, 90);
        update.LinkClicked += delegate { try { System.Diagnostics.Process.Start("https://github.com/" + Repo + "/releases/latest"); } catch { } };
        Controls.Add(update);
        Load += delegate { CheckForUpdate(); };
        apply.Click += delegate { Run(Chosen()); };
        restore.Click += delegate { Run(new List<string>()); };
        log.SetBounds(16, y + 46, 608, 90);
        log.Multiline = true; log.ReadOnly = true; log.ScrollBars = ScrollBars.Vertical;
        log.BackColor = Panel; log.ForeColor = Fg; log.BorderStyle = BorderStyle.FixedSingle;
        Controls.AddRange(new Control[] { apply, restore, log });
        ClientSize = new Size(640, y + 46 + 90 + 12);     // 680 (window 715): fits a 768-pixel-high screen

        string here = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        folder.Text = File.Exists(Path.Combine(here, "BOF4.exe")) ? here : FindGog() ?? here;
        Detect();
    }

    static readonly string[][] Credits = {
        new[] { "Project page, updates, issues", "github.com/d4rksp4rt4n/bof4-rekindled", "https://github.com/d4rksp4rt4n/bof4-rekindled" },
        new[] { "Restored scene scripts, text", "navarchos - Breath of Fire IV Uncensored (PS1)", "https://www.romhacking.net/hacks/7192/" },
        new[] { "Better Descriptions", "Naro", "https://www.romhacking.net/hacks/9575/" },
        new[] { "Dengeki Store graphics", "Japanese GOG release of Breath of Fire IV (Capcom)", null },
        new[] { "PlayStation reverb algorithm", "psx-spx (nocash PSX specifications)", "https://psx-spx.consoledev.net/soundprocessingunitspu/" },
        new[] { "Background art", "Ar,, (SteamGridDB)", "https://www.steamgriddb.com/hero/145909" },
        new[] { "Logo", "Llisandur (SteamGridDB)", "https://www.steamgriddb.com/logo/130843" },
        new[] { "Icon", "Rebochan (SteamGridDB)", "https://www.steamgriddb.com/icon/114222" },
    };

    void ShowAbout()
    {
        var f = new Form { Text = "About - BOF4 Rekindled", Font = Font, BackColor = Bg, ForeColor = Fg,
                           FormBorderStyle = FormBorderStyle.FixedDialog, MaximizeBox = false, MinimizeBox = false,
                           StartPosition = FormStartPosition.CenterParent, ShowInTaskbar = false, Icon = Icon };
        int y = 14;
        var head = new Label { Text = "BOF4 Rekindled " + Version, UseMnemonic = false, AutoSize = true, Location = new Point(16, y),
                               Font = new Font("Segoe UI", 10.5f, FontStyle.Bold) };
        var note = new Label { Text = "Breath of Fire IV is (c) Capcom. This is an unofficial fan patch; it changes only your own game files.",
                               Location = new Point(16, y + 24), Size = new Size(540, 34), ForeColor = Dim };
        f.Controls.Add(head); f.Controls.Add(note); y += 66;
        foreach (var c in Credits)
        {
            f.Controls.Add(new Label { Text = c[0], Location = new Point(16, y), Size = new Size(210, 18), ForeColor = Dim });
            if (c[2] == null) f.Controls.Add(new Label { Text = c[1], Location = new Point(230, y), Size = new Size(330, 18) });
            else
            {
                var link = new LinkLabel { Text = c[1], Location = new Point(230, y), Size = new Size(330, 18), Tag = c[2],
                                           LinkColor = Color.FromArgb(232, 150, 90), ActiveLinkColor = Fg, VisitedLinkColor = Color.FromArgb(200, 130, 80) };
                link.LinkClicked += delegate (object s, LinkLabelLinkClickedEventArgs e) {
                    try { System.Diagnostics.Process.Start((string)((Control)s).Tag); } catch { }
                };
                f.Controls.Add(link);
            }
            y += 24;
        }
        var close = MakeButton("Close", Panel); close.SetBounds(460, y + 10, 100, 30); close.Click += delegate { f.Close(); };
        f.Controls.Add(close); f.AcceptButton = close; f.CancelButton = close;
        f.ClientSize = new Size(576, y + 54);
        f.ShowDialog(this);
    }

    static System.Version Ver(string s)                   // "v1.1" / "1.1" / "1.1.0" -> 1.1.0
    {
        var p = s.Trim().TrimStart('v', 'V').Split('.').ToList();
        while (p.Count < 3) p.Add("0");
        return new System.Version(string.Join(".", p.Take(3)));
    }

    // Asks GitHub for the latest release tag in the background; silent on any failure (offline etc.).
    void CheckForUpdate()
    {
        try
        {
            ServicePointManager.SecurityProtocol |= (SecurityProtocolType)3072;   // TLS 1.2 (GitHub requires it)
            var wc = new WebClient();
            wc.Headers[HttpRequestHeader.UserAgent] = "BOF4-Rekindled-installer";
            wc.DownloadStringCompleted += (s, e) => {
                try
                {
                    var tag = Regex.Match(e.Result, "\"tag_name\"\\s*:\\s*\"([^\"]+)\"").Groups[1].Value;
                    if (Ver(tag) <= Ver(Version)) return;
                    update.Text = "Update available: " + tag;
                    update.Visible = true;
                    Log("A newer version (" + tag + ") is available on the GitHub releases page.");
                }
                catch { }
                finally { wc.Dispose(); }
            };
            wc.DownloadStringAsync(new Uri("https://api.github.com/repos/" + Repo + "/releases/latest"));
        }
        catch { }
    }

    static string FindGog()
    {
        foreach (var d in new[] { @"C:\GOG Games\Breath of Fire IV", @"C:\Program Files (x86)\GOG Galaxy\Games\Breath of Fire IV" })
            if (File.Exists(Path.Combine(d, "BOF4.exe"))) return d;
        return null;
    }

    void LoadManifest()
    {
        using (var s = typeof(Installer).Assembly.GetManifestResourceStream("manifest.gz"))
        using (var r = new StreamReader(new System.IO.Compression.GZipStream(s, System.IO.Compression.CompressionMode.Decompress)))
        {
            Variant cur = null; string l;
            while ((l = r.ReadLine()) != null)
            {
                if (l.StartsWith("O ")) options.Add(l.Substring(2).Split('|'));
                else if (l.StartsWith("E "))
                {
                    var p = l.Split(' ');
                    gogExe = p[1]; exeOpts.UnionWith(p.Skip(2));
                }
                else if (l.StartsWith("F "))
                {
                    var p = l.Split(' ');
                    cur = new Variant { Path = p[1], Key = p[2], Src = p[3], Dst = p[4] }; variants.Add(cur);
                }
                else if (l.Length > 0) cur.Ops.Add(l);
            }
        }
    }

    static string Sha(byte[] b)
    {
        using (var h = SHA256.Create()) return BitConverter.ToString(h.ComputeHash(b)).Replace("-", "").ToLowerInvariant();
    }

    void Log(string s) { log.AppendText(s + Environment.NewLine); }

    // show the options that are currently installed (the defaults on an untouched game). Options whose files
    // are from another version of the mod can't be read back; they keep their defaults.
    // Loader DLLs of this mod name their patch list inside (current or pre-rename name).
    static bool OurLoader(byte[] b)
    {
        string s = System.Text.Encoding.ASCII.GetString(b);
        return s.Contains("BOF4_Rekindled.mem") || s.Contains("BOF4_Uncut_EN.mem");
    }
    // Installs made before the rename keep their originals in BOF4_Uncut_EN_backup.
    void MoveOldBackup(string game)
    {
        string old = Path.Combine(game, "BOF4_Uncut_EN_backup"), now = Path.Combine(game, BackupDir);
        if (!Directory.Exists(old) || Directory.Exists(now)) return;
        try { Directory.Move(old, now); Log("Renamed the backup folder BOF4_Uncut_EN_backup to " + BackupDir + "."); }
        catch (Exception e) { Log("Could not rename BOF4_Uncut_EN_backup (" + e.Message + "); close programs using it and try again."); }
    }

    void Detect()
    {
        string game = folder.Text;
        if (!File.Exists(Path.Combine(game, "BOF4.exe"))) return;
        MoveOldBackup(game);
        var installed = new HashSet<string>(); var known = new HashSet<string>();
        bool any = false, older = false, steam = IsSteam(game);
        foreach (var g in Files())
        {
            string p = Path.Combine(game, g.Key);
            string h;
            try { h = File.Exists(p) ? Sha(File.ReadAllBytes(p)) : Empty; }
            catch (IOException) { continue; }                 // locked (e.g. an antivirus scanning it): Apply reports it
            catch (UnauthorizedAccessException) { continue; }
            var mine = g.SelectMany(v => v.Key.Split(',')).Distinct().ToList();
            var hits = g.Where(v => v.Dst == h).Select(v => v.Key.Split(',')).ToList();
            if (hits.Count > 0)
            {                                                 // same file for several keys: only what they all agree on
                any = true; installed.UnionWith(hits.Aggregate((a, b) => a.Intersect(b).ToArray()));
                known.UnionWith(mine.Where(id => hits.All(k => k.Contains(id)) || hits.All(k => !k.Contains(id))));
            }
            else if (h == g.First().Src) known.UnionWith(mine);  // original file: its options are off
            else if (File.Exists(p) && (g.First().Src == Empty || File.Exists(Path.Combine(game, BackupDir, g.Key))))
                older = true;                                 // ours, from another version (else: Run refuses it)
        }
        if (ExeState(game, steam) == 1) older = true;         // exe patched by an earlier version: its options unknown
        else
        {
            known.UnionWith(exeOpts);                         // exe options: the loader's list (none without it)
            if (installed.Contains("loader")) installed.UnionWith(IniOptions(game).Where(exeOpts.Contains));
        }
        if (any || older)
        {
            Defaults();
            foreach (var t in inputs)
            {
                var ids = Ids(t.Item1); var cb = t.Item2 as ComboBox;
                if (!ids.Any(known.Contains)) continue;
                if (cb != null) cb.SelectedIndex = Math.Max(0, Array.FindIndex(ids, installed.Contains));
                else ((Toggle)t.Item2).Checked = installed.Contains(ids[0]);
            }
        }
        log.Clear();
        if (steam) Log("Steam version found (experimental).");
        if (older) Log("Found an install of another version of this mod. Options that can't be read from its files show " +
                       "the defaults; Apply rebuilds those files from the backed-up originals.");
        else Log(any ? "Found an earlier install of this mod; the options switched on are the ones installed."
                     : "Ready. Choose the options and press Apply.");
        if (File.Exists(Path.Combine(game, "d3d9.dll")))
            Log("Note: d3d9.dll found. If it is the German patch's, remove it (and _d3d9_hook_config.txt): " +
                "it is not needed and its German text layout fixes garble the English text.");
    }

    void Run(List<string> chosen)
    {
        log.Clear();
        string game = folder.Text;
        try
        {
            if (!File.Exists(Path.Combine(game, "BOF4.exe"))) throw new Exception("BOF4.exe not found in that folder.");
            MoveOldBackup(game);
            var plan = new List<Tuple<string, byte[], Variant>>();   // path, original bytes, target (null = original)
            bool steam = IsSteam(game);
            int exeState = ExeState(game, steam);
            if (exeState < 0)
                throw new Exception("BOF4.exe is not the GOG or Steam build this mod supports (changed by something else?). " +
                                    "Reinstall the game files (GOG Galaxy: Verify / Repair), then run this again." +
                                    Environment.NewLine + "Nothing was changed.");
            var exeChosen = chosen.Where(exeOpts.Contains).ToList();
            if (exeChosen.Count > 0) chosen.Add("loader");
            string iniPath = Path.Combine(game, Ini), iniWant = exeChosen.Count > 0 ? IniText(exeChosen) : null;
            bool iniChange = iniWant != (File.Exists(iniPath) ? File.ReadAllText(iniPath) : null);
            foreach (var g in Files())
            {
                string p = Path.Combine(game, g.Key), bak = Path.Combine(game, BackupDir, g.Key);
                string orig = g.First().Src;
                var mine = new HashSet<string>(g.SelectMany(v => v.Key.Split(',')));
                string key = string.Join(",", chosen.Where(mine.Contains));     // same order as the manifest
                var target = key.Length == 0 ? null : g.First(v => v.Key == key);
                bool added = orig == Empty;                       // a file the mod adds (not in the game)
                if (!File.Exists(p) && !added) throw new Exception("Missing " + g.Key);
                byte[] cur = File.Exists(p) ? File.ReadAllBytes(p) : new byte[0]; string h = Sha(cur);
                byte[] src;
                if (h == orig) src = cur;
                else if (added && g.Key == "dsound.dll" && !g.Any(v => v.Dst == h)
                         && !OurLoader(cur))                      // an older build of it
                    throw new Exception(g.Key + " is already there and isn't this mod's (another mod's loader?). " +
                                        "Move it away first." + Environment.NewLine + "Nothing was changed.");
                else if (added) src = new byte[0];                // only this mod adds it (maybe an older build of it)
                else if (File.Exists(bak) && Sha(File.ReadAllBytes(bak)) == orig)
                {                                                 // patched before, maybe by an older version
                    src = File.ReadAllBytes(bak);
                    if (!g.Any(v => v.Dst == h)) Log(g.Key + ": not from this version; rebuilding from the backed-up original.");
                }
                else throw new Exception(g.Key + " was changed by something else and no original copy was found. " +
                                         "Reinstall the game files (GOG Galaxy: Verify / Repair), then run this again." +
                                         Environment.NewLine + "Nothing was changed.");
                if ((target == null ? orig : target.Dst) != h) plan.Add(Tuple.Create(g.Key, src, target));
            }
            string oldLoader = Path.Combine(game, "version.dll");   // earlier test build's loader
            bool dropOld = File.Exists(oldLoader) && OurLoader(File.ReadAllBytes(oldLoader));
            if (dropOld) { File.Delete(oldLoader); Log("removed   version.dll (old loader)"); }
            foreach (var f in new[] { "BOF4_Uncut_EN.mem", "BOF4_Uncut_EN.log" })   // names before the rename
                if (File.Exists(Path.Combine(game, f))) { File.Delete(Path.Combine(game, f)); Log("removed   " + f + " (old name)"); dropOld = true; }
            if (plan.Count == 0 && !dropOld && !iniChange && exeState == 0)
            { Log("Nothing to change - the game already has exactly these options."); return; }
            if (exeState == 1)
            {
                File.Copy(Path.Combine(game, BackupDir, "BOF4.exe"), Path.Combine(game, "BOF4.exe"), true);
                Log("restored  BOF4.exe (an earlier version patched it; now dsound.dll applies the changes in memory)");
            }
            foreach (var t in plan)
            {
                string p = Path.Combine(game, t.Item1), bak = Path.Combine(game, BackupDir, t.Item1);
                byte[] data = t.Item3 == null ? t.Item2 : Build(t.Item2, t.Item3);
                if (t.Item2.Length > 0 && !File.Exists(bak)) { Directory.CreateDirectory(Path.GetDirectoryName(bak)); File.WriteAllBytes(bak, t.Item2); }
                if (data.Length == 0) File.Delete(p);             // restoring "no file"
                else File.WriteAllBytes(p, data);
                Log((t.Item3 == null ? "restored  " : "patched   ") + t.Item1);
            }
            if (iniChange)
            {
                if (iniWant == null) File.Delete(iniPath); else File.WriteAllText(iniPath, iniWant);
                Log(iniWant == null ? "removed   " + Ini : "options   " + Ini + ": " + string.Join(", ", exeChosen));
            }
            Log(""); Log(chosen.Count == 0 ? "Done - original files restored." : "Done. Originals are kept in " + BackupDir + ".");
        }
        catch (UnauthorizedAccessException)
        {
            Log("Windows refused to write to the game folder. Close the game, or run this installer as administrator.");
        }
        catch (Exception e) { Log("Error: " + e.Message); }
    }

    static byte[] Build(byte[] src, Variant v)
    {
        var o = new MemoryStream();
        foreach (var op in v.Ops)
        {
            var p = op.Split(' ');
            if (p[0] == "C") o.Write(src, int.Parse(p[1]), int.Parse(p[2]));
            else { var b = Convert.FromBase64String(p[1]); o.Write(b, 0, b.Length); }
        }
        var r = o.ToArray();
        if (Sha(r) != v.Dst) throw new Exception("internal error building " + v.Path + "; nothing written for it.");
        return r;
    }
}
