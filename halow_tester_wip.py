import sys
import time
import socket
import argparse
import threading
import ipaddress
import keyboard
import concurrent.futures
from typing import Optional

PROGRESS_SPIN = ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷']

CANCEL_EVENT = threading.Event()

def connection_loop(ip_addr: ipaddress.IPv4Address, port: int) -> Optional[socket.socket]:
    while not CANCEL_EVENT.is_set():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.1)
        try:
            sock.connect((str(ip_addr), 80))
            return sock
        except TimeoutError:
            sock.close()
            pass

    return None


def client_operation(ip_addr: ipaddress.IPv4Address, settings_file: str) -> None:
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    socket_future = executor.submit(connection_loop, ip_addr, 80)
    
    counter: int = 0
    while not (CANCEL_EVENT.is_set() and socket_future.done()):
        print(f'\033[?25l{PROGRESS_SPIN[counter]} Waiting for connection from server. (Press \'X\' to cancel)', end='\r')
        counter = (counter + 1) % len(PROGRESS_SPIN)
        time.sleep(0.1)

    print(f'\n{socket_future.done()}')

    pass
    

def server_operation() -> None:
    pass

def main() -> None:
    parser = argparse.ArgumentParser('Halow Tester', 'Automated and streamlined HaLow testing and data collection.')
    parser.add_argument('ip_addr', type=str, help='IPV4 address of the client or server.')
    parser.add_argument('mode', type=str, choices=['CLIENT', 'SERVER'])
    parser.add_argument('-f', '--settings-file', type=str)

    args = parser.parse_args(['192.168.1.1', 'CLIENT'])

    ip_addr: Optional[ipaddress.IPv4Address] = None
    try:
        temp = ipaddress.ip_address(args.ip_addr)
        if not isinstance(temp, ipaddress.IPv4Address):
            raise ValueError
        else:
            ip_addr = temp
    except ValueError:
        print('Error: Provided IP address is not a valid IPV4 address. Terminating.')
        sys.exit(-1)

    keyboard.on_press_key('x', lambda _ : CANCEL_EVENT.set())

    if args.mode == 'CLIENT':
        client_operation(ip_addr, args.settings_file)

if __name__ == '__main__':
    main()