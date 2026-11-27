
using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Linq;
using System.Reflection;
using System.IO;
using System.IO.Pipes;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

using HarmonyLib;

namespace SS14Integration.Plugin
{
    public static class ChatSubmission
    {
        private const string RXPipeName = "python_tx_pipe";
        private const string TXPipeName = "cs_tx_pipe";
        private static int _receiverStarted;

        /// <summary>
        /// Starts the named-pipe server on a background thread.
        /// Call once during plugin initialization.
        /// </summary>
        public static void StartReceiver()
        {
            if (Interlocked.Exchange(ref _receiverStarted, 1) != 0)
                return;

            Logger.Log("ChatSubmission Receiver started.");
            Task.Run(PipeServerLoop);
        }

        private static async Task PipeServerLoop()
        {
            while (true)
            {
                try
                {
                    using var rxPipe = new NamedPipeClientStream(
                        ".",
                        RXPipeName,
                        PipeDirection.In,
                        PipeOptions.Asynchronous
                    );

                    using var txPipe = new NamedPipeClientStream(
                        ".",
                        TXPipeName,
                        PipeDirection.Out,
                        PipeOptions.Asynchronous
                    );
                    
                    Logger.Log($"Attempting to connect rxPipe \"{RXPipeName}\" with server \".\"...");
                    await rxPipe.ConnectAsync();
                    Logger.Log($"Attempting to connect txPipe \"{TXPipeName}\" with server \".\"...");
                    await txPipe.ConnectAsync();
                    Logger.Log("Pipes connected, creating StreamReader and StreamWriter...");

                    using var reader = new StreamReader(
                        rxPipe,
                        System.Text.Encoding.UTF8,
                        false,
                        1024,
                        leaveOpen: true
                    );

                    using var writer = new StreamWriter(
                        txPipe,
                        new System.Text.UTF8Encoding(false),
                        1024,
                        leaveOpen: true
                    )
                    {
                        AutoFlush = true,
                        NewLine = "\n"
                    };

                    Logger.Log("Attempting to write connection ack...");
                    writer.WriteLine("STARTED");
                    Logger.Log("Wrote connection ack.");

                    string? line;

                    while ((line = await reader.ReadLineAsync()) != null)
                    {
                        Logger.Log($"Received message {line} from rx pipe.");
                        try
                        {
                            using var document = JsonDocument.Parse(line);

                            if (!document.RootElement.TryGetProperty(
                                    "text", out var textElement) ||
                                textElement.ValueKind != JsonValueKind.String)
                            {
                                Logger.Log($"Received message was of invalid format.");
                                writer.WriteLine("ERR: Invalid message format");
                                continue;
                            }

                            var text = textElement.GetString();

                            if (text == "@HEARTBEAT")
                            {
                                Logger.Log($"Received heartbeat request, ack'ing OK");
                                writer.WriteLine("OK");
                                continue;
                            }

                            if (string.IsNullOrWhiteSpace(text))
                            {
                                Logger.Log($"Received message was empty.");
                                writer.WriteLine("ERR: Empty transcript");
                                continue;
                            }

                            Enqueue(text);

                            // Acknowledge successful queue insertion.
                            Logger.Log($"Writing OK ack!");
                            writer.WriteLine("OK");
                        }
                        catch (JsonException)
                        {
                            Logger.Log($"Message was invalid JSON.");
                            writer.WriteLine("ERR: Invalid JSON");
                        }
                        catch (Exception ex)
                        {
                            Logger.Log($"Got an error while receiving or sending ack: {ex}");
                            System.Diagnostics.Trace.TraceError(
                                $"[SS14Integration] Pipe message error: {ex}"
                            );

                            writer.WriteLine("ERR: Internal error");
                        }
                    }
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Trace.TraceError(
                        $"[SS14Integration] Pipe server error: {ex}"
                    );

                    await Task.Delay(1000);
                }
            }
        }

        private static readonly ConcurrentQueue<string> PendingMessages = new();

        /// <summary>
        /// Called by the named-pipe receiver when a transcript arrives.
        /// Safe to call from another thread.
        /// </summary>
        public static void Enqueue(string message)
        {
            if (string.IsNullOrWhiteSpace(message))
                return;

            PendingMessages.Enqueue(message.Trim());
        }

