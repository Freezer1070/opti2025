using System.Collections.Concurrent;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using OmniPlayer2026.Controls;

namespace OmniPlayer2026.Services;

public sealed class PlaybackManager
{
    private readonly ConcurrentDictionary<VideoPlayerControl, string> _players = new();
    private readonly SemaphoreSlim _loadGate = new(4, 4);

    public async Task RegisterAsync(VideoPlayerControl player, string filePath, CancellationToken cancellationToken = default)
    {
        _players[player] = filePath;
        await _loadGate.WaitAsync(cancellationToken);
        try
        {
            await player.LoadAsync(filePath, cancellationToken);
        }
        finally
        {
            _loadGate.Release();
        }
    }

    public void Unregister(VideoPlayerControl player)
    {
        _players.TryRemove(player, out _);
        player.Stop();
    }

    public long GetManagedMemoryMb() => GC.GetTotalMemory(false) / (1024 * 1024);

    public long GetWorkingSetMb() => Process.GetCurrentProcess().WorkingSet64 / (1024 * 1024);
}
