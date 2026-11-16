// SPDX-License-Identifier: GPL-3.0-or-later
// Adapted from BetterGI ChildSessionProcessLauncher (see NOTICE.md).
using System.Runtime.InteropServices;
using System.Security.Principal;
using BetterGenshinImpact.Service.ChildSession;

internal static class SessionLauncher
{
    internal static void Launch(uint session, string root, string action)
    {
        if (ChildSessionNativeMethods.TryGetChildSessionId() != session)
            throw new InvalidOperationException("Child session changed");
        string exe, args, cwd;
        if (action == "game")
        {
            exe = @"D:\ZenlessZoneZero Game\ZenlessZoneZero.exe";
            args = ""; cwd = Path.GetDirectoryName(exe)!;
            if (System.Diagnostics.Process.GetProcessesByName("ZenlessZoneZero").Length > 0)
                throw new InvalidOperationException("Exit the existing game normally before starting in child session");
        }
        else if (action is "switch-ww" or "ww-backend")
        {
            exe = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "System32", "WindowsPowerShell", "v1.0", "powershell.exe");
            args = "-NoProfile -WindowStyle Hidden -File \"" + Path.Combine(root, "tools", "switch-child-ww.ps1") + "\" -SessionId " + session + (action == "ww-backend" ? " -Mode Backend" : "");
            cwd = root;
        }
        else
        {
            exe = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "System32", "WindowsPowerShell", "v1.0", "powershell.exe");
            args = "-NoProfile -WindowStyle Hidden -File \"" + Path.Combine(root, "tools", "child-session-bootstrap.ps1") + "\" -SessionId " + session + " -Mode " + action;
            cwd = root;
        }
        if (!File.Exists(exe)) throw new FileNotFoundException("Executable missing", exe);
        string name = "PlaySage-ChildSession-" + Guid.NewGuid().ToString("N");
        var objects = new List<object>();
        dynamic? folder = null;
        bool registered = false;
        try
        {
            dynamic scheduler = Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service")!)!;
            objects.Add(scheduler); scheduler.Connect();
            folder = scheduler.GetFolder("\\"); objects.Add(folder);
            dynamic definition = scheduler.NewTask(0); objects.Add(definition);
            string account = WindowsIdentity.GetCurrent().Name;
            definition.RegistrationInfo.Author = "PlaySage";
            definition.Settings.Hidden = true;
            definition.Settings.AllowDemandStart = true;
            definition.Settings.DisallowStartIfOnBatteries = false;
            definition.Settings.StopIfGoingOnBatteries = false;
            definition.Settings.ExecutionTimeLimit = "PT0S";
            definition.Principal.UserId = account;
            definition.Principal.LogonType = 3;
            definition.Principal.RunLevel = 1;
            dynamic item = definition.Actions.Create(0); objects.Add(item);
            item.Path = exe; item.Arguments = args; item.WorkingDirectory = cwd;
            dynamic task = folder.RegisterTaskDefinition(name, definition, 2, account, null, 3, null);
            objects.Add(task); registered = true;
            object running = task.RunEx(null, 4, checked((int)session), null);
            objects.Add(running);
            if (running is null) throw new InvalidOperationException("Task scheduler returned no running instance");
        }
        finally
        {
            if (registered) folder!.DeleteTask(name, 0);
            for (int i = objects.Count - 1; i >= 0; i--)
                if (Marshal.IsComObject(objects[i])) Marshal.FinalReleaseComObject(objects[i]);
        }
    }
}
