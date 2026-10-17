Option Explicit

Dim shell, fso, folder, appPath, command, exitCode
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
appPath = folder & "\run_app.pyw"

exitCode = shell.Run("cmd /c where pyw >nul 2>nul", 0, True)
If exitCode = 0 Then
    command = "pyw -3 """ & appPath & """"
    shell.Run command, 0, False
    WScript.Quit 0
End If

exitCode = shell.Run("cmd /c where pythonw >nul 2>nul", 0, True)
If exitCode = 0 Then
    command = "pythonw """ & appPath & """"
    shell.Run command, 0, False
    WScript.Quit 0
End If

MsgBox "Python wurde nicht gefunden. Bitte installieren Sie Python 3.10 oder neuer von python.org und aktivieren Sie bei der Installation 'Add python.exe to PATH'.", 48, "Podcast-Transkript-Exporter"

