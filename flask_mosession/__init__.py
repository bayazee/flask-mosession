# -*- coding: utf-8 -*-
"""
    flask_mosession
    ~~~~~~~~~~~~~~~~~~

    Alternative for Flask session module that uses MongoDB as main storage

    :copyright: (c) 2013 by Bayazee & Rokooie.
    :license: BSD, see LICENSE for more details.
"""

from bson import Binary
from uuid import uuid4

from flask import current_app
from flask.sessions import SessionInterface, SessionMixin
from pymongo.errors import ConnectionFailure
from werkzeug.datastructures import CallbackDict
from cache_backends import NoCacheBackend


__revision__ = '$Revision: e1a7ef4049fb $'


class MoSession(CallbackDict, SessionMixin):
    """Session Replacement class.

    Instances of this class will replace the session (and thus be available
    through things like :attr:`flask.session`.

    The session class will save data to the store only when necessary, empty
    sessions will not be stored at all."""

    def __init__(self, initial=None):
        def _on_update(d):
            d.modified = True

        CallbackDict.__init__(self, initial, _on_update)

        if initial:
            # Data found in cache or db and usually its not modified
            self.modified = False
        else:
            self.generate_sid()
            self.new = True
            self.modified = True

    def generate_sid(self):
        self['_id'] = Binary(str(uuid4()))
        return self['_id']

    def remove_stored_session(self):
        current_app.extensions['mosession'].collection.remove({'_id': self['_id']})
        current_app.extensions['mosession'].cache.remove(str(self['_id']))

    def destroy(self):
        """Destroys a session completely, by deleting all keys and removing it
        from the internal store immediately.

        This allows removing a session for security reasons, e.g. a login
        stored in a session will cease to exist if the session is destroyed.
        """

        self.remove_stored_session()
        self.clear()
        self.new = True
        self.generate_sid()

    def regenerate(self):
        """Generate a new session id for this session.

        To avoid vulnerabilities through `session fixation attacks
        <http://en.wikipedia.org/wiki/Session_fixation>`_, this function can be
        called after an action like a login has taken place. The session will
        be copied over to a new session id and the old one removed.
        """

        self.remove_stored_session()
        self.new = True
        self.generate_sid()

    @property
    def sid(self):
        """
        Return Current session ID.

        this function help developer to store session id in browser cookie, and use it for next request's

        sid (or Session ID ) is same as mongoid, this peroperty has object of mongodb models and stored as
        :attr:`stored_session`.

        (:class:`MoSession`) class only stored object of session in self whit name :attr:`stored_session`.
        developer only can access to this peroperty with sid.

        sid stored as _id field in class.
        """

        return str(self['_id'])

    def __setattr__(self, *args, **kwargs):
        return SessionMixin.__setattr__(self, *args, **kwargs)


