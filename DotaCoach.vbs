Option Explicit

Dim shell, fso, base, pyw, script, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

base = fso.GetParentFolderName(WScript.ScriptFullName)
pyw = base & "\.venv\Scripts\pythonw.exe"
script = base & "\DotaCoach.pyw"

If Not fso.FileExists(pyw) Then
  MsgBox "Не найдено виртуальное окружение .venv. Сначала один раз запусти setup_windows.bat, потом снова открой DotaCoach.vbs.", 48, "Dota Coach AI"
  WScript.Quit 1
End If

If Not fso.FileExists(script) Then
  MsgBox "Не найден файл DotaCoach.pyw.", 48, "Dota Coach AI"
  WScript.Quit 1
End If

shell.CurrentDirectory = base
cmd = """" & pyw & """ """ & script & """"
shell.Run cmd, 0, False
