"""
Pooled PostgreSQL database backend for Django.

Requires psycopg 2: http://initd.org/projects/psycopg2
"""
from django import get_version as get_django_version
from django.db.backends.postgresql_psycopg2.base import \
    DatabaseWrapper as OriginalDatabaseWrapper
from django.db.backends.signals import connection_created
from threading import Lock
import logging
import sys

try:
    import psycopg2 as Database
    import psycopg2.extensions
except ImportError, e:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("Error loading psycopg2 module: %s" % e)

logger = logging.getLogger(__name__)

class PooledConnection():
    '''
    Thin wrapper around a psycopg2 connection to handle connection pooling.
    '''
    def __init__(self, pool, test_query=None):
        self._pool = pool
        
        # If passed a test query we'll run it to ensure the connection is available
        if test_query:
            self._wrapped_connection = None
            num_attempts = 0
            while self._wrapped_connection is None:
                num_attempts += 1;
                c = pool.getconn()
                try:
                    c.cursor().execute(test_query)
                except Database.Error:
                    pool.putconn(c, close=True)
                    if num_attempts > self._pool.maxconn:
                        logger.error("Unable to check out connection from pool %s" % self._pool)
                        raise;
                    else:
                        logger.info("Closing dead connection from pool %s" % self._pool, 
                                    exc_info=sys.exc_info())
                else:
                    if not c.autocommit:
                        c.rollback()
                    self._wrapped_connection = c
        else:
            self._wrapped_connection = pool.getconn()
        
        logger.debug("Checked out connection %s from pool %s" % (self._wrapped_connection, self._pool))

    def close(self):
        '''
        Override to return the connection to the pool rather than closing it.
        '''
        if self._wrapped_connection and self._pool:
            logger.debug("Returning connection %s to pool %s" % (self._wrapped_connection, self._pool))
            self._pool.putconn(self._wrapped_connection)
            self._wrapped_connection = None

    def __getattr__(self, attr):
        '''
        All other calls proxy through to the "real" connection
        '''
        return getattr(self._wrapped_connection, attr)

'''
This holds our connection pool instances (for each alias in settings.DATABASES that 
uses our PooledDatabaseWrapper.)
'''
connection_pools = {}
connection_pools_lock = Lock()

pool_config_defaults = {
    'MIN_CONNS': None, 
    'MAX_CONNS': 1,
    'TEST_ON_BORROW': False, 
    'TEST_ON_BORROW_QUERY': 'SELECT 1'
}

def _set_up_pool_config(self):
    '''
    Helper to configure pool options during DatabaseWrapper initialization.
    '''
    self._max_conns = self.settings_dict['OPTIONS'].get('MAX_CONNS', pool_config_defaults['MAX_CONNS'])
    self._min_conns = self.settings_dict['OPTIONS'].get('MIN_CONNS', self._max_conns)
                
    self._test_on_borrow = self.settings_dict["OPTIONS"].get('TEST_ON_BORROW', 
                                                             pool_config_defaults['TEST_ON_BORROW'])
    if self._test_on_borrow:
        self._test_on_borrow_query = self.settings_dict["OPTIONS"].get('TEST_ON_BORROW_QUERY', 
                                                                       pool_config_defaults['TEST_ON_BORROW_QUERY'])
    else: 
        self._test_on_borrow_query = None


def _create_connection_pool(self, conn_params):
    '''
    Helper to initialize the connection pool.
    '''
    connection_pools_lock.acquire()
    try:
        # One more read to prevent a read/write race condition (We do this
        # here to avoid the overhead of locking each time we get a connection.)
        if (self.alias not in connection_pools or
            connection_pools[self.alias]['settings'] != self.settings_dict):
            logger.info("Creating connection pool for db alias %s" % self.alias)
            logger.info("  using MIN_CONNS = %s, MAX_CONNS = %s, TEST_ON_BORROW = %s" % (self._min_conns,
                                                                                         self._max_conns,
                                                                                         self._test_on_borrow))

            from psycopg2 import pool
            connection_pools[self.alias] = {
                'pool': pool.ThreadedConnectionPool(self._min_conns, self._max_conns, **conn_params),
                'settings': dict(self.settings_dict),
            }
    finally:
        connection_pools_lock.release()


