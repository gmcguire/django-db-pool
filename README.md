Django DB Pool
=============

Another connection pool "solution"?
-----------------------------------

Yes, alas.  Django punts on the problem of pooled / persistant connections[1], generally telling folks to 
use a dedicated application like PGBouncer (for Postgres.)  However that's not always workable on app-centric
platforms like Heroku, where each application runs in isolation.  Thus this package.  There are others[2],
but this one attempts to provide connection persistance / pooling with as few dependencies as possible.

[1] https://groups.google.com/d/topic/django-users/m1jeE4Cxr9A/discussion
[2] https://github.com/jinzo/django-dbpool-backend


Requirements
------------

* [Django 1.3](https://www.djangoproject.com/download/) with [Postgres](http://www.postgresql.org/)


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

See the [code][dbpool/db/backends/postgres_psycopg2/base.py] for more information.

