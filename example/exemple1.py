from pyunitelway import UnitelwayClient, constants

client = UnitelwayClient(2, 7, 0, 0xfe, 0, 0, 0)
client.connect_socket("192.168.0.97", 502, [0x55, 0xAA, 0x55, 0x00, 0x4B, 0x00, 0x0B, 0x56])
#client.connect_socket("10.156.5.66", 502, [0x55, 0xAA, 0x55, 0x00, 0x25, 0x80, 0x0B, 0xb0])

r = client.write_internal_dwords(0, [23, 0, -23452], True)
print("RES =", r)
