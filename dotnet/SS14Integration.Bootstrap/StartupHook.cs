using System;
using System.IO;
using System.Reflection;
using System.Runtime.Loader;
using System.Runtime.InteropServices;

public static class StartupHook
{
    public static void Initialize()
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
        string logPath = Path.Combine(
            logDirectory,
            "plugin.log"
        );
        void Log(string message)
        {
            try
            {
                File.AppendAllText(
                    logPath,
                    $"(BOOTSTRAP) [{DateTime.Now:HH:mm:ss.fff}] {message}{Environment.NewLine}"
                );
            }
            catch {}
        }

        try
        {
            Log("StartupHook::Initialize called.");
            string builtDirectory = Path.GetDirectoryName(
                Assembly.GetExecutingAssembly().Location
            )!;

            string pluginPath = Path.Combine(
                builtDirectory,
                "SS14Integration.Plugin.dll"
            );

            Log($"Runtime: {RuntimeInformation.FrameworkDescription}");
            Log($"Target framework: {AppContext.TargetFrameworkName}");
            Log($"Bootstrap directory: {builtDirectory}");
            Log($"Plugin path: {pluginPath}");
            Log($"Current directory: {Environment.CurrentDirectory}");
            Log($"AppContext.BaseDirectory: {AppContext.BaseDirectory}");
            Log($"Bootstrap assembly: {Assembly.GetExecutingAssembly().Location}");
            Log($"Log path: {logPath}");

            if (!File.Exists(pluginPath))
                throw new FileNotFoundException(
                    "Plugin DLL was not found.",
                    pluginPath
                );

            AssemblyLoadContext.Default.Resolving += (_, name) =>
            {
                string dependencyPath = Path.Combine(
                    builtDirectory,
                    name.Name + ".dll"
                );

                if (File.Exists(dependencyPath))
                {
                    Log($"Resolving dependency: {dependencyPath}");

                    return AssemblyLoadContext.Default.LoadFromAssemblyPath(
                        dependencyPath
                    );
                }

                return null;
            };

            Assembly plugin =
                AssemblyLoadContext.Default.LoadFromAssemblyPath(pluginPath);

            Log($"Plugin loaded: {plugin.FullName}");
            var entryType = plugin.GetTypes()
                .FirstOrDefault(t =>
                    t.GetMethod(
                        "Initialize",
                        BindingFlags.Public | BindingFlags.Static,
                        binder: null,
                        types: Type.EmptyTypes,
                        modifiers: null
                    ) != null
                );

            if (entryType == null)
            {
                Log("Available plugin types:");

                foreach (var type in plugin.GetTypes())
                    Log($"  {type.FullName}");

                throw new Exception(
                    "Could not find a public static Initialize() method."
                );
            }

            Log($"Found entry point: {entryType.FullName}");

            var initialize = entryType.GetMethod(
                "Initialize",
                BindingFlags.Public | BindingFlags.Static,
                binder: null,
                types: Type.EmptyTypes,
                modifiers: null
            )!;

            Log("Invoking plugin...");

            initialize.Invoke(null, null);

            Log("Plugin initialization invoked.");
        }
        catch (Exception ex)
        {
            Log($"Encountered an exception: {ex}");
        }
    }
}