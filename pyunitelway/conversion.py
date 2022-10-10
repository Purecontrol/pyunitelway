"""Conversion and response parsing functions.
"""

from .constants import *
from .errors import BadUnitelwayChecksum, RefusedUnitelwayMessage, UnexpectedObjectTypeResponse, UniteRequestFailed
from .utils import check_unitelway, compute_bcc, compute_response_length, delete_dle, split_list_n

def keep_response_bytes(response):
    """Only keep UNI-TELWAY response bytes.

    When we receive a response, we get a lots of bytes, starting with the UNI-TELWAY response. This function only keeps
    the response bytes.
    
    :param list[int] response: Received response

    :returns: UNI-TELWAY bytes
    :rtype: list[int]
    """
    length = compute_response_length(response)
    return response[:length]

def unwrap_unitelway_response(response):
    """Delete the duplicated ``<DLE>``'s in a UNI-TELWAY response.

    See ``utils.delete_dle`` for ``<DLE>`` duplication rules.

    :param list[int] response: UNI-TELWAY response
    
    :returns: UNI-TELWAY response without duplicated ``<DLE>``'s
    :rtype: list[int]
    """
    without_dle = delete_dle(response)

    length = without_dle[3]
    return without_dle[:4 + length + 1]

def unitelway_to_xway(response):
    """Unwrap the X-WAY message from a UNI-TELWAY response.

    This function just returns the X-WAY bytes, without checking anything.

    :param list[int] response: UNI-TELWAY response

    :returns: X-WAY message
    :rtype: list[int]
    """
    return response[4:-1]

def xway_to_unite(response):
    """Unwrap the UNI-TE message from a X-WAY message.

    This function also checks if the X-WAY message has been received.

    The X-WAY message is received if the type code (first response byte)
    is not ``0x22``, which means a refused UNI-TELWAY message.

    :param list[int] response: X-WAY response

    :returns: UNI-TE message
    :rtype: list[int]

    :raises RefusedUnitelwayMessage: The X-WAY type code (first byte) is ``0x22``. It means a refused UNI-TELWAY message
    """
    # Type code = 0x22 => X-WAY refused
    if response[0] == 0x22:
        raise RefusedUnitelwayMessage()

    return response[6:]

def unwrap_unite_response(response):
    """Unwrap the UNI-TE response from a received response.

    This function uses all the functions defined above, so don't use them alone.
    It:

    * only keeps UNI-TELWAY message bytes
    * checks the message using the checksum
    * unwrap the X-WAY message
    * unwrap the UNI-TE message
    * check the UNI-TE response code
    * only returns UNI-TE bytes

    :param list[int] response: Received response
    
    :returns: UNI-TE bytes
    :rtype: list[int]

    :raises BadUnitelwayChecksum, UniteRequestFailed: Bad checksum, or received ``0xFD`` (which means UNI-TE request fail)
    :raises UniteRequestFailed: Received ``0xFD`` (which means UNI-TE request fail)
    """
    response = keep_response_bytes(response)
    if not check_unitelway(response):
        raise BadUnitelwayChecksum(response[-1], compute_bcc(response[:-1]))

    unitelway_bytes = unwrap_unitelway_response(response)
    xway_bytes = unitelway_to_xway(unitelway_bytes)

    unite_bytes = xway_to_unite(xway_bytes)

    code = unite_bytes[0]
    # Fail
    if code == 0xFD:
        raise UniteRequestFailed()

    return unite_bytes

def parse_mirror_result(received_data, sent_data):
    """Parse the ``MIRROR`` response.

    During a ``MIRROR``, the sender send an amount of bytes (``sent_data``), and the receiver must send the same bytes (``received_data``).
    This function check if the sent and the received data are the same.

    :param list[int] received_data: Received data in the response
    :param list[int] sent_data: Sent data during the request

    :returns: ``True`` if the sent and received data are the same
    :rtype: bool
    """
    return received_data == sent_data

