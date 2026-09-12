Option Explicit
Dim shell, fs, folder, shortcut
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
folder = fs.GetParentFolderName(WScript.ScriptFullName)
If Not fs.FileExists(folder & "\STFC-Advisor.exe") Then
    MsgBox "Extract the complete STFC-Advisor folder first, then run this shortcut helper from that folder.", 48, "STFC Advisor"
    WScript.Quit 1
End If
Set shortcut = shell.CreateShortcut(shell.SpecialFolders("Desktop") & "\STFC Advisor.lnk")
shortcut.TargetPath = folder & "\STFC-Advisor.exe"
shortcut.WorkingDirectory = folder
shortcut.IconLocation = folder & "\STFC-Advisor.exe,0"
shortcut.Save
MsgBox "STFC Advisor is now on your desktop. Keep this extracted folder in its current location.", 64, "STFC Advisor"
