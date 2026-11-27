namespace SS14Integration.Plugin
{
    static class Logger
    {
        public static string? logPath = null;

        public static void Init()
        {
            string? logDirectory = Environment.GetEnvironmentVariable(
                "STT_INTEGRATION_LOGDIR"
            );
            if (string.IsNullOrWhiteSpace(logDirectory))
            {
                throw new InvalidOperationException(
                    "STT_INTEGRATION_LOGDIR was not provided by the bootstrapper."
                );
            }
            logPath = Path.Combine(
                logDirectory,
                "plugin.log"
            );
        }
        public static void Log(string message)
        {
            if (logPath == null)
            {
                throw new NullReferenceException("Expected logPath to be set before calling Logger.Log.");    
            }
            File.AppendAllText(
                logPath,
                $"(PLUGIN) [{DateTime.Now:HH:mm:ss.fff}] {message}{Environment.NewLine}"
            );
        }
    }
}