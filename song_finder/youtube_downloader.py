from circuits import Component, Timer, Event, handler, Worker
from collections import deque
import sys
import os
import inspect
import subprocess

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


class YoutubeDownloader(Component):
    channel = 'youtube'
    EXPECTED_MAX_SIZE = 30

    def init(self, quality=3, rate_limit=None):
        script_dir = get_script_dir()
        save_dir = os.path.join(script_dir, 'songs')
        if not os.path.exists(save_dir):
            os.mkdir(save_dir)
        print('Script Dir: {}'.format(script_dir))
        print('Saving to: {}'.format(save_dir))
        os.chdir(save_dir)

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
        self.timeout = 2 # 2 * self.EXPECTED_MAX_SIZE / rate_limit
        self.queue = deque()
        self.downloading = None
        self.process = None

    @handler('youtube_download')
    def download(self, url):
        self.queue.append(url)
        self.fire(process_download(), 'youtube')

    @handler('process_download')
    def _process_download(self):
        suffix = ''
        if sys.platform.startswith('win'):
            suffix = '.exe'

        if not self.downloading and self.queue:
            self.downloading = self.queue.popleft()
            command = "youtube-dl{} {} {}".format(suffix, ' '.join(self.options), self.downloading)
            process = subprocess.Popen(command.split(),
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            error = stderr.decode('UTF-8')
            out = stdout.decode('UTF-8')
            if error:
                self.fire(youtube_error(error))
            self.fire(youtube_download_complete(self.downloading), '*')
            self.downloading = None
            self.fire(process_download(), 'youtube')
