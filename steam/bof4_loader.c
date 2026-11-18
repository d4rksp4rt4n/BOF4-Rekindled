// version.dll proxy for the Steam BOF4.exe (the GOG exe inside an Enigma wrapper, encrypted on disk).
// Windows loads it at startup because the wrapper imports version.dll; every export forwards to the
// system version.dll. A thread waits until the wrapper has unpacked the game, i.e. until every patch
// site holds the GOG bytes, then writes the same bytes the installer writes into the GOG exe.
// Patch list: BOF4_Uncut_EN.mem next to this DLL, one "VA ORIGHEX NEWHEX" line per site (written by the
// installer). If the bytes never match (another build), nothing is changed. Result: BOF4_Uncut_EN.log.
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <tlhelp32.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// ---------------------------------------------------------------- version.dll forwarding
#define EXPORTS(X) X(GetFileVersionInfoA) X(GetFileVersionInfoByHandle) X(GetFileVersionInfoExA) \
    X(GetFileVersionInfoExW) X(GetFileVersionInfoSizeA) X(GetFileVersionInfoSizeExA) \
    X(GetFileVersionInfoSizeExW) X(GetFileVersionInfoSizeW) X(GetFileVersionInfoW) X(VerFindFileA) \
    X(VerFindFileW) X(VerInstallFileA) X(VerInstallFileW) X(VerLanguageNameA) X(VerLanguageNameW) \
    X(VerQueryValueA) X(VerQueryValueW)
#define ENUM(n) i_##n,
enum { EXPORTS(ENUM) N_EXPORTS };
#define NAME(n) #n,
static const char *names[] = { EXPORTS(NAME) };
static FARPROC real[N_EXPORTS];
#define STUB(n) __declspec(naked) void p_##n(void) { __asm jmp real[i_##n * 4] }
EXPORTS(STUB)

static void load_real(void)
{
    char path[MAX_PATH];
    UINT n = GetSystemDirectoryA(path, MAX_PATH);        // SysWOW64 for this 32-bit process
    HMODULE h;
    int i;
    lstrcpyA(path + n, "\\version.dll");
    h = LoadLibraryA(path);
    for (i = 0; i < N_EXPORTS; i++) real[i] = h ? GetProcAddress(h, names[i]) : NULL;
}

// ---------------------------------------------------------------- patch list
typedef struct { BYTE *va; int n; BYTE *orig, *repl; } Site;
static Site *sites;
static int n_sites;
static char dir[MAX_PATH];

static void log_line(const char *fmt, ...)
{
    char path[MAX_PATH];
    FILE *f;
    va_list a;
    sprintf(path, "%sBOF4_Uncut_EN.log", dir);
    if (!(f = fopen(path, "a"))) return;
    va_start(a, fmt); vfprintf(f, fmt, a); va_end(a);
    fputc('\n', f); fclose(f);
}

static int hex(const char *s, BYTE *out)                  // returns byte count, -1 on bad input
{
    int n = 0;
    while (s[0] && s[1] && s[0] != ' ' && s[0] != '\r' && s[0] != '\n') {
        unsigned v;
        if (sscanf(s, "%2x", &v) != 1) return -1;
        out[n++] = (BYTE)v; s += 2;
    }
    return n;
}

static int load_list(void)
{
    char path[MAX_PATH], line[8192], a[4096], b[4096];
    FILE *f;
    int cap = 0;
    sprintf(path, "%sBOF4_Uncut_EN.mem", dir);
    if (!(f = fopen(path, "r"))) { log_line("no BOF4_Uncut_EN.mem: nothing to do"); return 0; }
    while (fgets(line, sizeof line, f)) {
        unsigned va;
        BYTE o[2048], r[2048];
        int no, nr;
        if (line[0] == '#' || sscanf(line, "%x %4095s %4095s", &va, a, b) != 3) continue;
        no = hex(a, o); nr = hex(b, r);
        if (no <= 0 || no != nr) { fclose(f); log_line("bad line in BOF4_Uncut_EN.mem: %s", line); return 0; }
        if (n_sites == cap) sites = realloc(sites, (cap = cap ? cap * 2 : 256) * sizeof *sites);
        sites[n_sites].va = (BYTE *)(UINT_PTR)va; sites[n_sites].n = no;
        sites[n_sites].orig = memcpy(malloc(no), o, no);
        sites[n_sites].repl = memcpy(malloc(no), r, no);
        n_sites++;
    }
    fclose(f);
    return n_sites;
}

