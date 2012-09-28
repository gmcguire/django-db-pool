Django DB Pool
=============

Another connection pool "solution"?
-----------------------------------

Yes, alas.  Django punts on the problem of pooled / persistant connections ([1][1]), generally telling folks to use a dedicated application like PGBouncer (for Postgres.)  However that's not always workable on app-centric platforms like Heroku, where each application runs in isolation.  Thus this package.  There are others ([2][2]), but this one attempts to provide connection persistance / pooling with as few dependencies as possible.

Currently only the Django postgres_psycopg2 driver is supported.  Connection pooling is implemented by thinly wrapping a psycopg2 connection object with a pool-aware class.  The actual pool implementation is psycop2g's built-in [ThreadedConnectionPool](http://initd.org/psycopg/docs/pool.html), which handles thread safety for the pool instance, as well as simple dead connection testing when connections are returned. 

Because this implementation sits inside the python interpreter, in a multi-process app server environment the pool will never be larger than one connection.  However, you can still benefit from connection persistance (no connection creation overhead, query plan caching, etc.) so the (minimal) additional overhead of the pool should be outweighed by these benefits. TODO: back this up with some data!


Requirements
------------

* [Django 1.3 or 1.4](https://www.djangoproject.com/download/) with [Postgres](http://www.postgresql.org/)


Installation
------------

    pip install django-db-pool


Usage
-----

Change your `DATABASES` -> `ENGINE` from `'django.db.backends.postgresql_psycopg2'` to 
`'dbpool.db.backends.postgresql_psycopg2'`.

If you are in a multithreaded environment, also set `MAX_CONNS` and optionally `MIN_CONNS` in the `OPTIONS`, 
like this:

    'default': {
        'ENGINE': 'dbpool.db.backends.postgresql_psycopg2',          
        'OPTIONS': {'MAX_CONNS': 1},
        # These options will be used to generate the connection pool instance
        # on first use and should remain unchanged from your previous entries
        'NAME': 'test',
        'USER': 'test',
        'PASSWORD': 'test123',
        'HOST': 'localhost',
        'PORT': '',
    }

See the [code][base] for more information on settings `MAX_CONNS` and `MIN_CONNS`.

Lastly, if you use [South](http://south.aeracode.org/) (and you should!) you'll want to make sure it knows that you're still using Postgres:

    SOUTH_DATABASE_ADAPTERS = {
        'default': 'south.db.postgresql_psycopg2',
    }

[1]: https://groups.google.com/d/topic/django-users/m1jeE4Cxr9A/discussion
[2]: https://github.com/jinzo/django-dbpool-backend
[base]: https://github.com/gmcguire/django-db-pool/blob/master/dbpool/db/backends/postgresql_psycopg2/base.py#L48-61

