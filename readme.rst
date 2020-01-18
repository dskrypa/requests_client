Requests Client
===============

Library that expands upon `Requests <https://requests.readthedocs.io/en/master/>`_ to provide an easy way to build
multiple requests to a given server, without needing to provide the full URL for every request.  This is especially
useful for working with RESTful applications with multiple backends, where a common endpoint is requested from each
backend.

Installation
------------

If installing on Linux, you should run the following first::

    $ sudo apt-get install python3-dev


Regardless of OS, setuptools is required::

    $ pip3 install setuptools


All of the other requirements are handled in setup.py, which will be run when you install like this::

    $ pip3 install git+git://github.com/dskrypa/requests_client
