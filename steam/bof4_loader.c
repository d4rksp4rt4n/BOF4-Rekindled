// dsound.dll proxy for the Steam BOF4.exe (the GOG exe inside an Enigma wrapper, encrypted on disk).
// The game imports dsound.dll, so Windows loads this DLL from the game folder; every export forwards to
// the system dsound.dll (loaded on first use). The game's first DirectSoundCreate call comes from its own (by then unpacked)
// code: there, if every patch site holds the GOG bytes, the same bytes the installer writes into the GOG
// exe are written in memory, then the call goes on to the real DirectSoundCreate.
// Patch list: BOF4_Rekindled.mem next to this DLL, one "VA ORIGHEX NEWHEX" line per site (written by the
// installer). If the bytes don't match (another build), nothing is changed. Result: BOF4_Rekindled.log.
// No C runtime: built with /NODEFAULTLIB /ENTRY:DllMain /GS-.
#include <windows.h>

// ---------------------------------------------------------------- dsound.dll forwarding
#define EXPORTS(X) X(DirectSoundCreate) X(DirectSoundEnumerateA) X(DirectSoundEnumerateW) \
    X(DllCanUnloadNow) X(DllGetClassObject) X(DirectSoundCaptureCreate) X(DirectSoundCaptureEnumerateA) \
    X(DirectSoundCaptureEnumerateW) X(GetDeviceID) X(DirectSoundFullDuplexCreate) X(DirectSoundCreate8) \
    X(DirectSoundCaptureCreate8)
#define ENUM(n) i_##n,
enum { EXPORTS(ENUM) N_EXPORTS };
#define NAME(n) #n,
static const char *names[] = { EXPORTS(NAME) };
static FARPROC real[N_EXPORTS];
// The system dsound.dll is loaded on the first call, not in DllMain: the Steam wrapper resolves the game's
// dsound imports by module name after it unpacks, and would get the system copy if it were already loaded.
static void load_real(void)                               // stdcall exports: eax/ecx/edx are free to clobber
{
    char path[MAX_PATH];
    UINT n;
    HMODULE h;
    int i;
    if (real[0]) return;
    n = GetSystemDirectoryA(path, MAX_PATH);              // SysWOW64 for this 32-bit process
    lstrcpyA(path + n, "\\dsound.dll");
    h = LoadLibraryA(path);
    for (i = N_EXPORTS - 1; i >= 0; i--) real[i] = h ? GetProcAddress(h, names[i]) : NULL;   // real[0] last
}
#define STUB(n) __declspec(naked) void p_##n(void) { __asm { call load_real } __asm { jmp real[i_##n * 4] } }
EXPORTS(STUB)                                             // p_DirectSoundCreate is unused (see .def)

// ---------------------------------------------------------------- patch list
typedef struct { BYTE *va; int n; BYTE *orig, *repl; } Site;
static Site *sites;
static int n_sites;
static char dir[MAX_PATH];
static DWORD t0;

static void log_line(const char *fmt, ...)
{
    char path[MAX_PATH], buf[1100];
    HANDLE f;
    DWORD w;
    va_list a;
    int n;
    lstrcpyA(path, dir); lstrcatA(path, "BOF4_Rekindled.log");
    va_start(a, fmt); n = wvsprintfA(buf, fmt, a); va_end(a);
    buf[n++] = '\n';
    f = CreateFileA(path, FILE_APPEND_DATA, FILE_SHARE_READ, NULL, OPEN_ALWAYS, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) return;
    WriteFile(f, buf, n, &w, NULL);
    CloseHandle(f);
}

static char *chr(char *s, char c)                       // strchr / strrchr without the C runtime
{
    for (; *s; s++) if (*s == c) return s;
    return NULL;
}

static int nib(char c)
{
    return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
}

static char *word(char **p)                               // next space-separated word on the line
{
    char *s = *p;
    while (*s == ' ' || *s == '\t') s++;
    *p = s;
    while (**p && **p != ' ' && **p != '\t') (*p)++;
    return *p > s ? s : NULL;
}

static int hex(const char *s, const char *e, BYTE *out)  // byte count, -1 on bad input
{
    int n = 0;
    if ((e - s) & 1) return -1;
    for (; s < e; s += 2) {
        int hi = nib(s[0]), lo = nib(s[1]);
        if (hi < 0 || lo < 0) return -1;
        out[n++] = (BYTE)(hi << 4 | lo);
    }
    return n;
}

