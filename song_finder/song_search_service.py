from functools import wraps
from collections import namedtuple, deque, OrderedDict
from circuits import Component, handler, Event, Worker, task
import requests

SearchLink = namedtuple('SearchLink', 'artist song url')
ResultLinks = namedtuple('ResultLinks', 'search_link youtube_url related_links')


class make_async(object):
    """Decorator for an event handler, pushes this event execution into a worker pool"""
    def __init__(self, *args, **kwargs):
        self.pool = kwargs.get("pool", "worker")
        if len(args) > 0:
            raise Exception("Usage: @async() or @async(pool=<worker_channel_name>)")

    def __call__(self, func):
        """Called at decoration time, with function"""
        @wraps(func)
        def decorated(itself, event, *args, **kwargs):
            evt = task(func, itself, event, *args, **kwargs)
            ret = yield itself.call(evt, self.pool)
            result = ret.value
            if isinstance(result, Exception):
                raise result
            yield result
        return decorated


class SongWebQuery(object):

    @staticmethod
    def get_initial_url(search_text):
        raise NotImplementedError

    @staticmethod
    def get_youtube_and_result_links(search_link):
        raise NotImplementedError


class TuneFMQuery(SongWebQuery):

    @staticmethod
    def get_initial_url(search_text):
        raise NotImplementedError

    @staticmethod
    def get_youtube_and_result_links(search_link):
        raise NotImplementedError


class song_found(Event):
    """
    Fired when a valid song is found.

    Sent with SearchLink object.
    """


class search_exhausted(Event):
    """
    Fired when no new songs are available for search tree.
    """


class youtube_link_for_download(Event):
    """
    Fired when a youtube song link is loaded.

    Argument is url
    """


class reject_song(Event):
    """
    Fired when user rejects song.  Use search_link as argument.
    """


class accept_song(Event):
    """
    Fired when user accepts song.  Use search_link as argument.
    """


class start_async_download(Event):
    """
    Retrieve Youtube link and related links in a manner that doesn't block due to web IO delay.

    Use search_link as argument.
    """


def download_web_page(url):
    response = requests.get(url)
    return response.text


class SongRelatedData(object):
    def __init__(self, search_link, send_youtube=False):
        self._state = None
        self.related_links = []
        self.youtube_url = None
        self._search_link = search_link
        self.send_youtube = send_youtube

    @property
    def is_uninitialized(self):
        return self._state is None

    @property
    def is_downloading(self):
        return self._state == 'downloading'

    @property
    def is_complete(self):
        return self._state == 'complete'

    def set_downloading(self):
        if self._state is not None:
            raise ValueError('Can only set is_downloading for unused object.  (._state = None)')
        self._state = 'downloading'

    def set_received_data(self, result_links):
        if result_links.search_link != self._search_link:
            raise ValueError('result_links data has different search_link information.')
        self._state = 'complete'
        self.youtube_url = result_links.youtube_url
        self.related_links = result_links.related_links


class SongSearchService(Component):

    channel = 'search_service'
    PRE_SEND_COUNT = 5

    def init(self, search_string, song_web_query_object):
        Worker(process=False).register(self)
        self.search_string = search_string
        self.query_object = song_web_query_object
        # Links to the specific page of song search service that have been used
        # (Added to initial list, added to list due to low count, or accept/rejected by user.)
        # This keeps from asking about previously processed links.
        self.used_links = set()
        # Links from a given search_link.  This is in an OrderedDict, as we may have to pull
        # prior to the user accept or rejecting it, due to running out of links.
        self.future_links = OrderedDict()
        # If youtube search is in progress, this caches calls to allow youtube so send when complete
        self.youtube_wait = []
        # Initial search link.  Do we need to save this?
        start_link = self.query_object.get_initial_url(search_string)
        if not start_link:
            self.fire(search_exhausted(), '*')
            return
        self._initialize_data(start_link)
        self.fire(song_found(start_link), '*')

    def _initialize_data(self, start_link):
        self.future_links[start_link] = SongRelatedData(start_link)
        self._call_async_downloader(start_link)

    def _call_async_downloader(self, search_link, download=False):
        ref = self.future_links[search_link]
        if download:
            ref.send_youtube = True
            if ref.is_complete:
                self._fire_youtube(search_link)
                return
            elif ref.is_downloading:
                return
        ref.set_downloading()

        self.fire(task(self.query_object.get_youtube_and_related_links, search_link), '*')
        # If our cache is less than PRE_SEND_COUNT, we need to build these up.
        count_left = self.PRE_SEND_COUNT - self._cached_count
        if count_left > 0:
            available = [key for key in self.future_links.keys() if self.future_links[key].is_uninitialized]
            number_to_fire = min(len(available), count_left)
            if number_to_fire:
                self._call_async_downloader(available[0])

    def _fire_youtube(self, search_link):
        ref = self.future_links[search_link]
        for related_link in ref.related_links:
            if related_link not in self.used_links:
                if related_link not in self.future_links:
                    self.future_links[related_link] = SongRelatedData(related_link)
        self.fire(youtube_link_for_download(ref.youtube_url), '*')
        self._use_link(search_link)

    @property
    def _cached_count(self):
        return len(self.future_links.values()) - len([value for value in self.future_links.values() if value is None])

    @handler('task_success')
    def _task_complete(self, function_called, results, *args, **kwargs):
        func, search_link = function_called
        print('_task_complete {} : {}'.format(search_link, results))
        ref = self.future_links[search_link]
        ref.set_received_data(results)
        for related_link in ref.related_links:
            if related_link not in self.used_links and related_link not in self.future_links:
                self.future_links[related_link] = SongRelatedData(related_link)
                self.fire(song_found(related_link), '*')
        if ref.send_youtube:
            self._fire_youtube(search_link)

    @handler('take_failure')
    def _task_error(self, *args, **kwargs):
        print('task error {} {}'.format(args, kwargs))

    def _use_link(self, search_link):
        """
        Add link to used, remove from future and check if we are out of songs.
        """
        self.used_links.add(search_link)
        del self.future_links[search_link]
        if len(self.future_links) == 0:
            self.fire(search_exhausted(), '*')

    @handler('accept_song')
    def _accept_song(self, event, search_link):
        """
        Handles event when user accepts a suggested song.

        If Youtube link is available, fire immediately.
        Otherwise add to youtube links to supply.

        :param search_link: accepted SearchLink object.
        :return: None
        """
        self._call_async_downloader(search_link, True)

    @handler('reject_song')
    def _reject_song(self, event, search_link):
        """
        Handles event when user accepts a suggested song.

        Clean out all precached data for link and don't apply future links from this.

        :param search_link: SearchLink object of rejected song
        :return: None
        """
        self._use_link(search_link)