'''
Simple Postgres pooled connection that uses psycopg2's built-in ThreadedConnectionPool
implementation.  In Django, use this by specifying MAX_CONNS and (optionally) MIN_CONNS 
in the OPTIONS dictionary for the given db entry in settings.DATABASES.  

MAX_CONNS should be equal to the maximum number of threads your app server is configured 
for.  For example, if you are running Gunicorn or Apache/mod_wsgi (in a multiple *process* 
configuration) MAX_CONNS should be set to 1, since you'll have a dedicated python 
interpreter per process/worker.  If you're running Apache/mod_wsgi in a multiple *thread*
configuration set MAX_CONNS to the number of threads you have configured for each process.

By default MIN_CONNS will be set to MAX_CONNS, which prevents connections from being closed.
If your load is spikey and you want to recycle connections, set MIN_CONNS to something lower 
than MAX_CONNS.   I suggest it should be no lower than your 95th percentile concurrency for 
your app server.

If you wish to validate connections on each check out, specify TEST_ON_BORROW (set to True) 
in the OPTIONS dictionary for the given db entry.  You can also provide an optional 
TEST_ON_BORROW_QUERY, which is "SELECT 1" by default.
'''
class DatabaseWrapper16(OriginalDatabaseWrapper):
    '''
    For Django 1.6.x
    
    TODO: See https://github.com/django/django/commit/1893467784deb6cd8a493997e8bac933cc2e4af9
      but more importantly https://github.com/django/django/commit/2ee21d9f0d9eaed0494f3b9cd4b5bc9beffffae5
      
    This code may be no longer needed!    
    '''
    set_up_pool_config = _set_up_pool_config
    create_connection_pool = _create_connection_pool
    
    def __init__(self, *args, **kwargs):
        super(DatabaseWrapper16, self).__init__(*args, **kwargs)
        self.set_up_pool_config()

    def get_new_connection(self, conn_params):
        # Is this the initial use of the global connection_pools dictionary for 
        # this python interpreter? Build a ThreadedConnectionPool instance and 
        # add it to the dictionary if so.
        if self.alias not in connection_pools or connection_pools[self.alias]['settings'] != self.settings_dict:
            for extra in pool_config_defaults.keys():
                if extra in conn_params:
                    del conn_params[extra]

            self.create_connection_pool(conn_params)

        return PooledConnection(connection_pools[self.alias]['pool'], test_query=self._test_on_borrow_query)


