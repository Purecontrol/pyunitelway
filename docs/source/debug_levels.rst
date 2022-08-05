Request debug levels
====================

There are multiple debug levels to see requests and response. The three values for ``debug`` parameter are:

* 0: No debug
* 1: Print sent request and received response
* 2: Print all received bytes

By default, the debug mode is set to 0 in all functions.

Example with ``read_internal_bit(0)``
-------------------------------------

If debug is set to 1, it will print the sent request information, its bytes, and the response bytes.

.. NOTE::

    All the UNI-TELWAY bytes are printed.

::

    ------------------ READ_INTERNAL_BIT at %M0 ----------------
    [1659693849.478014] Sending: 10 02 02 0a 20 00 fe 00 00 00 00 07 00 00 43
    [1659693849.542139] Received: 10 02 02 09 20 00 fe 00 00 00 30 00 00 6b

If debug is set to 2, it will also print all the bytes received from the PLC between the sending and the reception.

::

    ------------------ READ_INTERNAL_BIT at %M0 ----------------
    [1659693909.7501009] Sending: 10 02 02 0a 20 00 fe 00 00 00 00 07 00 00 43
    recv => 05 01
    recv => f0 10 05
    recv => 02
    recv => 10 02 02
    [1659693909.8064196] Received: 10 02 02 09 20 00 fe 00 00 00 30 00 00 6b
