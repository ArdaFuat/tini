Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
folder = fs.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = folder
If fs.FileExists(folder & "\.venv\Scripts\pythonw.exe") Then
    shell.Run """" & folder & "\.venv\Scripts\pythonw.exe"" """ & folder & "\launcher.pyw""", 1, False
Else
    shell.Run "wscript.exe """ & folder & "\Kur.vbs""", 0, False
End If
