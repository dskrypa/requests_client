Requests Client
===============

Library that expands upon `Requests <https://requests.readthedocs.io/en/master/>`_ to provide an easy way to build
multiple requests to a given server, without needing to provide the full URL for every request.  This is especially
useful for working with RESTful applications with multiple backends, where a common endpoint is requested from each
backend.

Documentation can be found here: https://dskrypa.github.io/requests_client/


Installation
------------

To add requests_client as a dependency, add the following to requirements.txt or ``install_requires`` in ``setup.py``::

    requests_client@ git+git://github.com/dskrypa/requests_client


To install it directly, use the following::

    $ pip install git+git://github.com/dskrypa/requests_client