static int load_list(void)
{
    char path[MAX_PATH], *text, *line, *next;
    HANDLE f, heap = GetProcessHeap();
    DWORD size, got;
    int cap = 0;
    lstrcpyA(path, dir); lstrcatA(path, "BOF4_Rekindled.mem");
    f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) { log_line("no BOF4_Rekindled.mem: nothing to do"); return 0; }
    size = GetFileSize(f, NULL);
    text = HeapAlloc(heap, 0, size + 1);
    ReadFile(f, text, size, &got, NULL);
    CloseHandle(f);
    text[got] = 0;
    for (line = text; line && *line; line = next) {
        char *p, *a, *ae, *b, *be, *v, *ve;
        BYTE *o, *r;
        DWORD va = 0;
        int no, nr;
        if ((next = chr(line, '\n'))) *next++ = 0;
        if ((p = chr(line, '\r'))) *p = 0;
        p = line;
        if (*line == '#' || !(v = word(&p))) continue;
        ve = p;
        for (; v < ve; v++) { int d = nib(*v); if (d < 0) break; va = va << 4 | d; }
        if (!(a = word(&p))) continue; ae = p;
        if (!(b = word(&p))) continue; be = p;
        o = HeapAlloc(heap, 0, (ae - a) / 2 + 1); r = HeapAlloc(heap, 0, (be - b) / 2 + 1);
        no = hex(a, ae, o); nr = hex(b, be, r);
        if (v < ve || no <= 0 || no != nr) { log_line("bad line in BOF4_Rekindled.mem: %s", line); return n_sites = 0; }
        if (n_sites == cap)
            sites = sites ? HeapReAlloc(heap, 0, sites, (cap *= 2) * sizeof *sites)
                          : HeapAlloc(heap, 0, (cap = 256) * sizeof *sites);
        sites[n_sites].va = (BYTE *)(UINT_PTR)va; sites[n_sites].n = no;
        sites[n_sites].orig = o; sites[n_sites].repl = r;
        n_sites++;
    }
    return n_sites;
}

// ---------------------------------------------------------------- checking and patching
static int site_matches(const Site *s)                    // ReadProcessMemory: no fault if unreadable
{
    static BYTE buf[2048];
    SIZE_T got = 0;
    int i;
    if (!ReadProcessMemory(GetCurrentProcess(), s->va, buf, s->n, &got) || got != (SIZE_T)s->n) return 0;
    for (i = 0; i < s->n; i++) if (buf[i] != s->orig[i]) return 0;
    return 1;
}

static void patch(void)
{
    int i, j;
    if (!load_list()) return;
    for (i = 0; i < n_sites; i++)
        if (!site_matches(&sites[i])) {
            BYTE buf[2048];
            SIZE_T got = 0;
            ReadProcessMemory(GetCurrentProcess(), sites[i].va, buf, sites[i].n, &got);
            log_line("not patched: the game's code at %08X does not match the GOG build this mod expects "
                     "(%d of %d bytes readable). Unsupported version?", (unsigned)(UINT_PTR)sites[i].va,
                     (int)got, sites[i].n);
            return;
        }
    for (i = 0; i < n_sites; i++) {                       // pages stay writable: script inserts and the
        DWORD old;                                        // music stub's data live in the patched cave
        VirtualProtect(sites[i].va, sites[i].n, PAGE_EXECUTE_READWRITE, &old);
        for (j = 0; j < sites[i].n; j++) sites[i].va[j] = sites[i].repl[j];
    }
    FlushInstructionCache(GetCurrentProcess(), NULL, 0);
    log_line("patched %d sites, %lu ms after start", n_sites, GetTickCount() - t0);
}

typedef HRESULT (WINAPI *DSCreate)(const GUID *, void **, void *);

HRESULT WINAPI DirectSoundCreate_hook(const GUID *dev, void **ds, void *outer)
{
    static LONG done;
    if (!InterlockedExchange(&done, 1)) patch();
    load_real();
    return real[i_DirectSoundCreate] ? ((DSCreate)real[i_DirectSoundCreate])(dev, ds, outer) : E_FAIL;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID unused)
{
    if (reason == DLL_PROCESS_ATTACH) {
        char *slash;
        t0 = GetTickCount();
        DisableThreadLibraryCalls(inst);
        GetModuleFileNameA(inst, dir, MAX_PATH);
        for (slash = dir; chr(slash, '\\'); slash = chr(slash, '\\') + 1) ;
        *slash = 0;                                       // cut after the last backslash
    }
    return TRUE;
}
