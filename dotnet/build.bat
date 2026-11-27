dotnet build SS14Integration.Bootstrap
dotnet build SS14Integration.Plugin
dotnet build SS14Integration.App
MOVE /Y "SS14Integration.Bootstrap\bin\Debug\net10.0\SS14Integration.Bootstrap.dll" "built\SS14Integration.Bootstrap.dll"
MOVE /Y "SS14Integration.Plugin\bin\Debug\net10.0\SS14Integration.Plugin.dll" "built\SS14Integration.Plugin.dll"
MOVE /Y "SS14Integration.App\bin\Debug\net10.0\*" "built\"