def _parse_read_bit_bytes(address, values_bits, has_forcing=False, forcing_bits=None):
    """Parse ``READ_XXX_BIT`` response bytes.
    
    At most 2 bytes are received:

    * 8 values bits
    * 8 forcing bits
    
    Note that they are no forcing bits for ``SYSTEM`` bits (``%S``).

    | The read bit is at the position ``address % 8`` from the right. For example, if I read ``%M255``, ``255 % 8 = 7``. So ``%M255`` is the last bit from the right. The bit at the position ``0`` is ``%M248``.
    | The same mechanism applies to the second byte, for the forcing bits.

    This function returns a ``tuple``, which is structured like this: ::

        (
            bool, # Value of read bit
            bool, # Forcing of read bit
            {
                248: (bool, bool), # (value, forcing)
                249: (True, False), # Value = 1, no forcing
                250: (False, True), # Forced to 0
                251: (True, True), # Forced to 1
                252: (bool, bool),
                253: (bool, bool),
                254: (bool, bool),
                255: (bool, bool),
            }
        )

    :param int address: Read bit address
    :param int value_bits: Value bits
    :param bool has_forcing: Specify if there is forcing (only for ``INTERNAL`` bit ``%M``)
    :param int forcing_bits: Forcing bits (only if ``has_forcing`` is ``True``)

    :returns: Tuple which store the read bits values and forcing
    :rtype: | (bool, bool, dict[int: (bool, bool)]) if forcing
            | (bool, dict[int: bool]) if not
    """
    # All bits
    offset = address % 8
    result = {}
    start_address = address - offset
    for i in range(8):
        value_bit = (values_bits & (1 << i)) != 0

        if has_forcing:
            forcing_bit = (forcing_bits & (1 << i)) != 0
            t = (value_bit, forcing_bit)
        else:
            t = value_bit

        result[i + start_address] = t

    if has_forcing:
        return (*result[address], result)   # result[address] is a tuple,
                                            # we use * to get (result[address][0], result[address][1], ...)
    return (result[address], result)

def parse_read_bit_result(address, bytes, has_forcing=False):
    """Parse ``READ_XXX_BIT`` response bytes.
    
    At most 2 bytes are received:

    * 8 values bits
    * 8 forcing bits
    
    Note that they are no forcing bits for ``SYSTEM`` bits (``%S``).

    | The read bit is at the position ``address % 8`` from the right. For example, if I read ``%M255``, ``255 % 8 = 7``. So ``%M255`` is the last bit from the right. The bit at the position ``0`` is ``%M248``.
    | The same mechanism applies to the second byte, for the forcing bits.

    This function returns a ``tuple``, which is structured like this: ::

        (
            bool, # Value of read bit
            bool, # Forcing of read bit
            {
                248: (bool, bool), # (value, forcing)
                249: (True, False), # Value = 1, no forcing
                250: (False, True), # Forced to 0
                251: (True, True), # Forced to 1
                252: (bool, bool),
                253: (bool, bool),
                254: (bool, bool),
                255: (bool, bool),
            }
        )

    :param int address: Read bit address
    :param int value_bits: Value bits
    :param bool has_forcing: Specify if there is forcing (only for ``INTERNAL`` bit ``%M``)
    :param int forcing_bits: Forcing bits (only if ``has_forcing`` is ``True``)

    :returns: Tuple which store the read bits values and forcing
    :rtype: | (bool, bool, dict[int: (bool, bool)]) if forcing
            | (bool, dict[int: bool]) if not
    """
    if has_forcing:
        return _parse_read_bit_bytes(address, bytes[0], has_forcing, bytes[1])

    return _parse_read_bit_bytes(address, bytes[0], has_forcing)

def parse_read_bits_result(expected_obj_type, start_address, number, bytes, has_forcing=False):
    """Parse multiple bit reading response.

    The response contains ``number / 8`` bytes for bits values, followed by ``number / 8`` for the forcing bits.

    .. NOTE::
    
        They are no forcing bits for ``SYSTEM`` bits (``%S``).

    The start_address bit is at position ``0`` (from the right) of the first byte.
    The first byte contains bits from address ``start_address + 0`` to ``start_address + 7``; 
    the second byte containts the bits ``start_address + 8`` to ``start_address + 15``; etc.

    The same rule applies for the forcing bits.

    For exemple, if I read 16 bits starting at ``%M255``, the first byte contains [``%M255``, ``%M262``], the second [``%M263``, ``%M270``].
    The two next bytes contain forcing information about [``%M255``, ``%M262``], then [``%M263``, ``%M270``].

    This function returns these information in a dictionary: ::

        {
            255: (bool, bool), # Value, forcing
            256: (True, False), # Value = 1, no forcing
            257: (True, True), # Forced to 1
            258: (False, True), # Forced to 0
            259: (bool, bool),
            260: (bool, bool),
            261: (bool, bool),
            262: (bool, bool),
            # ...
        }
    
    :param int expected_obj_type: Object type sent in the ``READ_OBJECTS`` request
    :param int start_address: First address read
    :param int number: Number of bits
    :param list[int] bytes: Received response
    :param bool has_forcing: Specify if there is forcing (only for ``INTERNAL`` bits ``%M``)

    :returns: Dictionary with values (and forcing) for each address
    :rtype: | dict[int: (bool, bool)] if forcing
            | dic[int: bool] if not

    :raises UnexpectedObjectTypeResponse: If the ``READ_OBJECTS`` object type is not the same as the sent request
    """
    if bytes[0] != expected_obj_type:
        raise UnexpectedObjectTypeResponse(expected_obj_type, bytes[1])

    bytes = bytes[1:]

    bytes_number = number // 8
    result = {}
    for i in range(number):
        vbyte_idx = i // 8
        voffset = i % 8
        value = (bytes[vbyte_idx] & (1 << voffset)) != 0

        if has_forcing:
            fbyte_idx = vbyte_idx + bytes_number
            foffset = voffset
            forcing = (bytes[fbyte_idx] & (1 << foffset)) != 0

            res = (value, forcing)
        else:
            res = value

        result[start_address + i] = res

    return result

