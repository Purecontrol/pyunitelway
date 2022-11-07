"""Utilities functions module.
"""

import time

from .constants import *

def wait_ms(delay):
    """Wait during ``delay`` milliseconds.
    
    :param int delay: Delay in ms
    """
    start = time.time()
    now = start
    while now - start < delay / 1000:
        now = time.time()

def format_bytearray(ba):
    """Format ``bytearray`` bytes in hexadecimal.
    
    Bytes are space-separated.
    
    :param bytearray ba: Bytes to format
    :returns: Bytes as string
    :rtype: str
    """
    hex_s = ba.hex()

    result = ""
    for i, c in enumerate(hex_s):
        result += c

        if i % 2 == 1 and i < len(hex_s) - 1:
            result += ' '

    return result

def format_hex_list(list):
    """Format a list of bytes in hexadecimal.
    
    Bytes are space-separated.
    
    :param list[int] list: List of bytes
    :returns: Bytes as string
    :rtype: str
    """
    return format_bytearray(bytearray(list))

def print_hex_list(list):
    """Print a list of bytes in hexadecimal.

    Bytes are space-separated.

    :param list[int] list: List of bytes
    """
    print(format_hex_list(list))

def get_response_code(query_code):
    """Return the UNI-TE response code that corresponds to a request code.
    
    | For reading and IO writing requests: response code = ``request code + 0x30``.
    | For other writing requests: response code = ``0xFE``.

    :param int query_code: Request code of which we want the response code

    :returns: The corresponding response code
    :rtype: int
    """
    if query_code in RESPONSE_CODES.keys():
        return RESPONSE_CODES[query_code]

    return query_code + 0x30

def is_valid_response_code(query_code, resp_code):
    """Check if a UNI-TE response code is valid.

    A code is valid if it's ``0xFD`` (request failed), ``request code + 0x30`` or ``0xFE``.
    Other response codes can be received because of conflicts (e.g. receive response for another request).

    :param int query_code: Request code
    :param int resp_code: Received response code

    :returns: True if the code is valid
    :rtype: bool
    """
    return resp_code == 0xFD or resp_code == get_response_code(query_code)

def sublist_in_list(list, sublist):
    """Check if a list is a sub-sequence of a list.
    
    Returns a ``tuple`` with a ``bool`` and an ``int`` : the ``bool`` is ``True`` if all the elements of sublist are in list, in the same order;
    and the ``int`` is the index of the first element in the sub-list (``-1`` if not found)
    
    :param list list: List where to check
    :param list sublist: Sub-list to search

    :returns: Tuple containing the boolean result and the index
    :rtype: (bool, int)
    """
    i = 0
    while i < len(list):
        ie = list[i]
        if ie == sublist[0]:
            j = i
            sub_i = 0
            while j < len(list) and sub_i < len(sublist):

                if list[j] != sublist[sub_i]:
                    i = j
                    break
                j += 1
                sub_i += 1

            if sub_i >= len(sublist):
                return True, i

        i += 1

    return False, -1

def split_list_n(list, n):
    """Split a list each ``n`` elements.

    :param list list: List to split
    :param int n: Number of elements in each sub-sequence

    :returns: Splitted list
    :rtype: list[list]
    """
    splitted = []
    word = []
    for i, b in enumerate(list):
        if i % n == 0:
            if len(word) > 0:
                splitted.append(word)
            word = []

        word.append(b)
        if i == len(list) - 1:
            splitted.append(word)

    return splitted

def compute_response_length(unitelway):
    """Compute a UNI-TELWAY response message length, skipping duplicated ``<DLE>`` characters.

    ``<DLE>`` bytes (``0x10``) are duplicated if:

    * the message length (4th byte) equals ``<DLE>``
    * or ``<DLE>`` is contained in the data section.

    The length is calculated before duplicating ``<DLE>``'s.
    
    :param list[int] unitelway: UNI-TELWAY bytes
    :returns: Length of the UNI-TELWAY response, without duplicated ``<DLE>``'s
    :rtype: int
    """
    i = 3
    
    length = unitelway[i]
    len_count = 0

    i += 1
    len_count += 1
    while len_count <= length:
        if unitelway[i] == DLE & unitelway[i+1] == DLE:
            len_count -= 1
   
        len_count += 1
        i += 1

    
    return i + 1

def duplicate_dle(unitelway, start_index):
    """Duplicate ``<DLE>``'s in a UNI-TELWAY request, before sending it.

    This function modifies directly the input message.

    ``<DLE>`` bytes (``0x10``) are duplicated if:

    * the message length (4th byte) equals ``<DLE>``
    * or ``<DLE>`` is contained in the data section.

    The length is calculated before duplicating ``<DLE>``'s.

    The ``start_index`` is the first data byte index. It's useful when the length equals ``<DLE>``, because all the message is shifted.

    :param list[int] unitelway: UNI-TELWAY bytes
    :param int start_index: First data byte index
    """
    i = start_index
    while i < len(unitelway):
        c = unitelway[i]
        if c == DLE:
            unitelway.insert(i, c)
            i += 1 # skip the duplicated DLE

        i += 1

def delete_dle(unitelway):
    """Delete duplicated ``<DLE>`` characters in a UNI-TELWAY response.

    :param list[int] unitelway: UNI-TELWAY bytes

    :returns: New UNI-TELWAY message without duplicated ``<DLE>``'s
    :rtype: list[int]    
    """
    result = unitelway[:3]

    i = 3
    while i < len(unitelway):
        b = unitelway[i]
        if b != DLE:
            result.append(b)
        else:
            # Insert second DLE
            try:
                result.append(unitelway[i + 1])
            except:
                pass

            i += 1 # skip duplicated DLE

        i += 1

    return result

def compute_bcc(unitelway_bytes):
    """Compute a UNI-TELWAY message checksum.

    The checksum is the sum of all bytes modulo 256. It's computed after ``<DLE>``'s duplication.
    
    :param list[int] unitelway_bytes: UNI-TELWAY message
    
    :returns: Sum of all bytes modulo 256
    :rtype: int
    """
    return sum(unitelway_bytes) % 256

def check_unitelway(response):
    """Check if a received UNI-TELWAY message is valid using its checksum.
    
    This function computes the checksum, and checks if it equals the received message checksum.

    :param list[int] response: UNI-TELWAY message to check

    :returns: ``True`` if the checksum is good. ``False`` otherwise
    :rtype: bool
    """
    bcc = compute_bcc(response[:-1])
    return bcc == response[-1]