using System.Windows;
using LibVLCSharp.Shared;
using OmniPlayer2026.Services;

namespace OmniPlayer2026;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        Core.Initialize();
        LibVlcBootstrapper.InitializeGlobalInstance();
        base.OnStartup(e);
    }
}