def parse_read_word_result(bytes):
    """Parse ``READ_XXX_WORD`` and ``READ_XXX_DWORD`` response.

    The response contains 2 or 4 bytes (``WORD`` or ``DWORD``). These bytes represent the signed word value (complement to 2) in little endian (less significant byte first).

    This function convert this list of bytes into a signed int.

    :param list[int] bytes: Received bytes without UNI-TE response code

    :returns: Signed word value
    :rtype: int
    """
    return int.from_bytes(bytes, byteorder="little", signed=True)

def parse_read_words_result(expected_obj_type, obj_size, bytes):
    """Parse multiple words and double words reading response.

    The response contains all the bytes of all words values. The values are signed (complement to 2) and in little endian (less significant byte first). 

    :param int expected_obj_type: Object type sent in the ``READ_OBJECTS`` request
    :param int obj_size: Size in bytes of the read word (2 for ``WORD``, 4 for ``DWORD``)
    :param list[int] bytes: Received response without UNI-TE response code

    :returns: Values of (d)words as signed int
    :rtype: list[int]

    :raises UnexpectedObjectTypeResponse: If the ``READ_OBJECTS`` object type is not the same as the sent request
    """
    if bytes[0] != expected_obj_type:
        raise UnexpectedObjectTypeResponse(expected_obj_type, bytes[1])

    bytes = bytes[1:]

    splitted = split_list_n(bytes, obj_size)
    values = [parse_read_word_result(v) for v in splitted]

    return values

#def _parse_io_values_bytes(struct, values):
#    length = struct[0]
#    struct = struct[1:]
#    
#    result = {}
#    for i in range(length):
#        byte_idx = i // 8
#        bit_idx = i % 8
#        struct_bit = (struct[byte_idx] & (1 << bit_idx)) != 0
#        value_bit = (values[byte_idx] & (1 << bit_idx)) != 0
#
#        result[i] = {
#            "type": "o" if struct_bit else "i",
#            "value": value_bit
#        }
#
#    return result

#def _parse_module_class_0_1(info_bytes):
#    channels_nb = info_bytes[1]
#    module_struct = info_bytes[2]
#    io_values = info_bytes[3]
#
#    return _parse_io_values_bytes(module_struct, io_values)
#
#def _parse_module_class_2(info_bytes):
#
#
#def parse_read_digital_module_image(response):
#    report_code =  response[2]
#    if report_code == 0: # no problem
#        report_bytes = response[3:]
#        module_status = report_bytes[0]
#        if module_status == 0: # no problem
#            module_class = report_bytes[1]
#            if module_class

def _parse_io_bit_result(start_address, bytes):
    """Parse ``%I`` or ``%Q`` bits in ``READ_IO_CHANNEL`` response.

    Bits section is a part of "Specific operation" section of ``READ_IO_CHANNEL`` response.

    | The first byte is the length.
    | The next bytes are the bits values. Each of these bytes contains 8 information about one bit, and the value of the bit is the less significant bit. That is the only bit returned.

    This function return a dictionary which stores the boolean value for each address. For example, if I read 8 bit starting at address ``0``, the result is: ::

        {
            0: True,
            1: False,
            2: False,
            3: False,
            4: False,
            5: True,
            6: False,
            7: False,
        }
    
    :param int start_address: First read bit address
    :param list[int] bytes: Bits values bytes

    :return: Dictionary which maps addresses with values
    :rtype: dict[int: bool]
    """
    length = bytes[0]
    bytes = bytes[1:]

    result = {}
    for i in range(length):
        bit = (bytes[i] & 1) != 0 # bit 0 is the value
        result[start_address + i] = bit

    return result

def _parse_io_words_result(start_address, bytes):
    """Parse ``%IW`` or ``%QW`` words in ``READ_IO_CHANNEL`` response.

    Words section is a part of "Specific operation" section of ``READ_IO_CHANNEL`` response.
    | The first byte is the length.
    | If the length is ``0``: there is no more byte.
    | If the length is > ``0``: the next bytes are the signed word values (complement to 2) in little endian.

    This function return a dictionary which stores the word value for each address. For example, if I read 8 words starting at address 0, the result is: ::

        {
            0: 1,
            1: 0,
            2: 0,
            3: 0,
            4: 0,
            5: 12,
            6: 0,
            7: 0,
        }
    
    :param int start_address: First read word address
    :param list[int] bytes: Bits values bytes

    :return: Dictionary which maps addresses with values
    :rtype: dict[int: int]
    
    """
    splitted = split_list_n(bytes, 2)

    result = {}
    for i, v in enumerate(splitted):
        result[start_address + i] = parse_read_word_result(v)

    return result

