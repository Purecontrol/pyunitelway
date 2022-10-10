"""UNI-TELWAY client module.
"""

import socket
import time

from pyunitelway.constants import *
from pyunitelway.conversion import parse_mirror_result, parse_read_bit_result, parse_read_bits_result, parse_read_io_channel_result, parse_read_word_result, parse_read_words_result, parse_write_io_channel_result, parse_write_result, unwrap_unite_response
from pyunitelway.errors import BadReadBitsNumberParam, UnexpectedUniteResponse
from pyunitelway.utils import compute_bcc, duplicate_dle, format_bytearray, format_hex_list, get_response_code, is_valid_response_code, sublist_in_list

class UnitelwayClient:
    """UNI-TELWAY slave client. To send UNI-TELWAY messages to master PLC.

    The sender PC is considered a slave, and the contacted PLC is the master.
    
    .. WARNING::
    
        Make sure that the slave address you chose for your PC is not already used by a slave PLC.
    
    :param int slave_address: Client slave address
    :param int category_code: UNI-TE category code (between 0 and 7)
    :param int xway_network: X-WAY network value
    :param int xway_station: X-WAY station value
    :param int xway_gate: X-WAY gate value
    :param int xway_ext1: X-WAY ext1 value (5-6 levels addressing)
    :param int xway_ext2: X-WAY ext2 value (5-6 levels addressing)
    :param bool VPN_Mode : Switch On if using VPN
    """
    def __init__(self, slave_address, category_code, xway_network, xway_station, xway_gate, xway_ext1, xway_ext2,VPN_Mode):
        """The constructor.
        
        ``ext1`` and ``ext2`` are used for 5 and 6-levels addressing. See: https://download.schneider-electric.com/files?p_enDocType=User+guide&p_File_Name=35000789_K06_000_00.pdf&p_Doc_Ref=35000789K01000, p.55 for the format.
        """
        self._unitelway_start = [
            DLE, STX,
            slave_address
        ]
        
        self._xway_start = [
            0x20,           # Type: standard
            xway_network,
            xway_station,
            xway_gate,
            xway_ext1,
            xway_ext2
        ]

        self.category_code = category_code
        self.link_address = slave_address
        self.VPN_Mode=VPN_Mode

    def connect_socket(self, ip, port, connection_query=None):
        """Connect to the USR-TCP232-306 adapter.

        A *connection query* is also needed to connect. Without this, the client is not able to talk to the PLC. But we
        still don't know how this query is built.

        If the argument ``conection_query`` is ``None`` (default), no connection query is executed.

        :param string ip: Adapter IPv4
        :param int port: Adapter port
        :param list[int] connection_query: *Connection query* bytes
        """
        self.socket = socket.socket(socket.AF_INET)
        self.socket.connect((ip, port))

        if connection_query is not None:
            self._send_connection_query(connection_query)

    def _send_connection_query(self, connection_query):
        """Send the *connection query* on the socket.

        See ``connect_socket`` for more information.

        :param list[int] connection_query: *Connection query*
        """
        self._unitelway_query(connection_query, "Connecting to USR-TCP232-306 adapter")

    def disconnect_socket(self,debug=0):

        try:
            self.socket.close()
            if debug>=2:
                print("Socket is closed")
              
        except:
            print("Socket is not closed")

    

    def _unite_to_xway(self, unite_bytes):
        """Wrap UNI-TE request into an X-WAY request.
        
        It just adds X-WAY header at the beginning. See this `UNI-TELWAY example`_ page 55 for the format.

        .. _`UNI-TELWAY example`: https://download.schneider-electric.com/files?p_enDocType=User+guide&p_File_Name=35000789_K06_000_00.pdf&p_Doc_Ref=35000789K01000

        :param list[int] unite_bytes: UNI-TE request bytes
        
        :returns: X-WAY request bytes
        :rtype: list[int]
        """
        xway_bytes = []
        for b in self._xway_start:
            xway_bytes.append(b)

        xway_bytes += unite_bytes
        return xway_bytes

    def _xway_to_unitelway(self, xway_bytes):
        """Wrap X-WAY request into a UNI-TELWAY request.

        It:

        * appends the header at the beginning
        * compute the length
        * duplicate ``<DLE>``'s
        * add the checksum at the end

        :param list[int] xway_bytes: X-WAY request bytes

        :returns: UNI-TELWAY request bytes
        :rtype: list[int]
        """
        unitelway_bytes = []
        for b in self._unitelway_start:
            unitelway_bytes.append(b)

        # Length
        length = len(xway_bytes)
        # Duplicate DLE if length == DLE
        if length == DLE:
            unitelway_bytes.append(DLE)
        unitelway_bytes.append(len(xway_bytes))

        unitelway_data_start = len(unitelway_bytes)

        unitelway_bytes += xway_bytes
        
        duplicate_dle(unitelway_bytes, unitelway_data_start)

        bcc = compute_bcc(unitelway_bytes)
        unitelway_bytes.append(bcc)

        return unitelway_bytes

    def _unite_to_unitelway(self, unite_bytes):
        """Unwrap UNI-TE request into a UNI-TELWAY request.

        It chains ``unite_to_xway`` and ``xway_to_unitelway``.

        :param list[int] unite_bytes: UNI-TE request bytes

        :returns: UNI-TELWAY request bytes
        :rtype: list[int]
        """
        xway = self._unite_to_xway(unite_bytes)
        return self._xway_to_unitelway(xway)

    def _unitelway_query(self, query, text="", debug=0):
        """Send a UNI-TELWAY request on the socket.

        .. WARNING::

            The UNI-TELWAY request has to be already built

        :param list[int] query: UNI-TELWAY request bytes
        :param str text: Text to print in debug mode
        :param bool debug: :doc:`Debug mode </debug_levels>`
        """
        bytes = bytearray(query)
        if debug >= 1:
            print(f"------------------ {text} ----------------")
            print(f"[{time.time()}] Sending: {format_bytearray(bytes)}")
        
        
        n = self.socket.send(bytes)
        
        #if debug:
        #    print(f"[{time.time()}] Sent {n} bytes.")

    def _unite_query(self, query, text="", debug=0):
        """Send a UNI-TE request on the socket.

        .. NOTE::

            All the UNI-TELWAY request is printed

        :param list[int] query: UNI-TE request bytes
        :param str text: Text to print in debug mode
        :param bool debug: :doc:`Debug mode </debug_levels>`
        """
        unitelway = self._unite_to_unitelway(query)
        self._unitelway_query(unitelway, text, debug)

    def _wait_unite_response(self, timeout=TIMEOUT_SEC, debug=0):
        """Wait until a UNI-TE response is received.

        This function works with ``unite_query_until_response()``.

        The master PLC regularly sends ``<DLE> <ENQ> XX`` enquery bytes. These bytes can be sent between a request from a slave
        and the response, that's why we need to wait our response.

        This function regularly reads 3 bytes on the socket while it encounters ``<DLE> <ENQ>``.
        If it receives ``<DLE> <STX>``, it reads the next 256 bytes, and return the result. 

        If the timeout is reached, it returns ``None``, then ``unite_query_until_response`` will send again the request.

        :param float timeout: Timeout before sending again the request

        :returns: Response bytes if the timeout is not reached.
            None otherwise
        :rtype: list[int] or None
        """
        start = time.time()
        end = start
        buf = []
        while True:
            r = self.socket.recv(3)
            if debug >= 2:
                print("recv =>", format_hex_list(r))
            buf.extend(b for b in r)

            # Delete <DLE> <ENQ> <nb>
            res = sublist_in_list(buf, [DLE, ENQ])
            is_in = res[0]
            index = res[1]
            if is_in:
                # Delete three elements starting at index
                for _ in range(3):
                    if index < len(buf):
                        buf.pop(index)

            # Find <DLE> <STX> sequence
            tmp = sublist_in_list(buf, [DLE, STX])
            dle_stx_ok = tmp[0]
            dle_stx_idx = tmp[1]

            if dle_stx_ok:
                buf.extend(b for b in self.socket.recv(1))
                received_link_addr = buf[dle_stx_idx + 2]
                if received_link_addr == self.link_address:
                    break
            
            if self.VPN_Mode == False:
                end = time.time()
                if end - start >= timeout:
                    return None

        buf = buf[dle_stx_idx:]
        buf.extend(b for b in self.socket.recv(256))
        
        return buf

    def _unite_query_until_response(self,address, query, timeout=TIMEOUT_SEC, text="", debug=0):
        """Send a UNI-TE request until it receives a valid response.

        This function works with ``wait_unite_response()``.

        If ``wait_unite_response`` returns ``None`` (reached timeout), it sends the request again.

        .. NOTE::

            All the UNI-TELWAY request is printed

        :param list[int] query: UNI-TE request
        :param float timeout: Timeout before sending again the request
        :param str text: Text to print in debug mode
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: UNI-TELWAY response bytes
        :rtype: list[int]
        """
        r = None
        while r is None:
            #Used with VPN
            if self.VPN_Mode:
                self._unite_query(query, text, debug)
                r = self._wait_unite_response(timeout, debug)
            #Used in local / must wait polling from automate
            else:
                if self.is_my_turn_to_talk(address):
                    self._unite_query(query, text, debug)
                    r = self._wait_unite_response(timeout, debug)
        return r

    def run_unite(self,address,query, timeout=TIMEOUT_SEC,text="", debug=0):
        """High-level function to send UNI-TE request and get the response.

        This function uses ``unite_query_until_response()`` and ``utils.unwrap_unite_response()``. So don't use them alone.
        See ``utils.py`` for more details about ``unwrap_unite_response``.

        .. NOTE::

            All the UNI-TELWAY request and response are printed

        :param address[int] : slave address
        :param list[int] query: UNI-TE request
        :param float timeout: Timeout before sending again the request
        :param str text: Text to print in debug mode
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: UNI-TE response bytes
        :rtype: list[int]

        :raises BadUnitelwayChecksum: Received bad UNI-TELWAY checksum
        """
        r = self._unite_query_until_response(address,query, timeout, text, debug)
        if debug >= 1:
            print(f"[{time.time()}] Received:", format_hex_list(r))
        
        self.disconnect_socket(debug=debug)
        
        return unwrap_unite_response(r)
    
    def is_my_turn_to_talk(self,address,debug=0):
        """Allows slave to give permission to the master to communicate

        .. NOTE::

        :param address[int] : slave address
        :param list[int] query: UNI-TE request
        :param float timeout: Timeout before sending again the request
        :param str text: Text to print in debug mode
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: Boolean. Slave authorized or not to communicate to master

        :raises BadUnitelwayChecksum: Received bad UNI-TELWAY checksum
        """
        buf = []
        is_in= False

        while True:
            r = self.socket.recv(3)
            if debug >= 1:
                print("recv =>", format_hex_list(r))

            buf.extend(b for b in r)

            if debug >=2:
                print("Buffer from master")
                print("Frame to get :"+ [DLE, ENQ,address])

            res = sublist_in_list(buf, [DLE, ENQ,address])
            is_in=res[0]

            if is_in:
                break
        return is_in

    #------ Mirror ------
    def mirror(self, data, debug=0):
        """Test connection with ``MIRROR`` request.

        This request sends a bunch of data and checks if the received message contains the same data.
        If data are the same: return ``True``, else ``False``.

        :param list[int] data: Data to send in the request
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: ``True`` if the received data is the same as the sent data
        :rtype: bool

        :raises BadUnitelwayChecksum: Bad UNI-TELWAY checksum
        :raises RefusedUnitelwayMessage: X-WAY type code == ``0x22``
        :raises UniteRequestFailed: Received ``0xFD``
        :raises UnexpectedUniteResponse: The response code is not ``MIRROR``'s response code 
        """
        unite_query = [0xFA, self.category_code, *data]
        slave_address= self._unitelway_start[2]
        
        resp = self.run_unite(slave_address,unite_query, text="MIRROR", debug=debug)
       

        if not is_valid_response_code(MIRROR, resp[0]):
            raise UnexpectedUniteResponse(get_response_code(MIRROR), resp[0])

        return parse_mirror_result(resp[1:], data)

        

    #------ Reading queries ------
    def _build_addressing_query(self, query_code, address, address_bytes_count=2, address_byte_order="little"):
        """Create a generic UNI-TE reading and writing request.

        ``READ_XXX_BIT``, ``READ_XXX_WORD``, ``READ_XXX_DWORD``, ``WRITE_XXX_BIT``, ``WRITE_XXX_WORD`` and ``WRITE_XXX_DWORD`` use the same structure:

        ============  =============  ========================
        Request code  Category code  Address
        ============  =============  ========================
        1 byte        1 byte         2 bytes (little endian)
        ============  =============  ========================

        This function returns these bytes from the request code and the address.

        :param int query_code: Request code
        :param int address: Reading address
        :param int address_bytes_count: Number of bytes reserved for the address in the query
        :param str address_byte_order: Address byte order in the request

        :returns: Reading request
        :rtype: list[int]
        """
        address_bytes = address.to_bytes(address_bytes_count, byteorder=address_byte_order, signed=False)
        unite_query = [query_code, self.category_code]
        unite_query.extend(address_bytes)

        return unite_query

    def read_internal_bit(self, address, debug=0):
        """Read bit in the internal memory (``%M``).

        The request reads bits by 8. The first returned bit is at the nearest address which is a multiple of 8.
        This function also returns the forcing state for each bit.

        For example, reading ``%M255`` returns bits from ``%M248`` to ``%M255``.

        The returned structure is a tuple with the value and forcing of the specified bit, and a dictionary which maps
        the address with the value and forcing for each read bit.::

            (
                bool, # value of read bit
                bool, # forcing of read bit
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

        :param int address: Bit address
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: Tuple with value and forcing for the 8 bits
        :rtype: (bool, bool, dict[int: (bool, bool)])
        """
        unite_query = self._build_addressing_query(READ_INTERNAL_BIT, address)
        
        slave_address= self._unitelway_start[2]

        resp = self.run_unite(slave_address, unite_query, text=f"READ_INTERNAL_BIT at %M{address}", debug=debug)

        if not is_valid_response_code(READ_INTERNAL_BIT, resp[0]):
            raise UnexpectedUniteResponse(get_response_code(READ_INTERNAL_BIT), resp[0])

        return parse_read_bit_result(address, resp[1:], has_forcing=True)

        

    def read_system_bit(self, address, debug=0):
        """Read bit in the system memory (``%S``).

        The request reads bits by 8. The first returned bit is at the nearest address which is a multiple of 8.

        For example, reading ``%S255`` returns bits from ``%S248`` to ``%S255``.

        The returned structure is a tuple with the value and forcing of the specified bit, and a dictionary which maps
        the address with the value and forcing for each read bit.::

            (
                bool, # value of read bit
                {
                    248: bool, # Value
                    249: True, # Value = 1
                    250: False, # Value = 0
                    251: bool,
                    252: bool,
                    253: bool,
                    254: bool,
                    255: bool,
                }
            )

        :param int address: Bit address
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: Tuple with value and forcing for the 8 bits
        :rtype: (bool, dict[int: bool])
        """
        unite_query = self._build_addressing_query(READ_SYSTEM_BIT, address)

        slave_address= self._unitelway_start[2]

        resp = self.run_unite(slave_address, unite_query, text=f"READ_SYSTEM_BIT at %S{address}", debug=debug)

        if not is_valid_response_code(READ_SYSTEM_BIT, resp[0]):
            raise UnexpectedUniteResponse(get_response_code(READ_SYSTEM_BIT), resp[0])

        if debug >=2:
            print(address)

        return parse_read_bit_result(address, resp[1:], has_forcing=False)

    def read_internal_word(self, address, debug=0):
        """Read a word (2 bytes signed integer) in the internal memory (``%MW``).

        :param int address: Word address
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: Signed word value
        :rtype: int
        """

        unite_query = self._build_addressing_query(READ_INTERNAL_WORD, address)

        slave_address= self._unitelway_start[2]

        resp = self.run_unite(slave_address,unite_query,text=f"READ_INTERNAL_WORD at %MW{address}", debug=debug)

        if not is_valid_response_code(READ_INTERNAL_WORD, resp[0]):
            raise UnexpectedUniteResponse(get_response_code(READ_INTERNAL_WORD), resp[0])
        
        return parse_read_word_result(resp[1:])

    def read_system_word(self, address, debug=0):
        """Read a word (2 bytes signed integer) in the system memory (``%SW``).

        :param int address: Word address
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: Signed word value
        :rtype: int
        """
        unite_query = self._build_addressing_query(READ_SYSTEM_WORD, address)

        slave_address= self._unitelway_start[2]

        resp = self.run_unite(slave_address,unite_query, text=f"READ_SYSTEM_WORD at %SW{address}", debug=debug)

        if not is_valid_response_code(READ_SYSTEM_WORD, resp[0]):
            raise UnexpectedUniteResponse(get_response_code(READ_SYSTEM_WORD), resp[0])

        return parse_read_word_result(resp[1:])

    def read_constant_word(self, address, debug=0):
        """Read a word (2 bytes signed integer) in the constant memory (``%KW``).

        :param int address: Word address
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: Signed word value
        :rtype: int
        """
        unite_query = self._build_addressing_query(READ_CONSTANT_WORD, address)

        slave_address= self._unitelway_start[2]

        resp = self.run_unite(slave_address, unite_query, text=f"READ_CONSTANT_WORD at %KW{address}", debug=debug)

        if not is_valid_response_code(READ_CONSTANT_WORD, resp[0]):
            raise UnexpectedUniteResponse(get_response_code(READ_CONSTANT_WORD), resp[0])

        return parse_read_word_result(resp[1:])

    def read_internal_dword(self, address, debug=0):
        """Read a double word (4 bytes signed integer) in the internal memory (``%MW``).

        :param int address: Word address
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: Signed word value
        :rtype: int
        """
        unite_query = self._build_addressing_query(READ_INTERNAL_DWORD, address)

        slave_address= self._unitelway_start[2]

        resp = self.run_unite(slave_address, unite_query, text=f"READ_INTERNAL_DWORD at %MD{address}", debug=debug)

        if not is_valid_response_code(READ_INTERNAL_DWORD, resp[0]):
            raise UnexpectedUniteResponse(get_response_code(READ_INTERNAL_DWORD), resp[0])

        return parse_read_word_result(resp[1:])

    def read_constant_dword(self, address, debug=0):
        """Read a double word (4 bytes signed integer) in the constant memory (``%KW``).

        :param int address: Word address
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: Signed word value
        :rtype: int
        """
        unite_query = self._build_addressing_query(READ_CONSTANT_DWORD, address)

        slave_address= self._unitelway_start[2]

        resp = self.run_unite(slave_address, unite_query, text=f"READ_CONSTANT_DWORD at %KD{address}", debug=debug)

        if not is_valid_response_code(READ_CONSTANT_DWORD, resp[0]):
            raise UnexpectedUniteResponse(get_response_code(READ_CONSTANT_DWORD), resp[0])

        return parse_read_word_result(resp[1:])

    #------ Reading objects queries ------
    def _read_objects(self, segment, obj_type, start_address, number, debug=0):
        """Send ``READ_OBJECTS`` request.

        This function is a low-level function: it returns directly the UNI-TE response. It's used in ``read_xxx_bits``, ``read_xxx_words`` and
        ``read_xxx_dwords``.

        :param int semgent: Object segment value
        :param int obj_type: Object type value
        :param int start_address: First address to read
        :param int number: Number of ojbects to read
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: UNI-TE ``READ_OBJECTS`` response
        """
        address_bytes = start_address.to_bytes(2, byteorder="little", signed=False)
        number_bytes = number.to_bytes(2, byteorder="little", signed=False)

        unite_query = [READ_OBJECTS, self.category_code, segment, obj_type]
        unite_query.extend(address_bytes)
        unite_query.extend(number_bytes)

        slave_address= self._unitelway_start[2]

        resp = self.run_unite(slave_address,unite_query, text=f"READ_OBJECTS Seg={segment} Type={obj_type} @{start_address} N={number}", debug=debug)

        if not is_valid_response_code(READ_OBJECTS, resp[0]):
            raise UnexpectedUniteResponse(get_response_code(READ_OBJECTS), resp[0])

        return resp

    def read_internal_bits(self, start_address, number, debug=0):
        """Read multiple bits in the internal memory (``%M``).

        .. WARNING::

            The number of bits must be a multiple of 8.

        This function returns a dictionary which maps the address with the value and forcing for each bit: ::

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

        :param int start_address: First address to read
        :param int number: Number of bits to read
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: Dictionary with value and forcing for each bit
        :rtype: dict[int: (bool, bool)]
        """
        if number % 8 != 0:
            raise BadReadBitsNumberParam(number)

        r = self._read_objects(0x64, 0x05, start_address, number, debug)
        return parse_read_bits_result(0x05, start_address, number, r[1:], has_forcing=True)

    def read_system_bits(self, start_address, number, debug=0):
        """Read multiple bits in the system memory (``%S``).

        .. WARNING::

            The number of bits must be a multiple of 8.

        This function returns a dictionary which maps the address with the value for each bit: ::

            {
                255: bool,   # Value
                256: True,   # Value = 1
                257: True,   # Value = 1
                258: False,  # Value = 0
                259: bool,
                260: bool,
                261: bool,
                262: bool,
                # ...
            }

        :param int start_address: First address to read
        :param int number: Number of bits to read
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: Dictionary with value for each bit
        :rtype: dict[int: bool]
        """
        if number % 8 != 0:
            raise BadReadBitsNumberParam(number)

        r = self._read_objects(0x64, 0x06, start_address, number, debug)
        return parse_read_bits_result(0x06, start_address, number, r[1:], has_forcing=False)

    def read_internal_words(self, start_address, number, debug=0):
        """Read multiple internal words (2 bytes signed integers) (``%MW``).

        :param int start_address: First address to read
        :param int number: Number of words to read
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: List of signed word values
        :rtype: list[int]
        """
        r = self._read_objects(0x68, 0x07, start_address, number, debug)
        return parse_read_words_result(0x07, 2, r[1:])

    def read_system_words(self, start_address, number, debug=0):
        """Read multiple system words (2 bytes signed integers) (``%SW``).

        :param int start_address: First address to read
        :param int number: Number of words to read
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: List of signed word values
        :rtype: list[int]
        """
        r = self._read_objects(0x6A, 0x07, start_address, number, debug)
        return parse_read_words_result(0x07, 2, r[1:])

    def read_constant_words(self, start_address, number, debug=0):
        """Read multiple constant words (2 bytes signed integers) (``%KW``).

        :param int start_address: First address to read
        :param int number: Number of words to read
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: List of signed word values
        :rtype: list[int]
        """
        r = self._read_objects(0x69, 0x07, start_address, number, debug)
        return parse_read_words_result(0x07, 2, r[1:])

    def read_internal_dwords(self, start_address, number, debug=0):
        """Read multiple internal double words (4 bytes signed integers) (``%MD``).

        .. WARNING::

            | Reading multiple ``DWORD``'s reads with a step of 2 addresses.
            | If I read 2 ``DWORD``'s starting at ``%MD1``, it will return ``[%MD1, %MD3]``.

        :param int start_address: First address to read
        :param int number: Number of words to read
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: List of signed words values
        :rtype: list[int]
        """
        r = self._read_objects(0x68, 0x08, start_address, number, debug)
        return parse_read_words_result(0x08, 4, r[1:])

    def read_constant_dwords(self, start_address, number, debug=0):
        """Read multiple constant double words (4 bytes signed integers) (``%KD``).

        .. WARNING::

            | Reading multiple ``DWORD``'s reads with a step of 2 addresses.
            | If I read 2 ``DWORD``'s starting at ``%MK1``, it will return ``[%KD1, %KD3]``.

        :param int start_address: First address to read
        :param int number: Number of words to read
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: List of signed words values
        :rtype: list[int]
        """
        r = self._read_objects(0x69, 0x08, start_address, number, debug)
        return parse_read_words_result(0x08, 4, r[1:])

    #---------- Reading IO queries ----------
    #def read_digital_module_image(self, extension, module_xway_address, debug=0):
        #unite_query = [0x49, self.category_code, extension, *module_xway_address, 1]
        #resp = self.run_unite(unite_query, text=f"READ_DIGITAL_MODULE_IMAGE at Address={module_xway_address}", debug=debug)

        #if not is_valid_response_code(READ_DIGITAL_MODULE_IMAGE, resp[0]):
            #raise UnexpectedUniteResponse(get_response_code(READ_DIGITAL_MODULE_IMAGE), resp[0])

        #return parse_read_digital_image_module_response(resp)

    def read_io_channel(self, xway_channel_address, obj_type, number, start_address, debug=0):
        """**[NOT TESTED]** Read I/O channel (``%I``, ``%Q``, ``%IW``, ``%QW``).

        The ``READ_IO_CHANNEL`` reads input and output bits and words at the same time. The ``number`` and ``start_address``
        arguments apply to all these types of data.

        It returns a dictionary with all input/output bits and words (see ``conversion.parse_read_io_channel_result``): ::

            {
                "I": {
                    0: True,
                    1: False,
                },
                "Q": {
                    0: False,
                    1: False,
                },

                "IW": {
                    0: 1,
                    1: 0,
                },
                "QW": {
                    0: 1,
                    1: 0,
                },
            }

        :param list[int] xway_channel_address: Bytes of the channel X-WAY address
        :param int obj_type: I/O object type
        :param int number: Number of objects to read.
        :param int start_address: First address to read.
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: Dictionary with all the values
        :rtype: dict[str: dict]
        """
        unite_query = [0x43, self.category_code, *xway_channel_address, 1, obj_type, number, start_address]
        r = self.run_unite(unite_query, text=f"READ_IO_CHANNEL Type={obj_type} @{start_address} N={number}", debug=debug)

        if not is_valid_response_code(READ_IO_CHANNEL, r[0]):
            raise UnexpectedUniteResponse(get_response_code(READ_IO_CHANNEL), r[0])

        return parse_read_io_channel_result(start_address, r[1:])



    #---------- Writing ----------
    def write_internal_bit(self, address, value, debug=0):
        """Write a bit in the internal memory (``%M``).

        The value can be ``0``, ``1``, ``True`` or ``False``.

        :param int address: Address to write
        :param bool value: Value to write
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: ``True`` if the writing succeeded
        :rtype: bool
        """
        unite_query = self._build_addressing_query(WRITE_INTERNAL_BIT, address)

        value_int = int(value)
        unite_query.append(value_int)
        
        slave_address= self._unitelway_start[2]

        resp = self.run_unite(slave_address, unite_query, text=f"WRITE_INTERNAL_BIT %M{address} = {value_int}", debug=debug)

        if not is_valid_response_code(WRITE_INTERNAL_BIT, resp[0]):
            raise UnexpectedUniteResponse(get_response_code(WRITE_INTERNAL_BIT), resp[0])
        else:
            if debug >=2:
                print("Request taken into account")

        return parse_write_result(resp)
        
    def write_system_bit(self, address, value, debug=0):
        """Write a bit in the system memory (``%S``).

        The value can be ``0``, ``1``, ``True`` or ``False``.

        :param int address: Address to write
        :param bool value: Value to write
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: ``True`` if the writing succeeded
        :rtype: bool
        """
        unite_query = self._build_addressing_query(WRITE_SYSTEM_BIT, address)

        value_int = int(value)
        unite_query.append(value_int)
        
        slave_address= self._unitelway_start[2]

        resp = self.run_unite(slave_address, unite_query, text=f"WRITE_SYSTEM_BIT %S{address} = {value_int}", debug=debug)

        if not is_valid_response_code(WRITE_SYSTEM_BIT, resp[0]):
            raise UnexpectedUniteResponse(get_response_code(WRITE_SYSTEM_BIT), resp[0])
        else:
            if debug >=2:
                print("Request taken into account")

        return parse_write_result(resp)
        
    def write_internal_word(self, address, value, debug=0):
        """Write a word (2 bytes signed integer) in the internal memory (``%MW``).

        :param int address: Address to write
        :param int value: Value to write
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: ``True`` if the writing succeeded
        :rtype: bool
        """
        unite_query = self._build_addressing_query(WRITE_INTERNAL_WORD, address)

        value_bytes = value.to_bytes(2, byteorder="little", signed=True)
        unite_query.extend(value_bytes)
        
        slave_address= self._unitelway_start[2]

        resp = self.run_unite(slave_address, unite_query, text=f"WRITE_INTERNAL_WORD %MW{address} = {value}", debug=debug)

        if not is_valid_response_code(WRITE_INTERNAL_WORD, resp[0]):
            raise UnexpectedUniteResponse(get_response_code(WRITE_INTERNAL_WORD), resp[0])
        else:
            if debug >=2:
                print("Request taken into account")
        return parse_write_result(resp)
        
    def write_system_word(self, address, value, debug=0):
        """Write a word (2 bytes signed integer) in the system memory (``%SW``).

        :param int address: Address to write
        :param int value: Value to write
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: ``True`` if the writing succeeded
        :rtype: bool
        """
        unite_query = self._build_addressing_query(WRITE_SYSTEM_WORD, address)

        value_bytes = value.to_bytes(2, byteorder="little", signed=True)
        unite_query.extend(value_bytes)
        
        slave_address= self._unitelway_start[2]

        resp = self.run_unite(slave_address, unite_query, text=f"WRITE_SYSTEM_WORD %SW{address} = {value}", debug=debug)

        if not is_valid_response_code(WRITE_SYSTEM_WORD, resp[0]):
            raise UnexpectedUniteResponse(get_response_code(WRITE_SYSTEM_WORD), resp[0])
        else:
            if debug >=2:
                print("Request taken into account")

        return parse_write_result(resp)
        
    def write_internal_dword(self, address, value, debug=0):
        """Write a double word (4 bytes signed integer) in the internal memory (``%MD``).

        :param int address: Address to write
        :param int value: Value to write
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: ``True`` if the writing succeeded
        :rtype: bool
        """
        unite_query = self._build_addressing_query(WRITE_INTERNAL_DWORD, address)

        value_bytes = value.to_bytes(4, byteorder="little", signed=True)
        unite_query.extend(value_bytes)
        
        slave_address= self._unitelway_start[2]

        resp = self.run_unite(slave_address, unite_query, text=f"WRITE_INTERNAL_DWORD %MD{address} = {value}", debug=debug)

        if not is_valid_response_code(WRITE_INTERNAL_DWORD, resp[0]):
            raise UnexpectedUniteResponse(get_response_code(WRITE_INTERNAL_DWORD), resp[0])
        else:
            if debug >=2:
                print("Request taken into account")

        return parse_write_result(resp)

    def _write_objects(self, segment, obj_type, start_address, number, data, debug=0):
        """Send ``WRITE_OBJECTS`` request.

        This function is a low-level function. It's used by ``write_xxx_bits``, ``write_xxx_words``, ``write_xxx_dwords``.

        The ``data`` argument represents the last bytes of the request.

        :param int segment: Object segment value
        :param int obj_type: Object type value
        :param int start_address: First address to write at
        :param list[int] data: Bytes to write
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: ``True`` if the writing succeeded
        :rtype: bool
        """
        address_bytes = start_address.to_bytes(2, byteorder="little", signed=False)
        number_bytes = number.to_bytes(2, byteorder="little", signed=False)

        unite_query = [WRITE_OBJECTS, self.category_code, segment, obj_type]
        unite_query.extend(address_bytes)
        unite_query.extend(number_bytes)
        unite_query.extend(data)

        slave_address= self._unitelway_start[2]

        resp = self.run_unite(slave_address, unite_query, text=f"WRITE_OBJECTS Seg={segment} Type={obj_type} @{start_address} Values={format_hex_list(data)}", debug=debug)

        if not is_valid_response_code(WRITE_OBJECTS, resp[0]):
            raise UnexpectedUniteResponse(get_response_code(WRITE_OBJECTS), resp[0])

        return parse_write_result(resp)

    def _write_words(self, segment, start_address, data, debug=0):
        """Write multiple words (2 bytes signed integers).

        This function is a low-level function. It's used by ``write_xxx_words``.

        The segment where to write (INTERNAL, SYSTEM) is to specify.

        :param int segment: Segment where to write
        :param int start_address: First address to write at
        :param list[int] data: Signed words values to write
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: ``True`` if the writing succeeded
        :rtype: bool
        """
        data_bytes_2d = [w.to_bytes(2, byteorder="little", signed=True) for w in data]
        data_bytes = []
        for word_bytes in data_bytes_2d:
            data_bytes.extend(word_bytes)

        ok = self._write_objects(segment, 0x07, start_address, len(data), data_bytes, debug)
        return ok

    def write_internal_words(self, start_address, data, debug=0):
        """Write multiple words (2 bytes signed integers) in the internal memory (``%MW``).

        :param int start_address: First address to write at
        :param list[int] data: Signed words values to write
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: ``True`` if the writing succeeded
        :rtype: bool
        """
        ok = self._write_words(0x68, start_address, data, debug)
        return ok

    def write_system_words(self, start_address, data, debug=0):
        """Write multiple words (2 bytes signed integers) in the system memory (``%SW``).

        :param int start_address: First address to write at
        :param list[int] data: Signed words values to write
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: ``True`` if the writing succeeded
        :rtype: bool
        """
        ok = self._write_words(0x6A, start_address, data, debug)
        return ok

    def _write_dwords(self, segment, start_address, data, debug=0):
        """Write multiple double words (4 bytes signed integers).

        This function is a low-level function. It's used by ``write_xxx_dwords``.

        The segment where to write (INTERNAL, SYSTEM) is to specify.

        :param int segment: Segment where to write
        :param int start_address: First address to write at
        :param list[int] data: Signed words values to write
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: ``True`` if the writing succeeded
        :rtype: bool
        """
        data_bytes_2d = [w.to_bytes(4, byteorder="little", signed=True) for w in data]
        data_bytes = []
        for dword_bytes in data_bytes_2d:
            data_bytes.extend(dword_bytes)

        ok = self._write_objects(segment, 0x08, start_address, len(data), data_bytes, debug)
        return ok

    def write_internal_dwords(self, start_address, data, debug=0):
        """Write multiple double words (4 bytes signed integers) in the internal memory (``%MD``).

        .. WARNING::

            | Writing multiple ``DWORD``'s writes with a step of 2 addresses.
            | If I write 2 ``DWORD``'s starting at ``%MD0``, it will writes at ``[%MD0, %K2]``.

        :param int start_address: First address to write at
        :param list[int] data: Signed words values to write
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: ``True`` if the writing succeeded
        :rtype: bool
        """
        ok = self._write_dwords(0x68, start_address, data, debug)
        return ok

    #---------- Writing IO queries ----------
    def write_io_channel(self, xway_channel_address, obj_type, start_address, number, bits_values, words_values, debug=0):
        """**[NOT TESTED]** Write I/O channel (``%I``, ``%Q``, ``%IW``, ``%QW``).

        | The ``bits_values`` argument are the request bytes.
        | The ``words_values`` argument is a list of signed integer values.

        :param list[int] xway_channel_address: Bytes of the channel X-WAY address
        :param int obj_type: I/O object type
        :param int start_address: First address to write
        :param int number: Number of objects to write
        :param int bits_values: Values of bits
        :param list[int] words_values: Values of words
        :param bool debug: :doc:`Debug mode </debug_levels>`

        :returns: ``True`` if writing succeeded (see ``conversion.parse_write_io_channel_result``)
        :rtype: bool
        """
        number_bytes = number.to_bytes(2, byteorder="little", signed=False)
        address_bytes = start_address.to_bytes(2, byteorder="little", signed=False)

        unite_query = [0x48, self.category_code, *xway_channel_address, 1, obj_type, 0, *number_bytes, *address_bytes]
        unite_query.append(len(bits_values))
        unite_query.extend(bits_values)

        words_bytes = []
        for w in words_values:
            w_bytes = w.to_bytes(2, byteorder="little", signed=True)
            words_bytes.extend(w_bytes)
        
        words_length_bytes = len(words_values).to_bytes(2, byteorder="little", signed=False)
        unite_query.extend(words_length_bytes)
        unite_query.extend(words_bytes)

        r = self.run_unite(unite_query, text=f"WRITE_IO_CHANNEL Type={obj_type} @{start_address} N={number} Bits={bits_values} Words={words_values}", debug=debug)

        if not is_valid_response_code(WRITE_IO_CHANNEL, r[0]):
            raise UnexpectedUniteResponse(get_response_code(WRITE_IO_CHANNEL), r[0])

        return parse_write_io_channel_result(r[1:])