import os
import re
import sys
import time
import json
import math
import requests
import datetime
import subprocess
from statistics import mean
from typing import Optional

CLIENT_HALOW_IP = '169.254.1.1'
SERVER_HALOW_IP = '169.254.90.55'
UBUS_JSONRPC_URL = f'http://{CLIENT_HALOW_IP}/ubus'

BOARD_NAMES = ['Heltec,HT-HD01-V1', 'alfa-network,ahuc7292u']
RADIO_NAMES = ['wlan0', 'mesh0']

USERNAMES = ['root', 'admin']
PASSWORDS = ['heltec.org', 'admin']

UBUS_RETRY_LIMIT = 5
UBUS_REPORT_RATE = 0.1

IPERF3_TCP_TEST_COUNT = 6
IPERF3_TCP_TEST_DURATION_SEC = 30
IPERF3_TCP_TEST_WINDOWS = [[75, 75, 100, 100], [32, 28, 22]]

IPERF3_UDP_TEST_COUNT = 6
IPERF3_UDP_TEST_DURATION_SEC = 30
IPERF3_UDP_TEST_THROUGHPUTS = [[2.28, 5.3, 11.4, 14.8], [1.6, 2.8, 4.0]]

ICMP_PING_TEST_SAMPLES = 110
ICMP_PING_TEST_BATCH_SIZE = 10

NRC_TO_HALOW_CHANNEL = {
    # 1 MHz Bandwidth Channels
    1: 1,    # 902.5 MHz
    3: 3,    # 903.5 MHz
    5: 5,    # 904.5 MHz
    7: 7,    # 905.5 MHz
    9: 9,    # 906.5 MHz
    11: 11,  # 907.5 MHz
    36: 13,  # 908.5 MHz
    37: 15,  # 909.5 MHz
    38: 17,  # 910.5 MHz
    39: 19,  # 911.5 MHz
    40: 21,  # 912.5 MHz
    41: 23,  # 913.5 MHz
    42: 25,  # 914.5 MHz
    43: 27,  # 915.5 MHz
    44: 29,  # 916.5 MHz
    45: 31,  # 917.5 MHz
    46: 33,  # 918.5 MHz
    47: 35,  # 919.5 MHz
    48: 37,  # 920.5 MHz
    149: 39, # 921.5 MHz
    150: 41, # 922.5 MHz
    151: 43, # 923.5 MHz
    152: 45, # 924.5 MHz
    100: 47, # 925.5 MHz
    104: 49, # 926.5 MHz
    108: 51, # 927.5 MHz
    # 2 MHz Bandwidth Channels
    2: 2,    # 903.0 MHz
    6: 6,    # 905.0 MHz
    10: 10,  # 907.0 MHz
    153: 14, # 909.0 MHz
    154: 18, # 911.0 MHz
    155: 22, # 913.0 MHz
    156: 26, # 915.0 MHz
    157: 30, # 917.0 MHz
    158: 34, # 919.0 MHz
    159: 38, # 921.0 MHz
    160: 42, # 923.0 MHz
    161: 46, # 925.0 MHz
    112: 50, # 927.0 MHz
    # 4 MHz Bandwidth Channels
    8: 8,    # 906.0 MHz
    162: 16, # 910.0 MHz
    163: 24, # 914.0 MHz
    164: 32, # 918.0 MHz
    165: 40, # 922.0 MHz
    116: 48  # 926.0 MHz
}
CHANNEL_TO_BANDWIDTH = {
    1: 1,
    3: 1,
    5: 1,
    7: 1,
    9: 1,
    11: 1,
    13: 1,
    15: 1,
    17: 1,
    19: 1,
    21: 1,
    23: 1,
    25: 1,
    27: 1,
    29: 1,
    31: 1,
    33: 1,
    35: 1,
    37: 1,
    39: 1,
    41: 1,
    43: 1,
    45: 1,
    47: 1,
    49: 1,
    51: 1,
    2: 2,
    6: 2,
    10: 2,
    14: 2,
    18: 2,
    22: 2,
    26: 2,
    30: 2,
    34: 2,
    38: 2,
    42: 2,
    46: 2,
    50: 2,
    8: 4,
    16: 4,
    24: 4,
    32: 4,
    40: 4,
    48: 4,
    12: 8,
    28: 8,
    44: 8,
    20: 16
}