def _parse_operation_zone(start_address, bytes):
    """Parse "Specific operation" section of ``READ_IO_CHANNEL`` section.

    | The first byte is the length of this section.
    | The next bytes are:

    * %I bits values (see ``_parse_io_bits_result``)
    * %Q bits values (see ``_parse_io_bits_result``)
    * %IW words values (see ``_parse_io_words_result``)
    * %QW words values (see ``_parse_io_words_result``)

    The returned structure is: ::

        {
            "I": {          # see _parse_io_bits_result
                0: True,
                1: False,
            },
            "Q": {          # see _parse_io_bits_result
                0: False,
                1: False,
            },

            "IW": {          # see _parse_io_words_result
                0: 1,
                1: 0,
            },
            "QW": {          # see _parse_io_words_result
                0: 1,
                1: 0,
            },
        }

    :param int start_address: First read object address
    :param list[int] bytes: "Specific operation" section bytes

    :returns: Dictionary which maps each section (``%I``, ``%Q``, ...) with its values
    :rtype: dict[str: dict]
    """
    length = bytes[0]
    bytes = bytes[1:]

    result = {}

    i_bits = _parse_io_bit_result(start_address, bytes)
    result["I"] = i_bits

    i_length = bytes[0]
    bytes = bytes[1 + i_length:] # pop length and bit bytes

    q_bits = _parse_io_bit_result(start_address, bytes)
    result["Q"] = q_bits

    q_length = bytes[0]
    bytes = bytes[1 + q_length:] # pop length and bit bytes

    iw_length_bytes = bytes[0:2]
    bytes = bytes[2:]
    iw_length = int.from_bytes(iw_length_bytes, byteorder="little", signed=False)
    if iw_length > 0:
        iw = _parse_io_words_result(start_address, bytes)
        result["IW"] = iw

    qw_length_bytes = bytes[0:2]
    bytes = bytes[2:]
    qw_length = int.from_bytes(qw_length_bytes, byteorder="little", signed=False)
    if qw_length > 0:
        qw = _parse_io_words_result(start_address, bytes)
        result["QW"] = qw

    return result

def parse_read_io_channel_result(start_address, response):
    """Parse ``READ_IO_CHANNEL`` response.

    | The two first bytes are the general report and channel default: they have to be ``0``.
    | The next read byte is the 5th byte: the operation report. It also has to be ``0``.
    | Then, the "Specific operation" section is parsed, see ``_parse_operation_zone``.

    The returned result is the same as ``_parse_operation_zone()`` result: ::

        {
            "I": {          # see _parse_io_bits_result
                0: True,
                1: False,
            },
            "Q": {          # see _parse_io_bits_result
                0: False,
                1: False,
            },

            "IW": {          # see _parse_io_words_result
                0: 1,
                1: 0,
            },
            "QW": {          # see _parse_io_words_result
                0: 1,
                1: 0,
            },
        }

    :param int start_address: First read object address
    :param list[int] response: UNI-TE response without the response code

    :returns: Dictionary which maps each section (``%I``, ``%Q``, ...) with its values
    :rtype: dict[str: dict]
    """
    if response[0] == 0 and response[1] == 0:
        operation_report = response[5]
        if operation_report == 0:
            return _parse_operation_zone(start_address, response[5:])

def parse_write_result(response):
    """Parse ``WRITE_XXX_XXX`` response.

    :param list[int] response: Response **with** UNI-TE response code

    :returns: ``True`` if response code is ``0xFE``
    :rtype: bool    
    """
    return response[0] == 0xFE

def parse_write_io_channel_result(response):
    """Parse ``WRITE_IO_CHANNEL`` response.

    :param list[int] response: Response without UNI-TE response code

    :returns: ``True`` if the first byte (report) is ``0``
    :rtype: bool
    """
    return response[0] == 0

def main():
    """Main function used for tests.

    Test parsing of ``READ_IO_CHANNEL`` response: ``[0x73, 0, 0, 1, 0, 1, 0, 2, 1, 0, 1, 1, 0, 0, 1, 0, 0xBC, 0]``
    """
    r = parse_read_io_channel_result([0x73, 0, 0, 1, 0, 1, 0, 2, 1, 0, 1, 1, 0, 0, 1, 0, 0xBC, 0])
    print("RES =", r)

if __name__ == "__main__":
    main()