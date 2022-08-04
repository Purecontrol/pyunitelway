class UnitelwayError(Exception):
    def __init__(self, message):
        super().__init__(message)

class BadUnitelwayChecksum(UnitelwayError):
    def __init__(self, expected, got):
        super().__init__(self, f"Bad UNI-TELWAY checksum: expected {expected}, got {got}")

class RefusedUnitelwayMessage(UnitelwayError):
    def __init__(self):
        super().__init__("Refused UNI-TELWAY message (X-WAY code = 0x22). See Notion for more details")

class UniteRequestFailed(UnitelwayError):
    def __init__(self):
        super().__init__("UNI-TE request failed (response: 0xFD). Possible causes: bad request code, bad values, ... See Notion for more details")

class BadReadBitsNumberParam(ValueError):
    def __init__(self, number):
        super().__init__(f"Number has to be a multiple of 8 (it is {number})")

class UnexpectedUniteResponse(UnitelwayError):
    def __init__(self, expected, got):
        super().__init__(f"Expected 0x{expected:X}, got 0x{got:X}. Check that the UnitelwayClient's link address is not used by another slave station")

class UnexpectedObjectTypeResponse(UnexpectedUniteResponse):
    def __init__(self, expected, got):
        super().__init__(expected, got)