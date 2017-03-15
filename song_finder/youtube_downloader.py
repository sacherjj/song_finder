from circuits import Component, Timer, Event, handler, Manager
from circuits.io import Process
from collections import deque
import sys
import os
import inspect
import time

__author__ = "Joe Sacher <sacherjj@gmail.com>"


def get_script_dir(follow_symlinks=True):
    if getattr(sys, 'frozen', False):  # py2exe, PyInstaller, cx_Freeze
        path = os.path.abspath(sys.executable)
    else:
        path = inspect.getabsfile(get_script_dir)
    if follow_symlinks:
        path = os.path.realpath(path)
    return os.path.dirname(path)


class youtube_download(Event):
    """ Use url argument for starting download. """


class youtube_download_complete(Event):
    """ Fired on finished download. """


class youtube_error(Event):
    """ Fires when YouTube download errors. """


class process_download(Event):
    """ Start async download. """


class poll_process(Event):
    """ Check if Process is complete. """


class YoutubeDownloader(Component):
    channel = 'youtube'
    EXPECTED_MAX_SIZE = 15

    def init(self, quality=3, rate_limit=None):
        self.manager = Manager()
        script_dir = get_script_dir()
        save_dir = os.path.join(script_dir, 'songs')
        if not os.path.exists(save_dir):
            os.mkdir(save_dir)
        print('Script Dir: {}'.format(script_dir))
        print('Saving to: {}'.format(save_dir))
        self.save_dir = save_dir

        self.options = ['--extract-audio',
                        '--prefer-ffmpeg',
                        '--audio-format mp3',
                        '--ffmpeg {}'.format(script_dir),
                        '--audio-quality {}'.format(quality)]
        if rate_limit:
            try:
                rate_limit = float(rate_limit)
            except ValueError as e:
                raise ValueError('rate_limit should be a float.')
            self.options.append('--limit-rate {}'.format(str(rate_limit) + 'M'))
        else:
            rate_limit = 1

        # Make timeout to cancel download relative to rate limiting
        self.timeout = 2 * self.EXPECTED_MAX_SIZE / rate_limit
        self.queue = deque()
        self.downloading = None
        self.process = None
        self.yt_dl = 'youtube-dl'
        if sys.platform.startswith('win'):
            self.yt_dl += '.exe'
        self.timer = None
        self.start_time = None

    @handler('youtube_download')
    def download(self, url):
        self.queue.append(url)
        self.fire(process_download(), 'youtube')

    @handler('process_download')
    def _process_download(self):
        if not self.downloading and self.queue:
            if not self.process:
                self.downloading = self.queue.popleft()
                flags = ' '.join(self.options)
                # Still not sure why I have to give a stock Manager() rather than self.
                self.process = Process(self.yt_dl + ' ' + flags + ' ' + self.downloading,
                                       cwd=self.save_dir).register(self.manager)

                self.process.start()
                self.start_time = time.clock()
                if not self.timer:
                    self.timer = Timer(1, poll_process(), persist=True).register(self)

    def _shutdown_process(self):
        self.process.kill()
        self.process = None
        self.timer.stop()
        self.timer.unregister()
        self.timer = None

    @handler('poll_process')
    def _poll_process(self):
        status = self.process.status
        if (time.clock() - self.start_time) > self.timeout:
            self._shutdown_process()
            self.fire(youtube_error('Timeout while downloading {}'.format(self.downloading)), '*')
            self.downloading = None
            self.fire(process_download())
            return
        if status is not None:
            self._shutdown_process()
            if status == 0:
                self.fire(youtube_download_complete(self.downloading), '*')
            else:
                self.fire(youtube_error(self.downloading), '*')
            self.downloading = None
            self.fire(process_download())