class DatabaseWrapper14and15(OriginalDatabaseWrapper):
    '''
    For Django 1.4.x and 1.5.x
    '''
    set_up_pool_config = _set_up_pool_config
    create_connection_pool = _create_connection_pool
    
    def __init__(self, *args, **kwargs):
        super(DatabaseWrapper14and15, self).__init__(*args, **kwargs)
        self.set_up_pool_config()

    def _cursor(self):
        settings_dict = self.settings_dict
        if self.connection is None or connection_pools[self.alias]['settings'] != settings_dict:
            # Is this the initial use of the global connection_pools dictionary for 
            # this python interpreter? Build a ThreadedConnectionPool instance and 
            # add it to the dictionary if so.
            if self.alias not in connection_pools or connection_pools[self.alias]['settings'] != settings_dict:
                if not settings_dict['NAME']:
                    from django.core.exceptions import ImproperlyConfigured
                    raise ImproperlyConfigured(
                        "settings.DATABASES is improperly configured. "
                        "Please supply the NAME value.")
                conn_params = {
                    'database': settings_dict['NAME'],
                }
                conn_params.update(settings_dict['OPTIONS'])
                for extra in ['autocommit'] + pool_config_defaults.keys():
                    if extra in conn_params:
                        del conn_params[extra]
                if settings_dict['USER']:
                    conn_params['user'] = settings_dict['USER']
                if settings_dict['PASSWORD']:
                    conn_params['password'] = force_str(settings_dict['PASSWORD'])
                if settings_dict['HOST']:
                    conn_params['host'] = settings_dict['HOST']
                if settings_dict['PORT']:
                    conn_params['port'] = settings_dict['PORT']

                self.create_connection_pool(conn_params)

            self.connection = PooledConnection(connection_pools[self.alias]['pool'], 
                                               test_query=self._test_on_borrow_query)
            self.connection.set_client_encoding('UTF8')
            tz = 'UTC' if settings.USE_TZ else settings_dict.get('TIME_ZONE')
            if tz:
                try:
                    get_parameter_status = self.connection.get_parameter_status
                except AttributeError:
                    # psycopg2 < 2.0.12 doesn't have get_parameter_status
                    conn_tz = None
                else:
                    conn_tz = get_parameter_status('TimeZone')

                if conn_tz != tz:
                    # Set the time zone in autocommit mode (see #17062)
                    self.connection.set_isolation_level(
                            psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
                    self.connection.cursor().execute(
                            self.ops.set_time_zone_sql(), [tz])
            self.connection.set_isolation_level(self.isolation_level)
            self._get_pg_version()
            connection_created.send(sender=self.__class__, connection=self)
        cursor = self.connection.cursor()
        cursor.tzinfo_factory = utc_tzinfo_factory if settings.USE_TZ else None
        return CursorWrapper(cursor)


class DatabaseWrapper13(OriginalDatabaseWrapper):
    '''
    For Django 1.3.x
    '''
    set_up_pool_config = _set_up_pool_config
    create_connection_pool = _create_connection_pool
    
    def __init__(self, *args, **kwargs):
        super(DatabaseWrapper13, self).__init__(*args, **kwargs)
        self.set_up_pool_config()

    def _cursor(self):
        '''
        Override _cursor to plug in our connection pool code.  We'll return a wrapped Connection
        which can handle returning itself to the pool when its .close() method is called.
        '''
        from django.db.backends.postgresql.version import get_version

        new_connection = False
        set_tz = False
        settings_dict = self.settings_dict

        if self.connection is None or connection_pools[self.alias]['settings'] != settings_dict:
            new_connection = True
            set_tz = settings_dict.get('TIME_ZONE')

            # Is this the initial use of the global connection_pools dictionary for 
            # this python interpreter? Build a ThreadedConnectionPool instance and 
            # add it to the dictionary if so.
            if self.alias not in connection_pools or connection_pools[self.alias]['settings'] != settings_dict:
                if settings_dict['NAME'] == '':
                    from django.core.exceptions import ImproperlyConfigured
                    raise ImproperlyConfigured("You need to specify NAME in your Django settings file.")
                conn_params = {
                    'database': settings_dict['NAME'],
                }
                conn_params.update(settings_dict['OPTIONS'])
                for extra in ['autocommit'] + pool_config_defaults.keys():
                    if extra in conn_params:
                        del conn_params[extra]
                if settings_dict['USER']:
                    conn_params['user'] = settings_dict['USER']
                if settings_dict['PASSWORD']:
                    conn_params['password'] = settings_dict['PASSWORD']
                if settings_dict['HOST']:
                    conn_params['host'] = settings_dict['HOST']
                if settings_dict['PORT']:
                    conn_params['port'] = settings_dict['PORT']

                self.create_connection_pool(conn_params)

            self.connection = PooledConnection(connection_pools[self.alias]['pool'], 
                                               test_query=self._test_on_borrow_query)
            self.connection.set_client_encoding('UTF8')
            self.connection.set_isolation_level(self.isolation_level)
            # We'll continue to emulate the old signal frequency in case any code depends upon it
            connection_created.send(sender=self.__class__, connection=self)
        cursor = self.connection.cursor()
        cursor.tzinfo_factory = None
        if new_connection:
            if set_tz:
                cursor.execute("SET TIME ZONE %s", [settings_dict['TIME_ZONE']])
            if not hasattr(self, '_version'):
                self.__class__._version = get_version(cursor)
            if self._version[0:2] < (8, 0):
                # No savepoint support for earlier version of PostgreSQL.
                self.features.uses_savepoints = False
            if self.features.uses_autocommit:
                if self._version[0:2] < (8, 2):
                    # FIXME: Needs extra code to do reliable model insert
                    # handling, so we forbid it for now.
                    from django.core.exceptions import ImproperlyConfigured
                    raise ImproperlyConfigured("You cannot use autocommit=True with PostgreSQL prior to 8.2 at the moment.")
                else:
                    # FIXME: Eventually we're enable this by default for
                    # versions that support it, but, right now, that's hard to
                    # do without breaking other things (#10509).
                    self.features.can_return_id_from_insert = True
        return CursorWrapper(cursor)

'''
Choose a version of the DatabaseWrapper class to use based on the Django
version.  This is a bit hacky, what's a more elegant way?
'''
django_version = get_django_version()
if django_version.startswith('1.3'):
    from django.db.backends.postgresql_psycopg2.base import CursorWrapper
    
    class DatabaseWrapper(DatabaseWrapper13):
        pass
elif django_version.startswith('1.4') or django_version.startswith('1.5'):
    from django.conf import settings
    from django.db.backends.postgresql_psycopg2.base import utc_tzinfo_factory, \
        CursorWrapper

    # The force_str call around the password seems to be the only change from 
    # 1.4 to 1.5, so we'll use the same DatabaseWrapper class and make 
    # force_str a no-op.
    try: 
        from django.utils.encoding import force_str
    except ImportError:
        force_str = lambda x: x

    class DatabaseWrapper(DatabaseWrapper14and15):
        pass
elif django_version.startswith('1.6'):
    class DatabaseWrapper(DatabaseWrapper16):
        pass
else:
    raise ImportError("Unsupported Django version %s" % django_version)