class MoSessionInterface(SessionInterface):
    """
    MoSession interface class, flask session interface is replaced with this.

    MoSession Interface helps developer to overload or change operation functionality of flask central session manager.
    """

    session_class = MoSession

    @property
    def collection(self):
        """
        Returns current app's session manager's mongodb collection.
        """
        return current_app.extensions['mosession'].collection

    def load_session(self, sid):
        stored_session = None
        if sid:
            stored_session = current_app.extensions['mosession'].cache.get(sid)
            if not stored_session:
                stored_session = self.collection.find_one({'_id': Binary(sid)})

                if stored_session:
                    current_app.extensions['mosession'].cache.set(sid, stored_session)

        if stored_session:
            return self.session_class(stored_session)

        return None

    def open_session(self, app, request):
        """
        Gives current app's instance and request, load's or creates session instance of request cycle.

        :param app: Current app's instance (required to load SESSION_COOKIE_NAME field from config)
        :param request: Current request
        :return: (Session)
        """
        s = self.load_session(str(request.cookies.get(app.config['SESSION_COOKIE_NAME'], '')))
        return s or self.session_class()

    def raw_save_session(self, session):
        dict_session = dict(session)
        self.collection.save(dict_session)
        current_app.extensions['mosession'].cache.set(session.sid, dict_session)

    def save_session(self, app, session, response):
        """
        If MoSession object is changed from it's last saved state, this function saves all change in cookie and application's cache.

        operation of function :
        step 1:if modified flag of session is true then function go to step 2 else function do nothing
        step 2:function calculate expire time and session permanent then if new flags of session and expire are true then change
        session expier property to expire time
        step 3:now if new flag of session is true set session sid (session id) and change flag to false.set sid and current cookie
        data in cookies
        step 4:set current session (new created) to current cache
        step 5:set modified flag os session to false

        :param app: Current app's instance (required to load SESSION_COOKIE_NAME field from config)
        :param session: MoSession's instance
        :param response: Responce object
        """
        if session.modified:
            # TODO: remember me ham az in variable estefade khahad kard
            session.permanent = self.get_expire_at_browser_close(app)

            expire = self.get_expiration_time(app, session)

            if session.new and expire:
                session['expire'] = expire

            self.raw_save_session(session)

            if session.new:
                session.new = False
                response.set_cookie(key=app.config['SESSION_COOKIE_NAME'], value=session.sid,
                                    domain=self.get_cookie_domain(app),
                                    expires=expire, httponly=self.get_cookie_httponly(app))

            session.modified = False

    def get_expire_at_browser_close(self, app):
        """
        Returns SESSION_EXPIRE_AT_BROWSER_CLOSE value from app's config.

        :param app: Current app's instance
        """
        return not app.config['SESSION_EXPIRE_AT_BROWSER_CLOSE']


class SessionStorage(object):
    """
    this class gives current application object and create functionality for using MongoDB with pymongo driver

    :param app: Current Application Object
    """
    def __init__(self, host, port, database_name):
        self.host = host
        self.port = port
        self.database_name = database_name

        self.connection = None
        self.database = None
        self.collections = {}

    def __getitem__(self, item):
        """
        Serves database collections as the class items with brackets.

        :param item: Requested collection's name
        """
        if not item in self.collections:
            if not self.database:
                self.connect()

            self.collections[item] = self.database[item]

        return self.collections[item]

    def connect(self):
        """
        Try to connect to mongodb and set self.database to sessions's database reference.

        It will try 5 times to connect to database - with 100ms delay between tries -
        """

        if self.connection:
            return

        from pymongo.connection import Connection
        from pymongo.errors import AutoReconnect

        for _connection_attempts in range(5):
            try:
                self.connection = Connection(self.host, self.port)
                self.database = self.connection[self.database_name]
            except AutoReconnect:
                from time import sleep
                sleep(0.1)
            else:
                break
        else:
            raise ConnectionFailure


class MoSessionExtension(object):
    """
    MoSession extension object.
    """

    def __init__(self, app=None):
        self.app = None
        self.session_class = None
        self.storage = None
        self._collection = None

        if app:
            self.init_app(app)

    def init_app(self, app):
        """
        Register flask-mosession with Flask's app instance.

        :param app: Flask's app instance
        """
        app.config.setdefault('MONGODB_SESSIONS_COLLECTION_NAME', 'sessions')
        app.config.setdefault('SESSION_EXPIRE_AT_BROWSER_CLOSE', True)
        app.config.setdefault('MOSESSION_CACHE_BACKEND', 'NoCacheBackend')

        app.session_interface = MoSessionInterface()
        app.extensions['mosession'] = self

        if self.session_class:
            app.session_interface.session_class = self.session_class

        self.cache = getattr(cache_backends, app.config['MOSESSION_CACHE_BACKEND'])(app)
        self.storage = SessionStorage(
            app.config['MONGODB_HOST'],
            app.config['MONGODB_PORT'],
            app.config['MONGODB_DATABASE']
        )
        self.app = app

    @property
    def collection(self):
        if not self._collection:
            self._collection = self.storage[self.app.config['MONGODB_SESSIONS_COLLECTION_NAME']]

        return self._collection

    def cleanup_sessions(self):
        # TODO: ba dastorate mongodb document haye expire shode bayad hazf beshe
        pass
