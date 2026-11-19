// Breath of Fire IV (GOG, English) - Uncut & fixes installer. Built by build_mod.py (csc, .NET Framework 4).
// The embedded manifest lists, per file and per combination of options, how to build the patched file from
// the original (copy ranges + literal bytes) and the SHA-256 of both. Originals go to BOF4_Uncut_EN_backup.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("Breath of Fire IV - English Uncut installer")]
[assembly: System.Reflection.AssemblyProduct("Breath of Fire IV - English Uncut")]
[assembly: System.Reflection.AssemblyVersion(Installer.Version + ".0.0")]
[assembly: System.Reflection.AssemblyFileVersion(Installer.Version + ".0.0")]

class Variant { public string Path, Key, Src, Dst; public List<string> Ops = new List<string>(); }

class Installer : Form
{
    readonly List<string[]> options = new List<string[]>();
    readonly List<Variant> variants = new List<Variant>();
    readonly TextBox folder = new TextBox(), log = new TextBox();
    readonly List<CheckBox> boxes = new List<CheckBox>();
    public const string Version = "1.2";           // release tag on GitHub: "1.2" or "1.2.0"
    const string Repo = "d4rksp4rt4n/bof4-english-uncut";
    readonly LinkLabel update = new LinkLabel { Visible = false, AutoSize = true };
    const string BackupDir = "BOF4_Uncut_EN_backup";
    // Steam: BOF4.exe is the GOG exe inside an Enigma wrapper (encrypted on disk), so it stays untouched and
    // version.dll applies the exe patch in memory (from BOF4_Uncut_EN.mem). The other files equal GOG's.
    const string SteamExe = "86f401f951e05458c36de3a1fb90af833a31ed6c947c378600f1a3869cdbef6e";
    static readonly string[] SteamOnly = { "version.dll", "BOF4_Uncut_EN.mem" };
    static bool IsSteam(string game) { return Sha(File.ReadAllBytes(Path.Combine(game, "BOF4.exe"))) == SteamExe; }
    IEnumerable<IGrouping<string, Variant>> Files(bool steam)
    {
        return variants.GroupBy(v => v.Path).Where(g => steam ? g.Key != "BOF4.exe" : !SteamOnly.Contains(g.Key));
    }
    static readonly string Empty = Sha(new byte[0]);

    [STAThread]
    static void Main() { Application.EnableVisualStyles(); Application.Run(new Installer()); }

