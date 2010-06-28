# |ALPHA| Hub - an authorization server for alpha-ioq3
# See files README and COPYING for copyright and licensing details.

"""
Custom py.test options.

    --database
        connection string to use, default 'sqlite:///'
        other useful values:
            'sqlite:///alphahub.sqlite'
            'mysql://alphahub:alphahub@localhost/alphahub'
            'postgresql://alphahub:alphahub@localhost/alphahub'
    --nodrop
        don't drop all tables after the tests have finished
        (you'll have to manually drop them to run the tests
        again)
"""

def pytest_addoption(parser):
    parser.addoption('--database', dest='database', default='sqlite:///')
    parser.addoption('--nodrop', dest='nodrop', action='store_true',
                     default=False)