        /// <summary>
        /// Called from ChatUIController.FrameUpdate on the SS14 client thread.
        /// </summary>
        public static void ProcessPending(object controller)
        {
            while (PendingMessages.TryDequeue(out var message))
            {
                try
                {
                    Submit(controller, message);
                }
                catch (Exception ex)
                {
                    Trace.TraceError(
                        $"[SS14Integration] Chat submission failed: {ex}"
                    );
                }
            }
        }

        private static void Submit(object controller, string message)
        {
            var controllerType = controller.GetType();

            // Retrieve ChatUIController's private client chat manager.
            var managerField = AccessTools.Field(
                controllerType,
                "_manager"
            );

            if (managerField == null)
                throw new MissingFieldException(
                    controllerType.FullName,
                    "_manager"
                );

            var manager = managerField.GetValue(controller);

            if (manager == null)
                throw new InvalidOperationException(
                    "Chat manager has not been initialized."
                );

            // Retrieve the client-side IChatManager.SendMessage method.
            // This is deliberately selected from the interface rather
            // than relying on the concrete implementation's type.
            var chatInterface = manager.GetType()
                .GetInterfaces()
                .FirstOrDefault(i =>
                    i.FullName == "Content.Client.Chat.Managers.IChatManager"
                );

            if (chatInterface == null)
                throw new TypeLoadException(
                    "Could not find Content.Client.Chat.Managers.IChatManager."
                );

            var sendMethod = chatInterface.GetMethod(
                "SendMessage",
                new[] { typeof(string), GetChannelType(controller) }
            );

            if (sendMethod == null)
                throw new MissingMethodException(
                    chatInterface.FullName,
                    "SendMessage"
                );

            var channelType = sendMethod.GetParameters()[1].ParameterType;

            // Use ChatUIController's own prefix/channel parser.
            // This preserves SS14's existing handling of radio,
            // whisper, emotes, OOC, etc.
            var splitMethod = controllerType.GetMethod(
                "SplitInputContents",
                BindingFlags.Instance | BindingFlags.Public
            );

            if (splitMethod == null)
                throw new MissingMethodException(
                    controllerType.FullName,
                    "SplitInputContents"
                );

            var splitResult = splitMethod.Invoke(
                controller,
                new object[] { message }
            );

            if (splitResult == null)
                return;

            // SplitInputContents returns a ValueTuple:
            // (ChatSelectChannel chatChannel, string text,
            //  RadioChannelPrototype? radioChannel)
            var tupleType = splitResult.GetType();

            var parsedChannel = tupleType
                .GetField("Item1")?
                .GetValue(splitResult);

            var parsedText = tupleType
                .GetField("Item2")?
                .GetValue(splitResult) as string;

            if (parsedText == null || parsedText.Length == 0)
                return;

            // Match ChatUIController's maximum message length check.
            var maxLengthProperty = controllerType.GetProperty(
                "MaxMessageLength",
                BindingFlags.Instance | BindingFlags.Public
            );

            if (maxLengthProperty?.GetValue(controller) is int maxLength
                && parsedText.Length > maxLength)
            {
                Trace.TraceWarning(
                    $"[SS14Integration] Message rejected: " +
                    $"{parsedText.Length} characters exceeds limit {maxLength}."
                );
                return;
            }

            // The normal default channel for voice transcription is Local.
            // If the parser recognized an explicit channel prefix, use it.
            object channel;

            if (parsedChannel != null &&
                !parsedChannel.ToString()!.Equals(
                    "None",
                    StringComparison.Ordinal
                ))
            {
                channel = parsedChannel;
            }
            else
            {
                channel = Enum.Parse(channelType, "Local");
            }

            sendMethod.Invoke(
                manager,
                new object[] { parsedText, channel }
            );
        }

        private static Type GetChannelType(object controller)
        {
            var splitMethod = controller.GetType().GetMethod(
                "SplitInputContents",
                BindingFlags.Instance | BindingFlags.Public
            );

            if (splitMethod == null)
                throw new MissingMethodException(
                    controller.GetType().FullName,
                    "SplitInputContents"
                );

            // Extract ChatSelectChannel from the first tuple element.
            var tupleType = splitMethod.ReturnType;
            var channelType = tupleType.GetGenericArguments()[0];

            return channelType;
        }
    }
}