    static readonly Color Bg = Color.FromArgb(24, 22, 28), Panel = Color.FromArgb(38, 35, 44),
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
        Text = "Breath of Fire IV - English Uncut " + Version; Font = new Font("Segoe UI", 9f);
        BackColor = Bg; ForeColor = Fg;
        FormBorderStyle = FormBorderStyle.FixedSingle; MaximizeBox = false; StartPosition = FormStartPosition.CenterScreen;
        try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }

        var banner = new PictureBox { Location = new Point(0, 0), Size = new Size(640, 230) };
        using (var s = typeof(Installer).Assembly.GetManifestResourceStream("banner.png"))
            banner.Image = Image.FromStream(s);
        int y = 236;
        var lf = new Label { Text = "Game folder (where BOF4.exe is):", Location = new Point(16, y), AutoSize = true, ForeColor = Dim };
        folder.SetBounds(16, y + 20, 510, 24); folder.BackColor = Panel; folder.ForeColor = Fg; folder.BorderStyle = BorderStyle.FixedSingle;
        var browse = MakeButton("Browse...", Panel); browse.SetBounds(534, y + 19, 90, 25);
        browse.Click += delegate {
            using (var d = new FolderBrowserDialog { SelectedPath = folder.Text })
                if (d.ShowDialog(this) == DialogResult.OK) { folder.Text = d.SelectedPath; Detect(); }
        };
        folder.Leave += delegate { Detect(); };
        Controls.AddRange(new Control[] { banner, lf, folder, browse });

        y += 60;
        foreach (var o in options)
        {
            var cb = new CheckBox { Text = o[1], Checked = o.Length < 4 || o[3] != "off", Location = new Point(16, y), AutoSize = true,
                                    Font = new Font("Segoe UI", 9.5f, FontStyle.Bold), Tag = o[0] };
            var desc = new Label { Text = o[2], Location = new Point(34, y + 22), Size = new Size(590, 18), ForeColor = Dim };
            boxes.Add(cb); Controls.Add(cb); Controls.Add(desc); y += 46;
        }
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
        apply.Click += delegate { Run(boxes.Where(b => b.Checked).Select(b => (string)b.Tag).ToList()); };
        restore.Click += delegate { Run(new List<string>()); };
        log.SetBounds(16, y + 48, 608, 110);
        log.Multiline = true; log.ReadOnly = true; log.ScrollBars = ScrollBars.Vertical;
        log.BackColor = Panel; log.ForeColor = Fg; log.BorderStyle = BorderStyle.FixedSingle;
        Controls.AddRange(new Control[] { apply, restore, log });
        ClientSize = new Size(640, y + 48 + 110 + 16);

        string here = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        folder.Text = File.Exists(Path.Combine(here, "BOF4.exe")) ? here : FindGog() ?? here;
        Detect();
    }

    static readonly string[][] Credits = {
        new[] { "Project page, updates, issues", "github.com/d4rksp4rt4n/bof4-english-uncut", "https://github.com/d4rksp4rt4n/bof4-english-uncut" },
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
        var f = new Form { Text = "About - Breath of Fire IV English Uncut", Font = Font, BackColor = Bg, ForeColor = Fg,
                           FormBorderStyle = FormBorderStyle.FixedDialog, MaximizeBox = false, MinimizeBox = false,
                           StartPosition = FormStartPosition.CenterParent, ShowInTaskbar = false, Icon = Icon };
        int y = 14;
        var head = new Label { Text = "Breath of Fire IV (GOG, English) - Uncut & fixes " + Version, UseMnemonic = false, AutoSize = true, Location = new Point(16, y),
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
            wc.Headers[HttpRequestHeader.UserAgent] = "BOF4-Uncut-EN-installer";
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

    // tick the options that are currently installed (all ticked on an untouched game)
    void Detect()
    {
        string game = folder.Text;
        if (!File.Exists(Path.Combine(game, "BOF4.exe"))) return;
        var installed = new HashSet<string>(); bool any = false, steam = IsSteam(game);
        foreach (var g in Files(steam))
        {
            string p = Path.Combine(game, g.Key);
            if (!File.Exists(p)) continue;
            string h = Sha(File.ReadAllBytes(p));
            var hits = g.Where(v => v.Dst == h).Select(v => v.Key.Split(',')).ToList();
            if (hits.Count == 0) continue;                    // same file for several keys: only what they share
            any = true; installed.UnionWith(hits.Aggregate((a, b) => a.Intersect(b).ToArray()));
        }
        if (any) foreach (var b in boxes) b.Checked = installed.Contains((string)b.Tag);
        log.Clear();
        if (steam) Log("Steam version found (experimental): BOF4.exe stays untouched; version.dll applies its changes " +
                       "in memory at start and writes BOF4_Uncut_EN.log.");
        Log(any ? "Found an earlier install of this mod; the ticked options are the ones installed."
                : "Ready. Tick what you want and press Apply.");
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
            var plan = new List<Tuple<string, byte[], Variant>>();   // path, original bytes, target (null = original)
            bool steam = IsSteam(game);
            var exeParts = new HashSet<string>(variants.Where(v => v.Path == "BOF4.exe").SelectMany(v => v.Key.Split(',')));
            if (steam && chosen.Any(exeParts.Contains)) chosen.Add("loader");
            foreach (var g in Files(steam))
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
                else if (added && SteamOnly.Contains(g.Key) && !g.Any(v => v.Dst == h))
                    throw new Exception(g.Key + " is already there and isn't this mod's (another mod's loader?). " +
                                        "Move it away first." + Environment.NewLine + "Nothing was changed.");
                else if (added) src = new byte[0];                // only this mod adds it (maybe an older build of it)
                else if (File.Exists(bak) && Sha(File.ReadAllBytes(bak)) == orig)
                {                                                 // patched before, maybe by an older version
                    src = File.ReadAllBytes(bak);
                    if (!g.Any(v => v.Dst == h)) Log(g.Key + ": not from this version; rebuilding from the backed-up original.");
                }
                else throw new Exception(g.Key + " is not the original English GOG/Steam file (another mod, or the German patch's files?)." +
                                         Environment.NewLine + "Nothing was changed.");
                if ((target == null ? orig : target.Dst) != h) plan.Add(Tuple.Create(g.Key, src, target));
            }
            if (plan.Count == 0) { Log("Nothing to change - the game already has exactly these options."); return; }
            foreach (var t in plan)
            {
                string p = Path.Combine(game, t.Item1), bak = Path.Combine(game, BackupDir, t.Item1);
                byte[] data = t.Item3 == null ? t.Item2 : Build(t.Item2, t.Item3);
                if (t.Item2.Length > 0 && !File.Exists(bak)) { Directory.CreateDirectory(Path.GetDirectoryName(bak)); File.WriteAllBytes(bak, t.Item2); }
                if (data.Length == 0) File.Delete(p);             // restoring "no file"
                else File.WriteAllBytes(p, data);
                Log((t.Item3 == null ? "restored  " : "patched   ") + t.Item1);
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