PROGRESS_SPIN = ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷']

def make_timestamp() -> str:
    curr_datetime = str(datetime.datetime.now()).split()
    return f'{curr_datetime[0]}_{curr_datetime[1][:8]}'

def get_session_token(id_counter: int) -> str:
    authentication_response = None
    for i in range(len(USERNAMES)):
        authentication_payload = {
            'jsonrpc': '2.0',
            'id': id_counter,
            'method': 'call',
            'params': [
                '00000000000000000000000000000000',
                'session',
                'login',
                {'username': USERNAMES[i], 'password': PASSWORDS[i]}
            ]
        }

        try:
            authentication_response = requests.post(UBUS_JSONRPC_URL, json=authentication_payload).json()
        except:
            print('ERROR: Failed to retrieve OpenWRT UBUS authentication token. Terminating.')
            sys.exit(-1)

        if authentication_response['result'][0] == 0:
            break

    if authentication_response is None:
        print('ERROR: Failed to retrieve OpenWRT UBUS authentication token. Terminating.')
        sys.exit(-1)

    return authentication_response['result'][1]['ubus_rpc_session']

def get_device(session_token: str, id_counter: int) -> str:
    get_devices_request = {
        'jsonrpc': '2.0',
        'id': id_counter,
        'method': 'call',
        'params': [ 
            session_token,
            'system', 
            'board',
            {}
        ]
    }

    retry_counter = 0
    peer_status_response = None
    while retry_counter < UBUS_RETRY_LIMIT:
        retry_counter += 1
        peer_status_response = requests.post(UBUS_JSONRPC_URL, json=get_devices_request).json()
        if peer_status_response['result'][0] == 0 and peer_status_response['result'][1]['board_name']:
            break
        
    if peer_status_response is None or not peer_status_response['result'][1]['board_name']:
        raise Exception('Invalid response from OpenWRT UBUS')

    return peer_status_response['result'][1]['board_name']

def _get_peer_stats_raw(session_token: str, device: str, id_counter: int) -> dict:
    peer_status_request = {
        'jsonrpc': '2.0',
        'id': id_counter,
        'method': 'call',
        'params': [ 
            session_token,
            'iwinfo', 
            'assoclist', 
            {'device': RADIO_NAMES[BOARD_NAMES.index(device)]}
        ] 
    }

    start = time.time()

    retry_counter = 0
    peer_status_response = None
    while retry_counter < UBUS_RETRY_LIMIT:
        retry_counter += 1
        peer_status_response = requests.post(UBUS_JSONRPC_URL, json=peer_status_request).json()
        if peer_status_response['result'][0] == 0 and peer_status_response['result'][1]['results'] and (peer_status_response['result'][1]['results'][0]['noise'] != 0 if device == BOARD_NAMES[0] else True):
            break

    # finish = (time.time() - start) * 1000
        
    if peer_status_response is None or peer_status_response['result'][0] != 0 or not peer_status_response['result'][1]['results']:
        raise Exception('Invalid response from OpenWRT UBUS')

    return peer_status_response['result'][1]['results'][0]
        
def get_channel_and_txpower(session_token: str, device: str, id_counter: int) -> tuple[int, int]:
    device_info_request = {
        'jsonrpc': '2.0',
        'id': id_counter,
        'method': 'call',
        'params': [ 
            session_token,
            'iwinfo', 
            'info', 
            {'device': RADIO_NAMES[BOARD_NAMES.index(device)]}
        ] 
    }

    device_info_response = None
    try:
        device_info_response = requests.post(UBUS_JSONRPC_URL, json=device_info_request).json()
    except:
        print('ERROR: Failed to query channel from OpenWRT UBUS. Terminating.')
        sys.exit(-1)

    if device_info_response['result'][0] != 0:
        print('ERROR: Failed to query channel from OpenWRT UBUS. Terminating.')
        sys.exit(-1)

    if device != BOARD_NAMES[1]:
        return (device_info_response['result'][1]['channel'], device_info_response['result'][1]['txpower'])
    else:
        return (NRC_TO_HALOW_CHANNEL[device_info_response['result'][1]['channel']], device_info_response['result'][1]['txpower'])

