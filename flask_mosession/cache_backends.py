

class BaseBackend(object):
    def __init__(self, app):
        pass

    def get(self, key):
        raise NotImplementedError

    def set(self, key, value):
        raise NotImplementedError

    def remove(self, key):
        raise NotImplementedError


class CacheinBackend(BaseBackend):
    def __init__(self, app):
        app.config.setdefault('MOSESSION_CACHE_PREFIX', 'mos')
        self.cache = app.extensions['cache'].create_cache(app.config['MOSESSION_CACHE_PREFIX'])

    def get(self, key):
        return self.cache.get(key)

    def set(self, key, value):
        self.cache.set(key, value)

    def remove(self, key):
        self.cache.delete(key)


class NoCacheBackend(BaseBackend):
    def get(self, key):
        return None

    def set(self, key, value):
        pass

    def remove(self, key):
        pass
