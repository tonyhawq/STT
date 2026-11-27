
using System.Diagnostics;
using Microsoft.Diagnostics.NETCore.Client;

namespace SS14Integration.App
{
    class Program
    {
        enum ExitCode
        {
            Success = 0,
            InvalidArguments = 2,
            ProcessDead = 3,
            ProcessNotFound = 4,
            DiagnosticsUnavailable = 5,
            BootstrapNotFound = 6,
            AttachmentFailed = 7
        }

        private static readonly string logDirectory = Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "logs/"
        );
        private static readonly string logPath = Path.Combine(
            logDirectory,
            "plugin.log"
        );

        static void LogStandard(string message)
        {
            Console.WriteLine(message);
            try
            {
                File.AppendAllText(
                    logPath,
                    $"(INJECTOR) [{DateTime.Now:HH:mm:ss.fff}] {message}{Environment.NewLine}"
                );
            }
            catch {}
        }

        static void LogError(string message)
        {
            Console.Error.WriteLine(message);
            try
            {
                File.AppendAllText(
                    logPath,
                    $"(INJECTOR) [{DateTime.Now:HH:mm:ss.fff}] ERROR: {message}{Environment.NewLine}"
                );
            }
            catch {}
        }

        static int Main(string[] args)
        {
            Directory.CreateDirectory(logDirectory);
            File.CreateText(logPath).Close();
            if (args.Length != 1 || !int.TryParse(args[0], out var pid))
            {
                LogError("Usage: SS14Integration.exe <PID>");
                return (int)ExitCode.InvalidArguments;
            }
            Process process; // memory leak but this program is short lived so...
            try
            {
                process = Process.GetProcessById(pid);
                if (process.HasExited)
                {
                    LogError($"The process with pid {pid} is dead.");
                    return (int)ExitCode.ProcessDead;
                }
            }
            catch (ArgumentException)
            {
                LogError($"No process with pid {pid} found.");
                return (int)ExitCode.ProcessNotFound;
            }
            var publishedProcesses = DiagnosticsClient.GetPublishedProcesses();

            if (!publishedProcesses.Contains(pid))
            {
                LogError(
                    "Process does not expose a .NET diagnostics endpoint."
                );
                return (int)ExitCode.DiagnosticsUnavailable;
            }

            LogStandard($"Target: {process.ProcessName}");
            LogStandard($"PID: {pid}");
            var bootstrapName = "SS14Integration.Bootstrap.dll";

            var hookPath = Path.GetFullPath(
                Path.Combine(
                    AppContext.BaseDirectory,
                    bootstrapName
                )
            );

            LogStandard(hookPath);

            if (!File.Exists(hookPath))
            {
                LogError($"Bootstrap assembly not found, expected {bootstrapName} to be located at {hookPath}.");
                return (int)ExitCode.BootstrapNotFound;
            }

            LogStandard($"Bootstrap and plugin logging directory: {logDirectory}");

            try
            {
                var diagnostics = new DiagnosticsClient(pid);

                diagnostics.SetEnvironmentVariable(
                    "STT_INTEGRATION_LOGDIR",
                    logDirectory
                );
                diagnostics.ApplyStartupHook(hookPath);

                LogStandard("Startup hook successfully applied.");
                return (int)ExitCode.Success;
            }
            catch (Exception ex)
            {
                LogError($"Attachment failed: {ex.Message}");
                return (int)ExitCode.AttachmentFailed;
            }
        }
    }
}