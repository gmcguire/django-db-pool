"""
Pooled PostgreSQL database backend for Django.

Requires psycopg 2: http://initd.org/projects/psycopg2
"""
from django.db.backends.postgresql.version import get_version
from django.db.backends.postgresql_psycopg2.base import CursorWrapper, \
    DatabaseWrapper as OriginalDatabaseWrapper
from django.db.backends.signals import connection_created
from threading import Lock


class PooledConnection():
    '''
    Thin wrapper around a psycopg2 connection to handle connection pooling.
    '''
    def __init__(self, pool):
        self._pool = pool
        self._wrapped_connection = pool.getconn()

    def close(self):
        '''
        Override to return the connection to the pool rather than closing it.
        '''
        if self._wrapped_connection and self._pool:
            self._pool.putconn(self._wrapped_connection)
            self._wrapped_connection = None

    def __getattr__(self, attr):
        '''
        All other calls proxy through to the "real" connection
        '''
        return self._wrapped_connection.__getattribute__(attr)

'''
This holds our connection pool instances (for each alias in settings.DATABASES that 
uses our PooledDatabaseWrapper.)
'''
connection_pools = {}
connection_pools_lock = Lock()

class DatabaseWrapper(OriginalDatabaseWrapper):
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
    '''
    def _cursor(self):
        '''
        Override _cursor to plug in our connection pool code.  We'll return a wrapped Connection
        which can handle returning itself to the pool when its .close() method is called.
        '''
        new_connection = False
        set_tz = False
        settings_dict = self.settings_dict
        
        if self.connection is None:
            new_connection = True
            set_tz = settings_dict.get('TIME_ZONE')
            
            # Is this the initial use of the global connection_pools dictionary for 
            # this python interpreter? Build a ThreadedConnectionPool instance and 
            # add it to the dictionary if so.
            global connection_pools
            if self.alias not in connection_pools:
                if settings_dict['NAME'] == '':
                    from django.core.exceptions import ImproperlyConfigured
                    raise ImproperlyConfigured("You need to specify NAME in your Django settings file.")
                conn_params = {
                    'database': settings_dict['NAME'],
                }
                max_conns = settings_dict['OPTIONS'].pop('MAX_CONNS', 1)
                min_conns = settings_dict['OPTIONS'].pop('MIN_CONNS', max_conns)
                conn_params.update(settings_dict['OPTIONS'])
                if 'autocommit' in conn_params:
                    del conn_params['autocommit']
                if settings_dict['USER']:
                    conn_params['user'] = settings_dict['USER']
                if settings_dict['PASSWORD']:
                    conn_params['password'] = settings_dict['PASSWORD']
                if settings_dict['HOST']:
                    conn_params['host'] = settings_dict['HOST']
                if settings_dict['PORT']:
                    conn_params['port'] = settings_dict['PORT']
                
                connection_pools_lock.acquire()
                try:
                    from psycopg2 import pool
                    connection_pools[self.alias] = pool.ThreadedConnectionPool(min_conns, max_conns, **conn_params)
                finally:
                    connection_pools_lock.release()
 
            self.connection = PooledConnection(connection_pools[self.alias])
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
