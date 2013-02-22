'''
Pooled PostGIS database backend for Django.

Requires psycopg 2: http://initd.org/projects/psycopg2

Created on Feb 22, 2013

@author: greg
'''
from dbpool.db.backends.postgresql_psycopg2.base import DatabaseWrapper as PooledDatabaseWrapper
from django.contrib.gis.db.backends.postgis.creation import PostGISCreation
from django.contrib.gis.db.backends.postgis.introspection import PostGISIntrospection
from django.contrib.gis.db.backends.postgis.operations import PostGISOperations

class DatabaseWrapper(PooledDatabaseWrapper):
    def __init__(self, *args, **kwargs):
        super(DatabaseWrapper, self).__init__(*args, **kwargs)
        self.creation = PostGISCreation(self)
        self.ops = PostGISOperations(self)
        self.introspection = PostGISIntrospection(self)