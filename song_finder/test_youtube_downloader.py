from unittest import TestCase
from .youtube_downloader import YoutubeDownloader, youtube_download
from circuits import Component, handler, Debugger, Timer, Event
import time

__author__ = "Joe Sacher <sacherjj@gmail.com>"


class YoutubeDownloaderCaller(Component):
    channel = 'caller'

    urls = ('https://www.youtube.com/watch?v=9AN04imFDK8',
            'https://www.youtube.com/watch?v=jaxZeisCHv8',
            'https://www.youtube.com/watch?v=jaxZeis____error____CHv8',
            'https://www.youtube.com/watch?v=D8zlUUrFK-M')

    def init(self, rate_limit):
        Debugger().register(self)
        self.ytd = YoutubeDownloader(3, rate_limit)
        self.ytd.register(self)
        self.complete = []

    def started(self, *args, **kwargs):
        for url in self.urls:
            self.fire(youtube_download(url), 'youtube')

    @handler('youtube_download_complete')
    def youtube_complete(self, event, *args, **kwargs):
        self.complete.append(args[0])
        print(args[0])
        if len(self.complete) > 2:
            self.stop()


class TestYoutubeDownloader(TestCase):
    def test_download(self):
        ydc = YoutubeDownloaderCaller(rate_limit=0.1)
        ydc.run()
        # If we return, we have completed test successfully.

