// SPDX-License-Identifier: GPL-3.0-or-later
// Reuses BetterGI's unmodified RDP host and native helpers; see NOTICE.md.
using System.Diagnostics;
using System.Text.Json;
using BetterGenshinImpact.Service.ChildSession;
using BetterGenshinImpact.View.Controls.ChildSession;

internal static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        if (args.Length != 1 || !Directory.Exists(args[0])) return;
        string root = Path.GetFullPath(args[0]);
        string logs = Path.Combine(root, "runs", "services", "child-session");
        Directory.CreateDirectory(logs);
        ApplicationConfiguration.Initialize();
        Application.Run(new SessionForm(root, logs));
    }
}

internal sealed class SessionForm : Form
{
    readonly string root, logs;
    readonly RdpActiveXHost host = new();
    readonly Label status = new() { Dock = DockStyle.Bottom, Height = 32 };
    readonly System.Windows.Forms.Timer timer = new() { Interval = 1000 };
    bool loggedIn;
    uint? session;
    readonly HashSet<string> launched = new();

    public SessionForm(string root, string logs)
    {
        this.root = root; this.logs = logs;
        Text = "PlaySage 桌面分身 — BetterGI Child Session";
        ClientSize = new Size(1000, 600);
        Controls.Add(host); Controls.Add(status);
        host.SetAudioMuted(true);
        host.LoginCompleted += (_, _) =>
        {
            session = ChildSessionNativeMethods.TryGetChildSessionId();
            loggedIn = session.HasValue;
            Save(loggedIn ? "connected" : "session_id_missing");
        };
        host.ConnectionFailed += (_, e) => { loggedIn = false; Save("connection_failed", e.Message); };
        Shown += (_, _) =>
        {
            try
            {
                var issues = ChildSessionEnvironmentCheck.Collect();
                if (issues.Count > 0) throw new InvalidOperationException(ChildSessionEnvironmentCheck.BuildSummary(issues));
                if (ChildSessionNativeMethods.IsRdpWrapperEnabled()) throw new InvalidOperationException("RDP Wrapper detected; no configuration changes made.");
                if (!ChildSessionNativeMethods.IsChildSessionsEnabled()) throw new InvalidOperationException("Child Session is disabled; no system settings changed.");
                Save("connecting");
                host.ConnectToChildSession(new Size(1920, 1080));
                timer.Start();
            }
            catch (Exception e) { Save("preflight_failed", e.GetBaseException().Message); }
        };
        timer.Tick += (_, _) => ProcessRequest();
        FormClosing += (_, _) =>
        {
            timer.Stop();
            // Disconnect the viewer only. Never log off a session or kill its game.
            host.DisconnectSession(); Save("viewer_closed");
        };
    }

    void Save(string state, string? error = null)
    {
        status.Text = state + (error == null ? "" : " — " + error);
        string path = Path.Combine(logs, "status.json");
        var data = new { state, error, session_id = session, host_pid = Environment.ProcessId,
            parent_session_id = Process.GetCurrentProcess().SessionId,
            at = DateTimeOffset.UtcNow, launched = launched.ToArray() };
        File.WriteAllText(path + ".tmp", JsonSerializer.Serialize(data, new JsonSerializerOptions { WriteIndented = true }));
        File.Move(path + ".tmp", path, true);
    }

    void ProcessRequest()
    {
        string path = Path.Combine(logs, "request.json");
        if (!File.Exists(path)) return;
        try
        {
            using var request = JsonDocument.Parse(File.ReadAllText(path));
            string action = request.RootElement.GetProperty("action").GetString() ?? "";
            uint expected = request.RootElement.GetProperty("session_id").GetUInt32();
            File.Move(path, Path.Combine(logs, "last-request.json"), true);
            if (!loggedIn || host.ConnectedState != 1 || session != expected ||
                ChildSessionNativeMethods.TryGetChildSessionId() != expected)
                throw new InvalidOperationException("Child session identity/connection changed");
            if (action == "hide") { Hide(); Save("connected_hidden"); return; }
            if (action == "show") { Show(); Save("connected"); return; }
            if (action is not ("probe" or "backend" or "game" or "switch-ww" or "ww-backend")) throw new InvalidOperationException("Unknown action");
            if (launched.Contains(action)) throw new InvalidOperationException("Already launched; inspect existing process before retry");
            SessionLauncher.Launch(expected, root, action);
            launched.Add(action);
            Save("launch_requested");
        }
        catch (Exception e) { Save("request_failed", e.GetBaseException().Message); }
    }
}
