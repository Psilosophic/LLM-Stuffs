<#
.SYNOPSIS
  Pops a Windows toast reminding you to compile the Brain (raw\ -> wiki\).
.DESCRIPTION
  Dependency-free (uses the built-in WinRT toast API attributed to PowerShell,
  no modules to install). Meant to be run on a schedule by Task Scheduler.
  Keeps the compile MANUAL — it only reminds; you decide when to run it.
#>

$ErrorActionPreference = 'SilentlyContinue'

try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.UI.Notifications.ToastNotification,        Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null

    # Attribute the toast to PowerShell so it actually surfaces.
    $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'

    $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
        [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $texts = $xml.GetElementsByTagName('text')
    $texts.Item(0).AppendChild($xml.CreateTextNode('🧠 Second Brain')) | Out-Null
    $texts.Item(1).AppendChild($xml.CreateTextNode(
        'Time to compile. Double-click compile-now.cmd (or run the compile in Claude Code).')) | Out-Null

    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
}
catch {
    # Fallback for any host where WinRT toasts aren't available: a simple popup.
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(
        'Time to compile your Second Brain (raw\ -> wiki\). Run compile-now.cmd when ready.',
        'Second Brain reminder') | Out-Null
}
