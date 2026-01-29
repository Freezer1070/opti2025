using System;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Threading;
using LibVLCSharp.Shared;
using OmniPlayer2026.Services;

namespace OmniPlayer2026.Controls;

public partial class VideoPlayerControl : UserControl
{
    private readonly DispatcherTimer _positionTimer;
    private MediaPlayer? _mediaPlayer;
    private bool _isDragging;
    private bool _isSuspended;
    private int _defaultVideoTrack = -1;
    private string? _currentSource;

    public VideoPlayerControl()
    {
        InitializeComponent();
        _positionTimer = new DispatcherTimer
        {
            Interval = TimeSpan.FromMilliseconds(250)
        };
        _positionTimer.Tick += (_, _) => UpdatePosition();

        MouseEnter += (_, _) => OverlayPanel.Opacity = 1;
        MouseLeave += (_, _) => OverlayPanel.Opacity = 0;
        SizeChanged += (_, _) => ApplyResourceThrottling();
        IsVisibleChanged += (_, _) => ApplyResourceThrottling();
    }

    public async Task LoadAsync(string filePath, CancellationToken cancellationToken = default)
    {
        _currentSource = filePath;
        var libVlc = LibVlcBootstrapper.Instance;

        await Dispatcher.InvokeAsync(() =>
        {
            _mediaPlayer?.Dispose();
            _mediaPlayer = new MediaPlayer(libVlc)
            {
                EnableHardwareDecoding = true,
                RealTime = true
            };
            PlayerView.MediaPlayer = _mediaPlayer;
        }, DispatcherPriority.Send, cancellationToken);

        await Task.Run(async () =>
        {
            using var media = new Media(libVlc, new Uri(filePath));
            media.AddOption(":codec=avcodec");
            media.AddOption(":avcodec-hw=d3d11va");
            media.AddOption(":avcodec-hw=dxva2");
            media.AddOption(":network-caching=500");
            media.AddOption(":file-caching=300");
            media.AddOption(":clock-jitter=0");
            media.AddOption(":clock-synchro=0");
            await media.Parse(MediaParseOptions.ParseLocal);
            cancellationToken.ThrowIfCancellationRequested();

            await Dispatcher.InvokeAsync(() =>
            {
                _mediaPlayer?.Play(media);
                _defaultVideoTrack = _mediaPlayer?.VideoTrack ?? -1;
                _positionTimer.Start();
            }, DispatcherPriority.Background, cancellationToken);
        }, cancellationToken);
    }

    public void Stop()
    {
        _positionTimer.Stop();
        _mediaPlayer?.Stop();
    }

    private void UpdatePosition()
    {
        if (_mediaPlayer is null || _isDragging)
        {
            return;
        }

        SeekSlider.Value = _mediaPlayer.Position;
    }

    private void OnSeekChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
    {
        if (_mediaPlayer is null)
        {
            return;
        }

        if (Mouse.LeftButton == MouseButtonState.Pressed)
        {
            _isDragging = true;
            return;
        }

        if (_isDragging)
        {
            _mediaPlayer.Position = (float)SeekSlider.Value;
            _isDragging = false;
        }
    }

    private void OnPlayPauseClicked(object sender, RoutedEventArgs e)
    {
        if (_mediaPlayer is null)
        {
            return;
        }

        if (_mediaPlayer.IsPlaying)
        {
            _mediaPlayer.Pause();
        }
        else
        {
            _mediaPlayer.Play();
        }
    }

    private void OnPipClicked(object sender, RoutedEventArgs e)
    {
        if (string.IsNullOrWhiteSpace(_currentSource))
        {
            return;
        }

        var window = new Window
        {
            Title = "OmniPlayer PiP",
            Width = 480,
            Height = 270,
            WindowStyle = WindowStyle.None,
            ResizeMode = ResizeMode.CanResizeWithGrip,
            Topmost = true,
            Background = System.Windows.Media.Brushes.Black,
            Content = new VideoPlayerControl()
        };

        window.Show();
        _ = ((VideoPlayerControl)window.Content).LoadAsync(_currentSource);
    }

    private void ApplyResourceThrottling()
    {
        if (_mediaPlayer is null)
        {
            return;
        }

        var area = ActualWidth * ActualHeight;
        var shouldSuspend = !IsVisible || area < 480 * 270;

        if (shouldSuspend == _isSuspended)
        {
            return;
        }

        _isSuspended = shouldSuspend;

        if (_isSuspended)
        {
            _mediaPlayer.SetVideoTrack(-1);
        }
        else if (_defaultVideoTrack >= 0)
        {
            _mediaPlayer.SetVideoTrack(_defaultVideoTrack);
        }
    }
}
