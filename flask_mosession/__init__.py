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
    """
    Session replacement class.

    The session object will be an instance of this class or it's children.
    By importing flask.session, you will get this class' object.

    The MoSession class will save data only when it's necessary,
    empty sessions will not saved.
    """

    def __init__(self, initial=None):
        def _on_update(d):
            d.modified = True

        CallbackDict.__init__(self, initial, _on_update)

        if initial:
            self.modified = False
        else:
            self.generate_sid()
            self.new = True
            self.modified = True

    def generate_sid(self):
        """
        Generate session id using UUID4 and store it in the object's _id attribute.

        :return: (Binary) Session id
        """
        self['_id'] = Binary(str(uuid4()))
        return self['_id']

    def remove_stored_session(self):
        current_app.extensions['mosession'].storage.collection.remove({'_id': self['_id']})
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
        Return session id.
        Session id is stored in database as it's _id field.

        :return: Session id
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
    def _mosession(self):
        """
        Returns current app's MoSession extension instance.
        """
        return current_app.extensions['mosession']

    def load_session(self, sid):
        """
        Load session from cache or database, If found in database but not in cache, saves it in cache too.

        :param sid: Session ID
        :return: An instance of type session_class with session data or None if session not found
        """
        if not sid:
            return None

        stored_session = self._mosession.cache.get(sid)
        if not stored_session:
            stored_session = self._mosession.storage.collection.find_one({'_id': Binary(sid)})

            if stored_session:
                self._mosession.cache.set(sid, stored_session)

        return self.session_class(stored_session) if stored_session else None

    def open_session(self, app, request):
        """
        Overrides open_session interface.
        Tries to load session, in case of failure creates a new instance of session_class type.

        :param app: Current app's instance (required to load SESSION_COOKIE_NAME field from config)
        :param request: Current request
        :return: Session object
        """
        return self.load_session(str(request.cookies.get(app.config['SESSION_COOKIE_NAME'], ''))) or self.session_class()

    def raw_save_session(self, session):
        """
        Save session in database and also in cache.

        :param session: Session object
        :return:
        """
        dict_session = dict(session)
        self._mosession.storage.collection.save(dict_session)
        self._mosession.cache.set(session.sid, dict_session)

    def save_session(self, app, session, response):
        """
        Overrides save_session interface.
        Save session data if it's modified, it cares about session expiration and other features.

        operation of function :
        step 1:if modified flag of session is true then function go to step 2 else function do nothing
        step 2:function calculate expire time and session permanent then if new flags of session and expire are true then change
        session expire property to expire time
        step 3:now if new flag of session is true set session sid (session id) and change flag to false.set sid and current cookie
        data in cookies
        step 4:set current session (new created) to current cache
        step 5:set modified flag os session to false

        :param app: Current app's instance (required to load SESSION_COOKIE_NAME field from config)
        :param session: Session object
        :param response: Response object
        """
        if not session.modified:
            return

        session.permanent = not app.config['SESSION_EXPIRE_AT_BROWSER_CLOSE']

        expiration = self.get_expiration_time(app, session)

        if session.new and expiration:
            # TODO: Is this line really necessary?
            session['expire'] = expiration

        self.raw_save_session(session)

        if session.new:
            session.new = False
            response.set_cookie(
                key=app.config['SESSION_COOKIE_NAME'],
                value=session.sid,
                domain=self.get_cookie_domain(app),
                expires=expiration, httponly=self.get_cookie_httponly(app)
            )

        session.modified = False


class SessionStorage(object):
    """
    The class role is to serve the storage, So it's a wrapper on pymongo's database class to add auto reconnect.

    :param app: Current Application Object
    """
    def __init__(self, host, port, database_name, collection_name):
        self.host = host
        self.port = port
        self.database_name = database_name
        self.collection_name = collection_name
        self._collection = None

    @property
    def collection(self):
        if not self._collection:
            self.connect()
        return self._collection

    def connect(self):
        """
        Try to connect to mongodb and set self.database to sessions's database reference.

        It will try 5 times to connect to database - with 100ms delay between tries -
        """

        if self._collection:
            return

        from pymongo.connection import Connection
        from pymongo.errors import AutoReconnect

        for _connection_attempts in range(5):
            try:
                self._collection = Connection(self.host, self.port)[self.database_name][self.collection_name]
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
        app.extensions['mosession'] = self

        app.config.setdefault('MONGODB_SESSIONS_COLLECTION_NAME', 'sessions')
        app.config.setdefault('SESSION_EXPIRE_AT_BROWSER_CLOSE', True)
        app.config.setdefault('MOSESSION_CACHE_BACKEND', 'NoCacheBackend')

        self.cache = getattr(cache_backends, app.config['MOSESSION_CACHE_BACKEND'])(app)
        self.storage = SessionStorage(
            app.config['MONGODB_HOST'],
            app.config['MONGODB_PORT'],
            app.config['MONGODB_DATABASE'],
            app.config['MONGODB_SESSIONS_COLLECTION_NAME'],
        )

        app.session_interface = MoSessionInterface()

        if self.session_class:
            app.session_interface.session_class = self.session_class

    def cleanup_sessions(self):
        # TODO: ba dastorate mongodb document haye expire shode bayad hazf beshe
        pass
