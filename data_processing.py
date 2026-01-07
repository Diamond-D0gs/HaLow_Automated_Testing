import os
import json
import pandas
import matplotlib.pyplot as plt

INPUT_DATA_DIRECTORY = '/home/gabriel/HaLow_Automated_Testing/results/old/1240_feet/2025-11-25_15:27:11_8MHz_CH12_21dBM_halow_test'
INPUT_DATA_FILE_NAME = ['UDP', 'TCP']

output_dir = './graphs/'
output_dir += '620_feet/' if INPUT_DATA_DIRECTORY.find('620_feet') != -1 else '1240_feet/'
output_dir += INPUT_DATA_DIRECTORY[INPUT_DATA_DIRECTORY.find('MHz')-1:]

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

for type in INPUT_DATA_FILE_NAME:
    is_tcp = type == 'TCP'
    for i in range(1, 6):
        with open(f'{INPUT_DATA_DIRECTORY}/Iperf3_{type}_Test_{i}.json', 'r') as file:
            data = json.load(file)

        iperf3_start_time = data['start']['timestamp']['timesecs']

        iperf3_pandas = []
        running_timestamp = iperf3_start_time
        for entry in data['intervals']:
            stream = entry['streams'][0]
            iperf3_pandas.append({
                'timestamp': running_timestamp,
                'bytes': stream['bytes'],
                'retransmits': stream['retransmits'] if is_tcp else 0,
                'snd_cwnd': stream['snd_cwnd'] if is_tcp else 0,
                'snd_wnd': stream['snd_wnd'] if is_tcp else 0,
                'rtt': stream['rtt'] if is_tcp else 0,
                'rttvar': stream['rttvar'] if is_tcp else 0,
                'pmtu': stream['pmtu'] if is_tcp else 0,
            })

            running_timestamp += stream['seconds']

        iperf3_dataframe = pandas.DataFrame(iperf3_pandas)
        iperf3_dataframe['timestamp'] = pandas.to_datetime(iperf3_dataframe['timestamp'], unit='s')
        iperf3_dataframe = iperf3_dataframe.set_index('timestamp')
        iperf3_dataframe = iperf3_dataframe.resample('1s').agg({
            'bytes': 'sum',        # Summing bytes gives you the total throughput for that second
            'retransmits': 'sum',  # Total retransmits in that second
            'snd_cwnd': 'mean',    # Average congestion window size (or use 'max' for peak)
            'rtt': 'mean',         # Average Round Trip Time
            'rttvar': 'mean',      # Average Jitter
            'pmtu': 'max'          # Constant value, max preserves it
        })
        iperf3_dataframe['kbps'] = (iperf3_dataframe['bytes'] * 8) / 1000.0

        radio_dataframe = pandas.read_csv(f'{INPUT_DATA_DIRECTORY}/Iperf3_{type}_Test_{i}.csv')
        radio_dataframe['timestamp'] = pandas.to_datetime(radio_dataframe['timestamp'], unit='ns')
        radio_dataframe = radio_dataframe.set_index('timestamp')

        # Throughput vs Signal Strength (raw data over 30s iperf window)
        iperf_start = iperf3_dataframe.index[0]
        iperf_end = iperf3_dataframe.index[-1]
        
        # Filter radio data to iperf test window
        radio_filtered = radio_dataframe[(radio_dataframe.index >= iperf_start) & (radio_dataframe.index <= iperf_end)]
        
        # Calculate relative time for both datasets
        iperf_relative_time = (iperf3_dataframe.index - iperf_start).total_seconds()
        radio_relative_time = (radio_filtered.index - iperf_start).total_seconds()

        fig0, fig0_ax1 = plt.subplots(figsize=(10, 6))

        fig0_ax1.set_xlabel('Time (seconds)')
        fig0_ax1.set_ylabel('Throughput (kbps)', color='tab:orange')
        fig0_ax1.plot(iperf_relative_time, iperf3_dataframe['kbps'], color='tab:orange', label='Throughput')
        fig0_ax1.tick_params(axis='y', labelcolor='tab:orange')
        fig0_ax1.ticklabel_format(style='plain', axis='y', useOffset=False)
        fig0_ax1.grid(True, linestyle='--', alpha=0.5)

        fig0_ax2 = fig0_ax1.twinx()
        fig0_ax2.set_ylabel('RSSI (dBm)', color='tab:blue')
        fig0_ax2.plot(radio_relative_time, radio_filtered['signal'], color='tab:blue', alpha=0.7, label='RSSI')
        fig0_ax2.tick_params(axis='y', labelcolor='tab:blue')

        plt.title(f'Throughput vs Signal Strength - {type} - Test {i}')
        fig0.tight_layout()
        plt.savefig(f'{output_dir}/throughput_vs_rssi_{type}_{i}.png')
        plt.close(fig0)

        # Throughput vs MCS and Short Guard Interval
        fig1, fig1_ax1 = plt.subplots(figsize=(10, 6))

        fig1_ax1.set_xlabel('Time (seconds)')
        fig1_ax1.set_ylabel('Throughput (kbps)', color='tab:orange')
        fig1_ax1.plot(iperf_relative_time, iperf3_dataframe['kbps'], color='tab:orange', label='Throughput')
        fig1_ax1.tick_params(axis='y', labelcolor='tab:orange')
        fig1_ax1.ticklabel_format(style='plain', axis='y', useOffset=False)
        fig1_ax1.grid(True, linestyle='--', alpha=0.5)

        fig1_ax2 = fig1_ax1.twinx()
        fig1_ax2.set_ylabel('MCS Index / Short GI')
        fig1_ax2.set_ylim(-0.5, 7.5)
        fig1_ax2.set_yticks(range(8))
        
        # Plot TX MCS as stepped line
        fig1_ax2.step(radio_relative_time, radio_filtered['tx_mcs'], color='tab:blue', 
                      where='post', label='TX MCS', linewidth=1.5)
        
        # Plot Short GI as stepped line (True=1, False=0)
        short_gi_numeric = radio_filtered['tx_short_gi'].astype(int)
        fig1_ax2.step(radio_relative_time, short_gi_numeric, color='tab:green', 
                      where='post', label='Short GI', linewidth=1.5, linestyle='--')

        # Combined legend for right axis
        fig1_ax2.legend(loc='upper right')

        plt.title(f'Throughput vs MCS and Short GI - {type} - Test {i}')
        fig1.tight_layout()
        plt.savefig(f'{output_dir}/throughput_vs_mcs_sgi_{type}_{i}.png')
        plt.close(fig1)

        # RSSI vs MCS and Short Guard Interval
        fig2, fig2_ax1 = plt.subplots(figsize=(10, 6))

        fig2_ax1.set_xlabel('Time (seconds)')
        fig2_ax1.set_ylabel('RSSI (dBm)', color='tab:blue')
        fig2_ax1.plot(radio_relative_time, radio_filtered['signal'], color='tab:blue', alpha=0.7, label='RSSI')
        fig2_ax1.tick_params(axis='y', labelcolor='tab:blue')
        fig2_ax1.grid(True, linestyle='--', alpha=0.5)

        fig2_ax2 = fig2_ax1.twinx()
        fig2_ax2.set_ylabel('MCS Index / Short GI')
        fig2_ax2.set_ylim(-0.5, 7.5)
        fig2_ax2.set_yticks(range(8))

        # Plot TX MCS as stepped line
        fig2_ax2.step(radio_relative_time, radio_filtered['tx_mcs'], color='tab:orange',
                      where='post', label='TX MCS', linewidth=1.5)

        # Plot Short GI as stepped line (True=1, False=0)
        short_gi_numeric = radio_filtered['tx_short_gi'].astype(int)
        fig2_ax2.step(radio_relative_time, short_gi_numeric, color='tab:green',
                      where='post', label='Short GI', linewidth=1.5, linestyle='--')

        # Combined legend for right axis
        fig2_ax2.legend(loc='upper right')

        plt.title(f'RSSI vs MCS and Short GI - {type} - Test {i}')
        fig2.tight_layout()
        plt.savefig(f'{output_dir}/rssi_vs_mcs_sgi_{type}_{i}.png')
        plt.close(fig2)