// ---------------------------------------------------------------- waiting and patching
static int site_matches(const Site *s, BYTE *buf)        // ReadProcessMemory: no fault while still encrypted / no access
{
    SIZE_T got = 0;
    return ReadProcessMemory(GetCurrentProcess(), s->va, buf, s->n, &got) && got == (SIZE_T)s->n
        && !memcmp(buf, s->orig, s->n);
}

static int all_match(int *first_bad)
{
    static BYTE buf[2048];
    int i;
    for (i = 0; i < n_sites; i++)
        if (!site_matches(&sites[i], buf)) { *first_bad = i; return 0; }
    return 1;
}

// Suspend every other thread; give up (and resume) if one is stopped inside a site's bytes.
static int suspend_others(HANDLE *th, int max, int *n)
{
    DWORD me = GetCurrentThreadId(), pid = GetCurrentProcessId();
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    THREADENTRY32 te;
    int ok = 1, i;
    *n = 0;
    te.dwSize = sizeof te;
    if (snap == INVALID_HANDLE_VALUE) return 0;
    for (BOOL more = Thread32First(snap, &te); more && *n < max; more = Thread32Next(snap, &te)) {
        HANDLE h;
        CONTEXT c;
        if (te.th32OwnerProcessID != pid || te.th32ThreadID == me) continue;
        if (!(h = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT, FALSE, te.th32ThreadID))) continue;
        if (SuspendThread(h) == (DWORD)-1) { CloseHandle(h); continue; }
        th[(*n)++] = h;
        c.ContextFlags = CONTEXT_CONTROL;
        if (GetThreadContext(h, &c))
            for (i = 0; i < n_sites; i++)
                if (c.Eip > (DWORD)(UINT_PTR)sites[i].va && c.Eip < (DWORD)(UINT_PTR)sites[i].va + sites[i].n) ok = 0;
    }
    CloseHandle(snap);
    return ok;
}

static void resume(HANDLE *th, int n)
{
    while (n--) { ResumeThread(th[n]); CloseHandle(th[n]); }
}

static DWORD WINAPI worker(LPVOID unused)
{
    static HANDLE th[256];
    DWORD t0 = GetTickCount();
    int bad = 0, n, i;
    if (!load_list()) return 0;
    timeBeginPeriod(1);
    for (;;) {
        if (all_match(&bad)) {
            if (suspend_others(th, 256, &n) && all_match(&bad)) break;
            resume(th, n);
        }
        if (GetTickCount() - t0 > 60000) {
            BYTE buf[2048];
            SIZE_T got = 0;
            ReadProcessMemory(GetCurrentProcess(), sites[bad].va, buf, sites[bad].n, &got);
            log_line("not patched: the game's code at %08X does not match the GOG build this mod expects "
                     "(%d of %d bytes readable). Unsupported version?", (unsigned)(UINT_PTR)sites[bad].va,
                     (int)got, sites[bad].n);
            timeEndPeriod(1);
            return 0;
        }
        Sleep(1);
    }
    for (i = 0; i < n_sites; i++) {                       // pages stay writable: script inserts and the
        DWORD old;                                        // music stub's data live in the patched cave
        VirtualProtect(sites[i].va, sites[i].n, PAGE_EXECUTE_READWRITE, &old);
        memcpy(sites[i].va, sites[i].repl, sites[i].n);
    }
    FlushInstructionCache(GetCurrentProcess(), NULL, 0);
    resume(th, n);
    timeEndPeriod(1);
    log_line("patched %d sites, %lu ms after start", n_sites, GetTickCount() - t0);
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID unused)
{
    if (reason == DLL_PROCESS_ATTACH) {
        char *slash;
        DisableThreadLibraryCalls(inst);
        load_real();
        GetModuleFileNameA(inst, dir, MAX_PATH);
        if ((slash = strrchr(dir, '\\'))) slash[1] = 0;
        CloseHandle(CreateThread(NULL, 0, worker, NULL, 0, NULL));
    }
    return TRUE;
}
