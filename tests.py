'''
Simplistic test of pooling code 

Created on Mar 28, 2013

@author: greg
'''
import random
import threading

n_threads = 6
n_fast_tests = 1000
n_slow_tests = 10

def test_slow_connection(execs_remaining):
    print '%s: Test slow %s' % (threading.current_thread().name, n_slow_tests - execs_remaining)
    
    signals.request_started.send(sender=base.BaseHandler)
    
    cursor = connection.cursor()
    cursor.execute("SELECT pg_sleep(1)")
    
    signals.request_finished.send(sender=base.BaseHandler)

def test_fast_connection(execs_remaining):
    print '%s: Test fast %s' % (threading.current_thread().name, n_fast_tests - execs_remaining)
    
    signals.request_started.send(sender=base.BaseHandler)
    
    cursor = connection.cursor()
    cursor.execute("SELECT 1")
    row = cursor.fetchone()
    assert(row[0] == 1)
    
    signals.request_finished.send(sender=base.BaseHandler)

def test_connection():
    l_fast_tests = n_fast_tests
    l_slow_tests = n_slow_tests
    
    while l_fast_tests > 0 or l_slow_tests > 0:
        if random.randint(0, n_fast_tests + n_slow_tests) < n_slow_tests and l_slow_tests > 0:
            test_slow_connection(l_slow_tests)
            l_slow_tests -= 1
        elif l_fast_tests > 0:
            test_fast_connection(l_fast_tests)
            l_fast_tests -= 1


if __name__ == '__main__':
    from django.core import signals
    from django.core.handlers import base
    from django.db import connection

    print ('Running test_connection in %s threads with %s fast / %s slow loops each. ' 
           'Should take about %s seconds.') % (n_threads, n_fast_tests, n_slow_tests, n_slow_tests)

    # Warm up pool
    cursor = connection.cursor()
    cursor.execute("SELECT 1")
    row = cursor.fetchone()
    assert(row[0] == 1)
    connection.close()

    # Take requests in n_threads
    for n in range(n_threads):
        t = threading.Thread(target=test_connection)
        t.start()