def get_peer_stats(session_token: str, device: str, id_counter: int) -> tuple:
    peer_stats_raw = _get_peer_stats_raw(session_token, device, id_counter)
    
    return (
        time.time_ns(),
        peer_stats_raw['signal'],
        peer_stats_raw['signal_avg'],
        peer_stats_raw['noise'] if peer_stats_raw['noise'] != 0 else -1,
        peer_stats_raw['rx']['mcs'] if 'mcs' in peer_stats_raw['rx'] else -1,
        peer_stats_raw['rx']['short_gi'] if 'short_gi'in peer_stats_raw['rx'] else -1,
        peer_stats_raw['tx']['mcs'] if 'mcs' in peer_stats_raw['tx'] else -1,
        peer_stats_raw['tx']['short_gi'] if 'short_gi' in peer_stats_raw['tx'] else -1
    )

def get_iperf3_throughput(bandwidth: int, device: str) -> str:
    return f'{IPERF3_UDP_TEST_THROUGHPUTS[BOARD_NAMES.index(device)][int(math.log(bandwidth, 2))]}M'

def get_iperf3_windows(bandwidth: int, device: str) -> str:
    return f'{IPERF3_TCP_TEST_WINDOWS[BOARD_NAMES.index(device)][int(math.log(bandwidth, 2))]}K'

def _write_out_stat_log_csv(path: str, stat_log: list) -> None:
    with open(f'{path}.csv', 'w') as file:
        file.write('timestamp,signal,signal_avg,noise_floor,rx_mcs,rx_short_gi,tx_mcs,tx_short_gi\n')
        for entry in stat_log:
            file.write(f'{entry[0]},{entry[1]},{entry[2]},{entry[3]},{entry[4]},{entry[5]},{entry[6]},{entry[7]}\n')

def write_out_iperf3_result_files(path: str, iperf3_results: str, stat_log: list) -> None:
    with open(f'{path}.json', 'w') as file:
        file.write(iperf3_results)
    _write_out_stat_log_csv(path, stat_log)
    
def write_out_ping_result_files(path: str, ping_stats: list, stat_log: list) -> None:
    with open(f'{path}_Pings.csv', 'w') as file:
        file.write('timestamp,bytes,sequence,ttl,time_ms\n')
        for entry in ping_stats:
            file.write(f'{entry[0]},{entry[1]},{entry[2]},{entry[3]},{entry[4]}\n')
        _write_out_stat_log_csv(path, stat_log)

def parse_ping_line(line: str) -> Optional[tuple]:
    match = re.search(r'\[(\d+\.\d+)\].*?(\d+) bytes.*?icmp_seq=(\d+).*?ttl=(\d+).*?time=([\d.]+)', line)
    return (match.group(1), match.group(2), match.group(3), match.group(4), match.group(5)) if match is not None else None

