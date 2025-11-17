import re

test = '[1763335364.615064] 64 bytes from 169.254.63.82: icmp_seq=1 ttl=63 time=4.25 ms'
#test = 'Reply from 169.254.63.82: bytes=32 time=16ms TTL=64'

match = re.search(r'\[(\d+\.\d+)\].*?(\d+) bytes.*?icmp_seq=(\d+).*?ttl=(\d+).*?time=([\d.]+)', test)
if match:
    timestamp = match.group(1)  # 1763335364.615064
    num_bytes = match.group(2)  # 64
    sequence = match.group(3)   # 1
    ttl = match.group(4)        # 63
    time_ms = match.group(5)    # 4.25

pass