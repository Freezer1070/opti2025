using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using OmniPlayer2026.Controls;
using OmniPlayer2026.Services;

namespace OmniPlayer2026;

public partial class MainWindow : Window
{
    private readonly PlaybackManager _playbackManager = new();

    public MainWindow()
    {
        InitializeComponent();
        MouseLeftButtonDown += (_, _) => DragMove();
    }

    private async Task AddPlayersAsync(IEnumerable<string> files)
    {
        var tasks = new List<Task>();
        foreach (var file in files)
        {
            var control = new VideoPlayerControl();
            PlayersHost.Items.Add(control);
            tasks.Add(_playbackManager.RegisterAsync(control, file));
        }

        await Task.WhenAll(tasks);
    }

    private async void OnDropFiles(object sender, DragEventArgs e)
    {
        if (!e.Data.GetDataPresent(DataFormats.FileDrop))
        {
            return;
        }

        var files = (string[])e.Data.GetData(DataFormats.FileDrop);
        await AddPlayersAsync(files.Where(File.Exists));
    }

    private void OnDragOver(object sender, DragEventArgs e)
    {
        e.Effects = DragDropEffects.Copy;
        e.Handled = true;
    }

    private void OnMinimizeClicked(object sender, RoutedEventArgs e) => WindowState = WindowState.Minimized;

    private void OnMaximizeClicked(object sender, RoutedEventArgs e) =>
        WindowState = WindowState == WindowState.Maximized ? WindowState.Normal : WindowState.Maximized;

    private void OnCloseClicked(object sender, RoutedEventArgs e) => Close();
}