def main() -> None:
    session_token = get_session_token(0)

    id_counter = 0
    device = get_device(session_token, id_counter := id_counter + 1)
    channel, txpower = get_channel_and_txpower(session_token, device, id_counter := id_counter + 1)
    bandwidth = CHANNEL_TO_BANDWIDTH[channel]
    
    directory = f'./results/{make_timestamp()}_{bandwidth}MHz_CH{channel}_{txpower}dBM_halow_test'

    os.mkdir(directory)

    # Perform UDP testing.
    iperf3_udp_parameters = [
        'iperf3', '-J', '-u',
        '-c', SERVER_HALOW_IP,
        '-t', str(IPERF3_UDP_TEST_DURATION_SEC),
        '-b', get_iperf3_throughput(bandwidth, device),
        '-i', str(UBUS_REPORT_RATE)
    ]

    i = 0
    previous_udp_bitrates = []
    previous_udp_bitrate = 'N/A'
    while i < IPERF3_UDP_TEST_COUNT:
        iperf3_tcp_process = subprocess.Popen(iperf3_udp_parameters, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, pipesize=1024**2)

        stat_log = []
        spinner_index = 0
        while iperf3_tcp_process.poll() == None:
            start_time = time.time()

            stat_log.append(get_peer_stats(session_token, device, id_counter := id_counter + 1))
            rssi = stat_log[-1][1]
            noise = stat_log[-1][3]
            snr = rssi - noise

            if device != BOARD_NAMES[1]:
                print(f'\033[?7l\033[2K\033[?25l{PROGRESS_SPIN[spinner_index]} Performing UDP test [{i + 1}/{IPERF3_TCP_TEST_COUNT}] (RSSI: {rssi}dBm, Noise Floor: {noise}dBm, SNR: {snr}dB, Previous Bitrate: {previous_udp_bitrate})', end='\033[?7h\r')
            else:
                print(f'\033[?7l\033[2K\033[?25l{PROGRESS_SPIN[spinner_index]} Performing UDP test [{i + 1}/{IPERF3_TCP_TEST_COUNT}] (RSSI: {rssi}dBm, Previous Bitrate: {previous_udp_bitrate})', end='\033[?7h\r')
            spinner_index = (spinner_index + 1) % len(PROGRESS_SPIN)

            delta_time = time.time() - start_time
            time.sleep(max(0, UBUS_REPORT_RATE - delta_time))

        if iperf3_tcp_process.returncode != 0:
            continue

        iperf3_results = iperf3_tcp_process.communicate()[0]

        # Extract average bitrate from test that had just occured.
        results_json = json.loads(iperf3_results)
        previous_udp_bitrates.append(results_json['end']['sum_received']['bits_per_second'] / 1000.0)
        previous_udp_bitrate = f'{previous_udp_bitrates[-1]:.2f} Kbit/s'

        write_out_iperf3_result_files(f'{directory}/Iperf3_UDP_Test_{i + 1}', iperf3_results, stat_log)

        i += 1

    if IPERF3_UDP_TEST_COUNT > 0:
        print(f'\033[2K✓ UDP Testing Complete (Average Bitrate: {mean(previous_udp_bitrates):.2f} Kbit/s)')

    # Perform TCP testing.
    iperf3_tcp_parameters = [
        'iperf3', '-J',
        '-c', SERVER_HALOW_IP,
        '-t', str(IPERF3_TCP_TEST_DURATION_SEC),
        '-w', get_iperf3_windows(bandwidth, device),
        '-i', str(UBUS_REPORT_RATE)
    ]

    i = 0
    previous_tcp_rtt = 'N/A'
    previous_tcp_bitrate = 'N/A'
    previous_tcp_rtts = []
    previous_tcp_bitrates = []
    while i < IPERF3_TCP_TEST_COUNT:
        iperf3_tcp_process = subprocess.Popen(iperf3_tcp_parameters, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, pipesize=1024**2)

        stat_log = []
        spinner_index = 0
        while iperf3_tcp_process.poll() == None:
            start_time = time.time()

            stat_log.append(get_peer_stats(session_token, device, id_counter := id_counter + 1))
            rssi = stat_log[-1][1]
            noise = stat_log[-1][3]
            snr = rssi - noise

            if device != BOARD_NAMES[1]:
                print(f'\033[?7l\033[2K\033[?25l{PROGRESS_SPIN[spinner_index]} Performing TCP test [{i + 1}/{IPERF3_TCP_TEST_COUNT}] (RSSI: {rssi}dBm, Noise Floor: {noise}dBm, SNR: {snr}dB, Previous Bitrate: {previous_tcp_bitrate}, Previous Average RTT: {previous_tcp_rtt})', end='\033[?7h\r')
            else:
                print(f'\033[?7l\033[2K\033[?25l{PROGRESS_SPIN[spinner_index]} Performing TCP test [{i + 1}/{IPERF3_TCP_TEST_COUNT}] (RSSI: {rssi}dBm, Previous Bitrate: {previous_tcp_bitrate}, Previous Average RTT: {previous_tcp_rtt})', end='\033[?7h\r')
            spinner_index = (spinner_index + 1) % len(PROGRESS_SPIN)

            delta_time = time.time() - start_time
            time.sleep(max(0, UBUS_REPORT_RATE - delta_time))

        if iperf3_tcp_process.returncode != 0:
            continue

        iperf3_results = iperf3_tcp_process.communicate()[0]

        # Extract average bitrate from test that had just occured.
        results_json = json.loads(iperf3_results)

        previous_tcp_bitrates.append(results_json['end']['sum_received']['bits_per_second'] / 1000.0)
        previous_tcp_bitrate = f'{previous_tcp_bitrates[-1]:.2f} Kbit/s'

        previous_tcp_rtts.append(results_json['end']['streams'][0]['sender']['mean_rtt'] / 1000.0)
        previous_tcp_rtt = f'{previous_tcp_rtts[-1]:.2f}ms'

        write_out_iperf3_result_files(f'{directory}/Iperf3_TCP_Test_{i + 1}', iperf3_results, stat_log)

        i += 1

    if IPERF3_TCP_TEST_COUNT > 0:
        print(f'\033[2K✓ TCP Testing Complete (Average Bitrate: {mean(previous_tcp_bitrates):.2f} Kbit/s, Average RTT: {mean(previous_tcp_rtts):.2f}ms)')

    # Perform latency testing.
    ping_parameters = [
        'ping', '-D', '-4',
        '-c', str(ICMP_PING_TEST_BATCH_SIZE),
        SERVER_HALOW_IP
    ]

    i = 0
    stat_log = []
    ping_stats = []
    latency_sum = 0.0
    average_latency = 'N/A'
    while i < ICMP_PING_TEST_SAMPLES:
        ping_process = subprocess.Popen(ping_parameters, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, pipesize=1024**2)

        spinner_index = 0
        temp_stat_log = []
        while ping_process.poll() == None:
            start_time = time.time()

            temp_stat_log.append(get_peer_stats(session_token, device, id_counter := id_counter + 1))
            rssi = temp_stat_log[-1][1]
            noise = temp_stat_log[-1][3]
            snr = rssi - noise
            
            if device != BOARD_NAMES[1]:
                print(f'\033[?7l\033[2K\033[?25l{PROGRESS_SPIN[spinner_index]} Gathering ICMP Samples [{i}/{ICMP_PING_TEST_SAMPLES}] (RSSI: {rssi}dBm, Noise Floor: {noise}dBm, SNR: {snr}dB, Average Latency: {average_latency})', end='\033[?7h\r')
            else:
                print(f'\033[?7l\033[2K\033[?25l{PROGRESS_SPIN[spinner_index]} Gathering ICMP Samples [{i}/{ICMP_PING_TEST_SAMPLES}] (RSSI: {rssi}dBm, Average Latency: {average_latency})', end='\033[?7h\r')
            spinner_index = (spinner_index + 1) % len(PROGRESS_SPIN)

            delta_time = time.time() - start_time
            time.sleep(max(0, UBUS_REPORT_RATE - delta_time))

        lines = ping_process.communicate()[0].split('\n')[1:-5]
        if len(lines) != ICMP_PING_TEST_BATCH_SIZE:
            continue

        stat_log += temp_stat_log

        for line in lines:
            ping_stats.append(parse_ping_line(line))
        for x in range(1, ICMP_PING_TEST_BATCH_SIZE + 1):
            latency_sum += float(ping_stats[-x][4])
        
        average_latency = f'{(latency_sum / len(ping_stats)):.2f}ms'

        i += ICMP_PING_TEST_BATCH_SIZE

    write_out_ping_result_files(f'{directory}/Iperf3_ICMP_Test', ping_stats, stat_log)

    print(f'\033[2K✓ ICMP Testing Complete (Average Latency: {average_latency})')

    pass

if __name__ == '__main__':
    main()