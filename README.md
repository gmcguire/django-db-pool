Django DB Pool
=============

**Note that this code has not been rigorously tested in high-volume production systems!  You should perform your own
load / concurrency tests prior to any deployment.  And of course, patches are highly appreciated.**

Another connection pool "solution"?
-----------------------------------

Yes, alas.  Django punts on the problem of pooled / persistant connections ([1][1]), generally telling folks to use a 
dedicated application like PGBouncer (for Postgres.)  However that's not always workable on app-centric platforms like 
Heroku, where each application runs in isolation.  Thus this package.  There are others ([2][2]), but this one attempts 
to provide connection persistance / pooling with as few dependencies as possible.

Currently only the Django's postgres_psycopg2 / postgis drivers are supported.  Connection pooling is implemented by 
thinly wrapping a psycopg2 connection object with a pool-aware class.  The actual pool implementation is psycop2g's 
built-in [ThreadedConnectionPool](http://initd.org/psycopg/docs/pool.html), which handles thread safety for the pool 
instance, as well as simple dead connection testing when connections are returned. 

Because this implementation sits inside the python interpreter, in a multi-process app server environment the pool will 
never be larger than one connection.  However, you can still benefit from connection persistance (no connection creation 
overhead, query plan caching, etc.) so the (minimal) additional overhead of the pool should be outweighed by these 
benefits. TODO: back this up with some data!


Requirements
------------

* [Django 1.3 - 1.5](https://www.djangoproject.com/download/)
* [PostgreSQL](http://www.postgresql.org/) or [PostGIS](http://postgis.net/) for your database


Installation
------------

    pip install django-db-pool


Usage
-----

* PostgreSQL
   * Change your `DATABASES` -> `ENGINE` from `'django.db.backends.postgresql_psycopg2'` to `'dbpool.db.backends.postgresql_psycopg2'`.
* PostGIS
   * Change your `DATABASES` -> `ENGINE` from `'django.contrib.gis.db.backends.postgis'` to `'dbpool.db.backends.postgis'`.

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

You can set `TEST_ON_BORROW` (also in the `OPTIONS`) to True if you would like a connection to be validated each time it is
checked out.  If you enable this, any connection that fails a test query will be discarded from the pool and a new connection 
fetched, retrying up to the largest size of the pool.  Since this incurs some overhead you should weigh it against the 
benefit of transparently recovering from database connection failures.

Lastly, if you use [South](http://south.aeracode.org/) (and you should!) you'll want to make sure it knows that you're still 
using Postgres:

    SOUTH_DATABASE_ADAPTERS = {
        'default': 'south.db.postgresql_psycopg2',
    }

[1]: https://groups.google.com/d/topic/django-users/m1jeE4Cxr9A/discussion
[2]: https://github.com/jinzo/django-dbpool-backend
[base]: https://github.com/gmcguire/django-db-pool/blob/0.0.8/dbpool/db/backends/postgresql_psycopg2/base.py#L47-60

