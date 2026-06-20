$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Dota Coach AI.lnk"
$TargetPath = Join-Path $Root "DotaCoach.vbs"
$IconPath = Join-Path $Root "ui\assets\dota_coach.ico"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = "Dota Coach AI"
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = $IconPath
}
$Shortcut.Save()

Write-Host "Desktop shortcut created: $ShortcutPath"
