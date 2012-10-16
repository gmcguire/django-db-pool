# -*- coding: utf-8 -*-
from distutils.core import setup
from setuptools import find_packages

setup(
    name='django-db-pool',
    version='0.0.7',
    author=u'Greg McGuire',
    author_email='gregjmcguire+github@gmail.com',
    packages=find_packages(),
    url='https://github.com/gmcguire/django-db-pool',
    license='BSD licence, see LICENSE',
    description='Basic database persistance / connection pooling for Django + ' + \
                'Postgres.',
    long_description=open('README.md').read(),
    classifiers=[
        'Topic :: Database',
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python',
    ],
    zip_safe=False,
    install_requires=[
        "Django>=1.3,<1.4.99",
        "psycopg2>=2.4",
    ],
)
