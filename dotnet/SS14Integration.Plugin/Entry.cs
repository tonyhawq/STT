
using System;
using System.IO;
using System.Reflection;
using System.Threading;
using HarmonyLib;
using SS14Integration.Plugin;

public static class Entry
{
    private static readonly Harmony Harmony =
        new("com.ss14integration.client");

    private static bool AttemptPatching()
    {
        Thread.Sleep(1000);
        var controllerType = AccessTools.TypeByName(
            "Content.Client.UserInterface.Systems.Chat.ChatUIController"
        );

        if (controllerType is null)
            throw new Exception("ChatUIController type not found.");

        Logger.Log($"Found controller: {controllerType.FullName}");

        var frameUpdate = AccessTools.Method(
            controllerType,
            "FrameUpdate"
        );

        if (frameUpdate == null)
            throw new Exception("FrameUpdate method not found.");

        Logger.Log($"Found method: {frameUpdate}");

        var postfix = new HarmonyMethod(
            typeof(Entry).GetMethod(
                nameof(FrameUpdatePostfix),
                BindingFlags.Static | BindingFlags.NonPublic
            )
        );

        Harmony.Patch(
            frameUpdate,
            postfix: postfix
        );

        Logger.Log("Harmony patch installed successfully.");
        return true;
    }

    public static void Initialize()
    {
        Logger.Init();
        Logger.Log("Plugin initialization started.");
        Logger.Log("Starting ChatSubmission...");
        ChatSubmission.StartReceiver();
        Logger.Log("Started ChatSubmission.");
        while (true)
        {
            try
            {
                if (AttemptPatching())
                {
                    Logger.Log("Patching successful, escaping loop.");
                    break;
                }
            }
            catch (Exception ex)
            {
                Logger.Log($"Encountered an exception while attempting patching: {ex}");
            }
        }
        Logger.Log("Patching completed.");
    }

    private static void FrameUpdatePostfix(object __instance)
    {
        try
        {
            ChatSubmission.ProcessPending(__instance);
        }
        catch (Exception ex)
        {
            Logger.Log($"Chat processing error: {ex}");
        }
    }
}
