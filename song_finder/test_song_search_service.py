from unittest import TestCase
from circuits import Component, Debugger, Timer, Event
import time
from .song_search_service import SongSearchService, SearchLink, ResultLinks, accept_song, reject_song, SongWebQuery

__author__ = "Joe Sacher <sacherjj@gmail.com>"


data_structure = {'link_1': ['artist_1', 'song_1', 'youtube_1', ['link_2', 'link_3', 'link_4']],
                  'link_2': ['artist_2', 'song_2', 'youtube_2', ['link_4', 'link_5', 'link_6']],
                  'link_3': ['artist_3', 'song_3', None, ['link_2', 'link_3']],
                  'link_4': ['artist_4', 'song_4', 'youtube_4', ['link_7']],
                  'link_5': ['artist_5', 'song_5', 'youtube_5', []],
                  'link_6': ['artist_6', 'song_6', 'youtube_6', []],
                  'link_7': ['artist_7', 'song_7', 'youtube_7', []]}


class TestWebQuery(SongWebQuery):
    @staticmethod
    def get_initial_url(search_string):
        if search_string == 'find_me':
            values = data_structure['link_1']
            return SearchLink(values[0], values[1], 'link_1')
        return None

    @staticmethod
    def get_youtube_and_related_links(search_link):
        print('get_youtube_and_links {}'.format(search_link))
        values = data_structure[search_link.url]
        related_links = []
        for link in values[3]:
            ref = data_structure[link]
            related_links.append(SearchLink(ref[0], ref[1], link))
        # Simulate Slow Web Result
        time.sleep(0.5)
        results = ResultLinks(search_link, values[2], related_links)
        print('returning from async {}'.format(results))
        return results


class TestRunner(Component):
    def init(self, search_string, accept_reject_map):
        self.accept_reject_map = accept_reject_map
        Debugger().register(self)
        self.song_search = SongSearchService(search_string, TestWebQuery).register(self)
        Timer(1, Event.create("foo"), persist=True).register(self)

    def foo(self):
        print('foo')

    def song_found(self, event, search_link):
        print('Song Found {}'.format(search_link))
        if self.accept_reject_map[search_link.url]:
            self.fire(accept_song(search_link), 'search_service')
        else:
            self.fire(reject_song(search_link), 'search_service')

    def youtube_link_for_download(self, event, url):
        print('Youtube download: {}'.format(url))

    def search_exhausted(self, event):
        print('Search Exhausted')
        self.stop()


class TestSongSearchService(TestCase):
    def test_empty_initial_result(self):
        tr = TestRunner('will not find me', {})
        tr.run()
        tr = None

    def test_always_accept_search_1(self):
        map = {'link_1': True,
               'link_2': True,
               'link_3': True,
               'link_4': True,
               'link_5': True,
               'link_6': True,
               'link_7': True}
        tr = TestRunner('find_me', map)
        tr.run()
        tr = None
