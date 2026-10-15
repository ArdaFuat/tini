# IShellLinkW preserves Turkish names and paths, including both dotless ı characters.
function New-TiniShortcuts([string]$Root, [string[]]$Folders) {
    if (-not ('TiniSetup.Shortcuts' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
namespace TiniSetup {
    [ComImport, Guid("00021401-0000-0000-C000-000000000046")]
    class ShellLink { }
    [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown),
     Guid("000214F9-0000-0000-C000-000000000046")]
    interface IShellLinkW {
        void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int count, IntPtr data, uint flags);
        void GetIDList(out IntPtr id);
        void SetIDList(IntPtr id);
        void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder text, int count);
        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string text);
        void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int count);
        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string path);
        void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder text, int count);
        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string text);
        void GetHotkey(out short hotkey);
        void SetHotkey(short hotkey);
        void GetShowCmd(out int cmd);
        void SetShowCmd(int cmd);
        void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int count, out int index);
        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string path, int index);
        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path, uint reserved);
        void Resolve(IntPtr window, uint flags);
        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string path);
    }
    public static class Shortcuts {
        public static void Create(string file, string target, string args, string root, string icon) {
            var link = (IShellLinkW)new ShellLink();
            try {
                link.SetPath(target);
                link.SetArguments(args);
                link.SetWorkingDirectory(root);
                link.SetIconLocation(icon, 0);
                link.SetDescription("Tını - Türkçe konuşarak yaz");
                link.SetShowCmd(1);
                ((IPersistFile)link).Save(file, true);
            } finally { Marshal.FinalReleaseComObject(link); }
        }
    }
}
'@
    }
    foreach ($folder in $Folders) {
        if (-not $folder) { continue }
        [IO.Directory]::CreateDirectory($folder) | Out-Null
        [TiniSetup.Shortcuts]::Create(
            (Join-Path $folder 'Tını.lnk'),
            (Join-Path $Root '.venv\Scripts\pythonw.exe'),
            ('"' + (Join-Path $Root 'launcher.pyw') + '"'),
            $Root, (Join-Path $Root 'assets\ses.ico'))
    }
}
