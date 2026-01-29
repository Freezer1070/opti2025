using LibVLCSharp.Shared;

namespace OmniPlayer2026.Services;

public static class LibVlcBootstrapper
{
    private static readonly object Sync = new();
    private static LibVLC? _instance;

    public static LibVLC Instance => _instance ?? throw new InvalidOperationException("LibVLC not initialized.");

    public static void InitializeGlobalInstance()
    {
        lock (Sync)
        {
            if (_instance != null)
            {
                return;
            }

            _instance = new LibVLC(
                "--avcodec-hw=d3d11va",
                "--avcodec-hw=dxva2",
                "--drop-late-frames",
                "--skip-frames",
                "--file-caching=300",
                "--network-caching=500",
                "--live-caching=300",
                "--no-sub-autodetect-file",
                "--clock-jitter=0",
                "--clock-synchro=0",
                "--no-video-title-show");
        }
    }
}
