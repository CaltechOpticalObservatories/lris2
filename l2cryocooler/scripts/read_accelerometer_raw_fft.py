"""
TMS Accelerometer Reader

Reads acceleration data from TMS USB accelerometers and displays FFT spectrum.
"""
import argparse
import datetime
import os
import threading
import numpy as np
import sounddevice as sd
import matplotlib.pyplot as plt
from scipy import signal
from scipy.integrate import cumulative_trapezoid
from adjustText import adjust_text


def find_devices():
    """
    # returns an array of TMS compatible devices with associated information
    #
    # Returns dictionary items per device
    #   "device"        - Device number to be used by SoundDevice stream
    #   "model"         - Model number
    #   "serial_number" - Serial number
    #   "date"          - Calibration date
    #   "format"        - format of data from device, 0 - acceleration, 1 - voltage
    #   "sensitivity_int - Raw sensitivity as integer counts/EU ie Volta or m/s^2
    #   "scale"         - sensitiivty scaled to float for use with a
    #                     -1.0 to 1.0 scaled data.  Format returned with
    #                     'float32' format to SoundDevice stream.
    """
    
    # The Modal Shop model number substrings
    models=["485B", "333D", "633A", "SDC0"]
    
    api_num=0
    
    # Return all available audio inputs
    devices = sd.query_devices()
    dev_info = []
    dev_num=0
    # Iterate through available devices and find ones named with a TMS model.
    # Note this returns multiple instances of the same device, because there
    # are different audio API's available.
    for device in devices:
        if (device['hostapi'] == api_num):
            name = device['name']
            match = next((x for x in models if x in name), False)
            if match is not False:
                loc = name.find(match)
                model = name[loc:loc+6] # Extract the model
                fmt = name[loc+7:loc+8] # Extract the format of data
                serialnum = name[loc+8:loc+14]  # Extract the serial number
                # parse devices that are voltage
                if fmt == "2" or fmt == '3':
                    form = 1    # Voltage
                    # Extract the sensitivity
                    sens = [int(name[loc+14:loc+21]), int(name[loc+21:loc+28])]
                    if fmt == "3":  # 50mV reference for format 3
                        sens[0] *= 20 # Convert to 1V reference
                        sens[1] *= 20 
                    scale = np.array([8388608.0/sens[0],
                                      8388608.0/sens[1]],
                                     dtype='float32') # scale to volts
                    date = datetime.datetime.strptime(name[loc+28:loc+34], '%y%m%d') # Isolate the calibration date from the fullname string
                elif fmt == "1":
                    # These devices are acceleration
                    form = 0
                    # Extract the sensitivity
                    sens = [int(name[loc+14:loc+19]), int(name[loc+19:loc+24])]
                    scale = np.array([855400.0/sens[0],
                                      855400.0/sens[1]],
                                      dtype='float32') # scale to m/s²
                    date = datetime.datetime.strptime(name[loc+24:loc+30], '%y%m%d') # Isolate the calibration date from the fullname string
                else:
                    print("Expecting 1, 2, or 3 format")
                dev_info.append({"device":dev_num,\
                                 "model":model,\
                                 "serial_number":serialnum,\
                                 "date":date,\
                                 "format":form,\
                                 "sensitivity_int":sens,\
                                 "scale":scale,\
                                 })
        dev_num += 1
    if len(dev_info) == 0:
        print("No compatible devices found")
    return dev_info


def read_accelerometer(device_info, duration=5.0, sample_rate=48000):
    """Read acceleration data from the TMS device.

    Args:
        device_info: Device dictionary from find_devices()
        duration: Recording duration in seconds
        sample_rate: Sample rate in Hz (default 48000)

    Returns:
        Tuple of (time_array, channel1_data, channel2_data) in m/s²
    """
    device_index = device_info['device']
    scale = device_info['scale']

    # Record audio data from the device
    data = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=2,
        dtype='float32',
        device=device_index
    )
    sd.wait()  # Wait for recording to complete

    # Scale the data to m/s² (or volts depending on device format)
    channel1 = data[:, 0] * scale[0]
    channel2 = data[:, 1] * scale[1]

    # Create time array
    time_array = np.linspace(0, duration, len(channel1))

    return time_array, channel1, channel2


def highpass_filter(data, cutoff=1.0, sample_rate=48000, order=2):
    """Apply a highpass filter to remove DC offset and low-frequency drift.

    Args:
        data: Input signal
        cutoff: Cutoff frequency in Hz
        sample_rate: Sample rate in Hz
        order: Filter order

    Returns:
        Filtered signal
    """
    nyquist = sample_rate / 2
    normalized_cutoff = cutoff / nyquist
    sos = signal.butter(order, normalized_cutoff, btype='high', output='sos')
    return signal.sosfiltfilt(sos, data)


def integrate_signal(data, dt, sample_rate=48000):
    """Integrate signal using cumulative trapezoid with highpass filter to remove drift.

    Args:
        data: Input signal
        dt: Time step
        sample_rate: Sample rate in Hz

    Returns:
        Integrated signal with drift removed
    """
    integrated = cumulative_trapezoid(data, dx=dt, initial=0)
    return highpass_filter(integrated, cutoff=1.0, sample_rate=sample_rate)


# Colors for different devices
DEVICE_COLORS = ['#1f77b4', '#ff7f0e']  # Blue, Orange


def calculate_fft(accel_data, sample_rate=48000, num_bins=4097):
    """Calculate FFT amplitude spectrum for acceleration and displacement with binning.

    Args:
        accel_data: Acceleration data array in m/s²
        sample_rate: Sample rate in Hz
        num_bins: Number of frequency bins for output (default 4097)

    Returns:
        Dictionary with:
            - frequencies: Frequency array in Hz
            - accel_amp: Acceleration amplitude spectrum in m/s²
            - disp_amp: Displacement amplitude spectrum in µm
    """
    dt = 1.0 / sample_rate
    n = len(accel_data)
    raw_frequencies = np.fft.rfftfreq(n, dt)

    # Acceleration FFT
    accel_fft = np.fft.rfft(accel_data)
    raw_accel_amp = 2.0 * np.abs(accel_fft) / n

    # Displacement FFT (double integrate acceleration)
    velocity = integrate_signal(accel_data, dt, sample_rate)
    displacement = integrate_signal(velocity, dt, sample_rate)
    displacement_um = displacement * 1e6  # Convert to microns

    disp_fft = np.fft.rfft(displacement_um)
    raw_disp_amp = 2.0 * np.abs(disp_fft) / n

    # Bin the FFT data using median for smoothing
    max_freq = raw_frequencies[-1]
    bin_edges = np.linspace(0, max_freq, num_bins + 1)
    frequencies = (bin_edges[:-1] + bin_edges[1:]) / 2  # Bin centers

    accel_amp = np.zeros(num_bins)
    disp_amp = np.zeros(num_bins)

    for i in range(num_bins):
        mask = (raw_frequencies >= bin_edges[i]) & (raw_frequencies < bin_edges[i + 1])
        if np.any(mask):
            accel_amp[i] = np.median(raw_accel_amp[mask])
            disp_amp[i] = np.median(raw_disp_amp[mask])
        else:
            # Interpolate if no samples in bin
            accel_amp[i] = np.interp(frequencies[i], raw_frequencies, raw_accel_amp)
            disp_amp[i] = np.interp(frequencies[i], raw_frequencies, raw_disp_amp)

    return {
        'frequencies': frequencies,
        'accel_amp': accel_amp,
        'disp_amp': disp_amp
    }


def save_calibration(fft_data_list, serial_numbers, filepath='calibration.npz'):
    """Save calibration FFT data to a file.

    Args:
        fft_data_list: List of FFT data dictionaries from calculate_fft()
        serial_numbers: List of device serial numbers
        filepath: Path to save calibration file
    """
    cal_data = {}
    for serial, fft_data in zip(serial_numbers, fft_data_list):
        cal_data[f'{serial}_frequencies'] = fft_data['frequencies']
        cal_data[f'{serial}_accel_amp'] = fft_data['accel_amp']
        cal_data[f'{serial}_disp_amp'] = fft_data['disp_amp']
    cal_data['serial_numbers'] = np.array(serial_numbers, dtype=str)
    np.savez(filepath, **cal_data)
    print(f"Calibration data saved to {filepath}")


def load_calibration(filepath='calibration.npz'):
    """Load calibration FFT data from a file.

    Args:
        filepath: Path to calibration file

    Returns:
        Dictionary mapping serial numbers to FFT data dictionaries,
        or None if file doesn't exist
    """
    if not os.path.exists(filepath):
        return None

    data = np.load(filepath, allow_pickle=True)
    serial_numbers = data['serial_numbers']

    cal_data = {}
    for serial in serial_numbers:
        cal_data[serial] = {
            'frequencies': data[f'{serial}_frequencies'],
            'accel_amp': data[f'{serial}_accel_amp'],
            'disp_amp': data[f'{serial}_disp_amp']
        }
    return cal_data


def plot_fft(fft_data_list, serial_numbers, calibration_data=None, num_peaks=3):
    """Plot FFT amplitude spectrum of acceleration and displacement data with peak detection.

    Args:
        fft_data_list: List of FFT data dictionaries from calculate_fft()
        serial_numbers: List of device serial numbers
        calibration_data: Optional dict of calibration data to subtract (from load_calibration)
        num_peaks: Number of top peaks to label per device

    Returns:
        matplotlib figure
    """
    # Create figure with 2 subplots
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))

    # Track min/max for y-axis limits
    accel_amp_min, accel_amp_max = float('inf'), 0
    disp_amp_min, disp_amp_max = float('inf'), 0

    # Collect text annotations for adjust_text
    accel_texts = []
    disp_texts = []

    for i, (fft_data, serial) in enumerate(zip(fft_data_list, serial_numbers)):
        color = DEVICE_COLORS[i % len(DEVICE_COLORS)]

        frequencies = fft_data['frequencies']
        accel_amp = fft_data['accel_amp'].copy()
        disp_amp = fft_data['disp_amp'].copy()

        # Subtract calibration if available for this device
        if calibration_data and serial in calibration_data:
            cal = calibration_data[serial]
            # Check if frequency bins match exactly
            if len(frequencies) == len(cal['frequencies']) and np.allclose(frequencies, cal['frequencies']):
                # Bins match - direct use
                cal_accel = cal['accel_amp'].copy()
                cal_disp = cal['disp_amp'].copy()
            else:
                # Bins differ - interpolate calibration data
                print(f"Warning: Frequency bins differ for {serial} "
                      f"(measurement: {len(frequencies)}, calibration: {len(cal['frequencies'])})")
                cal_accel = np.interp(frequencies, cal['frequencies'], cal['accel_amp'])
                cal_disp = np.interp(frequencies, cal['frequencies'], cal['disp_amp'])

            # Smooth the calibration data to reduce noise artifacts
            smooth_window = 15
            cal_accel_smooth = np.convolve(cal_accel, np.ones(smooth_window)/smooth_window, mode='same')
            cal_disp_smooth = np.convolve(cal_disp, np.ones(smooth_window)/smooth_window, mode='same')

            # Subtract smoothed calibration, clip to small floor for log display
            noise_floor = 1e-9
            accel_amp = np.maximum(accel_amp - cal_accel_smooth, noise_floor)
            disp_amp = np.maximum(disp_amp - cal_disp_smooth, noise_floor)

        # Update y-axis bounds (only for frequencies in 10-200 Hz range)
        freq_mask = (frequencies >= 10.0) & (frequencies <= 200.0)
        accel_amp_min = min(accel_amp_min, accel_amp[freq_mask].min())
        accel_amp_max = max(accel_amp_max, accel_amp[freq_mask].max())

        axes[0].loglog(frequencies, accel_amp, color=color, linewidth=0.8, label=serial)

        # Find and label peaks using prominence (in 10-200 Hz range)
        min_freq_idx = np.searchsorted(frequencies, 10.0)
        max_freq_idx = np.searchsorted(frequencies, 200.0)
        search_region = accel_amp[min_freq_idx:max_freq_idx]
        peak_indices, properties = signal.find_peaks(
            search_region,
            prominence=np.median(search_region) * 0.5
        )
        peak_indices = peak_indices + min_freq_idx

        if len(peak_indices) > 0:
            prominences = properties['prominences']
            sorted_idx = np.argsort(prominences)[::-1]
            top_peak_indices = peak_indices[sorted_idx[:num_peaks]]

            for idx in top_peak_indices:
                freq = frequencies[idx]
                amp = accel_amp[idx]
                axes[0].plot(freq, amp, 'v', color=color, markersize=8)
                txt = axes[0].text(freq, amp, f'{freq:.1f} Hz, {amp:.4f} m/s²',
                                   fontsize=8, color=color, fontweight='bold')
                accel_texts.append(txt)

        # Update y-axis bounds for displacement (only for frequencies in 10-200 Hz range)
        disp_amp_min = min(disp_amp_min, disp_amp[freq_mask].min())
        disp_amp_max = max(disp_amp_max, disp_amp[freq_mask].max())

        axes[1].loglog(frequencies, disp_amp, color=color, linewidth=0.8, label=serial)

        # Find and label peaks using prominence (in 10-200 Hz range)
        disp_search_region = disp_amp[min_freq_idx:max_freq_idx]
        peak_indices, properties = signal.find_peaks(
            disp_search_region,
            prominence=np.median(disp_search_region) * 0.5
        )
        peak_indices = peak_indices + min_freq_idx

        if len(peak_indices) > 0:
            prominences = properties['prominences']
            sorted_idx = np.argsort(prominences)[::-1]
            top_peak_indices = peak_indices[sorted_idx[:num_peaks]]

            for idx in top_peak_indices:
                freq = frequencies[idx]
                amp = disp_amp[idx]
                axes[1].plot(freq, amp, 'v', color=color, markersize=8)
                if amp >= 0.1:
                    amp_str = f'{amp:.2f} µm'
                else:
                    amp_str = f'{amp:.3f} µm'
                txt = axes[1].text(freq, amp, f'{freq:.1f} Hz, {amp_str}',
                                   fontsize=8, color=color, fontweight='bold')
                disp_texts.append(txt)

    # Configure acceleration subplot
    title_suffix = " (calibrated)" if calibration_data else ""
    axes[0].set_xlabel('Frequency (Hz)', fontsize=11)
    axes[0].set_ylabel('Amplitude (m/s²)', fontsize=11)
    axes[0].set_title(f'Acceleration FFT Spectrum{title_suffix}', fontsize=12)
    axes[0].set_xlim(10, 200)
    accel_ylim_min = max(accel_amp_min * 0.5, 1e-10)
    axes[0].set_ylim(accel_ylim_min, accel_amp_max * 2)
    axes[0].grid(True, which='both', alpha=0.3)
    axes[0].legend(loc='upper right', fontsize=9)

    # Configure displacement subplot
    axes[1].set_xlabel('Frequency (Hz)', fontsize=11)
    axes[1].set_ylabel('Amplitude (µm)', fontsize=11)
    axes[1].set_title(f'Displacement FFT Spectrum{title_suffix}', fontsize=12)
    axes[1].set_xlim(10, 200)
    disp_ylim_min = max(disp_amp_min * 0.5, 1e-10)
    axes[1].set_ylim(disp_ylim_min, disp_amp_max * 2)
    axes[1].grid(True, which='both', alpha=0.3)
    axes[1].legend(loc='upper right', fontsize=9)

    # Adjust text labels to avoid overlap
    if accel_texts:
        adjust_text(accel_texts, ax=axes[0], arrowprops=dict(arrowstyle='-', color='gray', lw=0.5))
    if disp_texts:
        adjust_text(disp_texts, ax=axes[1], arrowprops=dict(arrowstyle='-', color='gray', lw=0.5))

    plt.tight_layout()
    return fig


def record_from_devices(devices, duration=1.0):
    """Record from multiple devices simultaneously using threads.

    Args:
        devices: List of device info dictionaries
        duration: Recording duration in seconds

    Returns:
        Tuple of (time_array, data_list) where data_list has one array per device
    """
    results = [None] * len(devices)

    def record_device(index, dev):
        t, ch1, _ = read_accelerometer(dev, duration=duration)
        results[index] = (t, ch1)

    threads = []
    for i, dev in enumerate(devices):
        thread = threading.Thread(target=record_device, args=(i, dev))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    t = results[0][0]
    data_list = [result[1] for result in results]
    return t, data_list


def run_continuous(devices, serial_numbers, sample_rate=48000, smooth=False, decay=0.7):
    """Run continuous FFT display mode.

    Args:
        devices: List of device info dictionaries
        serial_numbers: List of serial number strings
        sample_rate: Sample rate in Hz
        smooth: Use exponential moving average on FFT spectra for smoother display
        decay: Decay factor for EMA (0-1, higher = more smoothing/history)
    """
    dt = 1.0 / sample_rate
    num_peaks = 5

    if smooth:
        # Fast updates with rolling buffer for good frequency resolution
        record_duration = 0.2
        buffer_duration = 1.0
        buffer_samples = int(buffer_duration * sample_rate)
        # Initialize rolling buffers for each device
        rolling_buffers = [np.zeros(buffer_samples) for _ in devices]
    else:
        record_duration = 1.0
        rolling_buffers = None

    # Initialize averaged spectra storage (will be set on first iteration)
    avg_accel_spectra = [None] * len(devices)
    avg_disp_spectra = [None] * len(devices)

    plt.ion()
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    plt.tight_layout()

    mode_str = f"smooth (decay={decay})" if smooth else "continuous"
    print(f"Starting {mode_str} mode. Press Ctrl+C or close the window to stop.")

    try:
        while plt.fignum_exists(fig.number):
            # Record from all devices
            _, data_list = record_from_devices(devices, duration=record_duration)

            # In smooth mode, update rolling buffers with new data
            if smooth:
                for i, new_data in enumerate(data_list):
                    # Shift buffer left and append new data
                    rolling_buffers[i] = np.roll(rolling_buffers[i], -len(new_data))
                    rolling_buffers[i][-len(new_data):] = new_data
                # Use the full rolling buffers for FFT
                data_list = rolling_buffers

            # Clear both axes
            axes[0].cla()
            axes[1].cla()

            # Track min/max for y-axis limits
            accel_amp_min, accel_amp_max = float('inf'), 0
            disp_amp_min, disp_amp_max = float('inf'), 0

            for i, (accel_data, serial) in enumerate(zip(data_list, serial_numbers)):
                color = DEVICE_COLORS[i % len(DEVICE_COLORS)]

                n = len(accel_data)
                frequencies = np.fft.rfftfreq(n, dt)

                # --- Acceleration FFT ---
                accel_fft = np.fft.rfft(accel_data)
                accel_amp = 2.0 * np.abs(accel_fft) / n

                # Apply EMA smoothing if enabled
                if smooth:
                    if avg_accel_spectra[i] is None:
                        avg_accel_spectra[i] = accel_amp
                    else:
                        avg_accel_spectra[i] = decay * avg_accel_spectra[i] + (1 - decay) * accel_amp
                    accel_amp = avg_accel_spectra[i]

                freq_mask = (frequencies >= 10.0) & (frequencies <= 200.0)
                accel_amp_min = min(accel_amp_min, accel_amp[freq_mask].min())
                accel_amp_max = max(accel_amp_max, accel_amp[freq_mask].max())

                axes[0].loglog(frequencies, accel_amp, color=color, linewidth=0.8, label=serial)

                # Find and label peaks using prominence (in 10-200 Hz range)
                min_freq_idx = np.searchsorted(frequencies, 10.0)
                max_freq_idx = np.searchsorted(frequencies, 200.0)
                search_region = accel_amp[min_freq_idx:max_freq_idx]
                peak_indices, properties = signal.find_peaks(
                    search_region,
                    prominence=np.median(search_region) * 0.5
                )
                peak_indices = peak_indices + min_freq_idx

                if len(peak_indices) > 0:
                    # Sort by prominence to get the most significant peaks
                    prominences = properties['prominences']
                    sorted_idx = np.argsort(prominences)[::-1]
                    top_peak_indices = peak_indices[sorted_idx[:num_peaks]]

                    for j, idx in enumerate(top_peak_indices):
                        freq = frequencies[idx]
                        amp = accel_amp[idx]
                        axes[0].plot(freq, amp, 'v', color=color, markersize=8)
                        axes[0].annotate(
                            f'{freq:.1f} Hz, {amp:.4f} m/s²',
                            xy=(freq, amp),
                            xytext=(5, 10 + j * 12 + i * 25),
                            textcoords='offset points',
                            fontsize=8,
                            color=color,
                            fontweight='bold'
                        )

                # --- Displacement FFT ---
                velocity = integrate_signal(accel_data, dt, sample_rate)
                displacement = integrate_signal(velocity, dt, sample_rate)
                displacement_um = displacement * 1e6

                disp_fft = np.fft.rfft(displacement_um)
                disp_amp = 2.0 * np.abs(disp_fft) / n

                # Apply EMA smoothing if enabled
                if smooth:
                    if avg_disp_spectra[i] is None:
                        avg_disp_spectra[i] = disp_amp
                    else:
                        avg_disp_spectra[i] = decay * avg_disp_spectra[i] + (1 - decay) * disp_amp
                    disp_amp = avg_disp_spectra[i]

                disp_freq_mask = (frequencies >= 10.0) & (frequencies <= 200.0)
                disp_amp_min = min(disp_amp_min, disp_amp[disp_freq_mask].min())
                disp_amp_max = max(disp_amp_max, disp_amp[disp_freq_mask].max())

                axes[1].loglog(frequencies, disp_amp, color=color, linewidth=0.8, label=serial)

                # Find and label peaks using prominence (in 10-200 Hz range)
                disp_search_region = disp_amp[min_freq_idx:max_freq_idx]
                peak_indices, properties = signal.find_peaks(
                    disp_search_region,
                    prominence=np.median(disp_search_region) * 0.5
                )
                peak_indices = peak_indices + min_freq_idx

                if len(peak_indices) > 0:
                    # Sort by prominence to get the most significant peaks
                    prominences = properties['prominences']
                    sorted_idx = np.argsort(prominences)[::-1]
                    top_peak_indices = peak_indices[sorted_idx[:num_peaks]]

                    for j, idx in enumerate(top_peak_indices):
                        freq = frequencies[idx]
                        amp = disp_amp[idx]
                        axes[1].plot(freq, amp, 'v', color=color, markersize=8)
                        # Format amplitude based on magnitude
                        if amp >= 0.1:
                            amp_str = f'{amp:.2f} µm'
                        else:
                            amp_str = f'{amp:.3f} µm'
                        axes[1].annotate(
                            f'{freq:.1f} Hz, {amp_str}',
                            xy=(freq, amp),
                            xytext=(5, 10 + j * 12 + i * 25),
                            textcoords='offset points',
                            fontsize=8,
                            color=color,
                            fontweight='bold'
                        )

            # Configure axes
            axes[0].set_xlabel('Frequency (Hz)', fontsize=11)
            axes[0].set_ylabel('Amplitude (m/s²)', fontsize=11)
            axes[0].set_title('Acceleration Spectrum', fontsize=12)
            axes[0].set_xlim(10, 200)
            accel_ylim_min = max(accel_amp_min * 0.5, 1e-10)
            axes[0].set_ylim(accel_ylim_min, accel_amp_max * 2)
            axes[0].grid(True, which='both', alpha=0.3)
            axes[0].legend(loc='upper right', fontsize=9)

            axes[1].set_xlabel('Frequency (Hz)', fontsize=11)
            axes[1].set_ylabel('Amplitude (µm)', fontsize=11)
            axes[1].set_title('Displacement Spectrum', fontsize=12)
            axes[1].set_xlim(10, 200)
            disp_ylim_min = max(disp_amp_min * 0.5, 1e-10)
            axes[1].set_ylim(disp_ylim_min, disp_amp_max * 2)
            axes[1].grid(True, which='both', alpha=0.3)
            axes[1].legend(loc='upper right', fontsize=9)

            plt.tight_layout()
            plt.pause(0.01)

    except KeyboardInterrupt:
        print("\nStopping continuous mode...")

    plt.ioff()
    plt.close(fig)
    print("Done.")


def main():
    """Main function to discover and display TMS device information."""
    parser = argparse.ArgumentParser(
        prog='read_accelerometer',
        description='Read and display data from TMS USB accelerometers'
    )
    parser.add_argument('-c', '--continuous', action='store_true',
                        help='Run in continuous mode with live updates')
    parser.add_argument('-m', '--smooth', action='store_true',
                        help='Use smoothed mode with EMA averaging (faster updates)')
    parser.add_argument('-d', '--decay', type=float, default=0.7,
                        help='Decay factor for smooth mode (0-1, default: 0.7)')
    parser.add_argument('-s', '--save', action='store_true',
                        help='Save plots to output directory')
    parser.add_argument('-C', '--calibration', action='store_true',
                        help='Get calibration data')
    args = parser.parse_args()

    print("Searching for TMS devices...")
    devices = find_devices()

    if not devices:
        return

    print(f"\nFound {len(devices)} TMS device(s):\n")

    for i, dev in enumerate(devices):
        print(f"Device {i + 1}:")
        print(f"  Device Index:    {dev['device']}")
        print(f"  Model:           {dev['model']}")
        print(f"  Serial Number:   {dev['serial_number']}")
        print(f"  Calibration Date: {dev['date'].strftime('%Y-%m-%d')}")
        print(f"  Format:          {'Acceleration (m/s²)' if dev['format'] == 0 else 'Voltage (V)'}")
        print(f"  Sensitivity:     {dev['sensitivity_int']}")
        print(f"  Scale:           {dev['scale']}")
        print()

    devices_to_use = devices[:2]
    serial_numbers = [dev['serial_number'] for dev in devices_to_use]

    if args.continuous or args.smooth:
        run_continuous(devices_to_use, serial_numbers, smooth=args.smooth, decay=args.decay)
        return

    if args.calibration:
        # Calibration mode - record noise floor and save FFT data
        cal_duration = 5.0
        print(f"Recording calibration data from {len(devices_to_use)} device(s) for {cal_duration}s...")
        print("Ensure the instrument is in a quiet state (measuring only noise).")
        t, data_list = record_from_devices(devices_to_use, duration=cal_duration)
        print("Recording complete.")

        # Calculate FFT for each device
        fft_data_list = [calculate_fft(data) for data in data_list]

        # Save calibration data
        save_calibration(fft_data_list, serial_numbers)

        # Plot the calibration spectrum
        fig = plot_fft(fft_data_list, serial_numbers)
        fig.suptitle('Calibration Noise Floor', fontsize=14)
        plt.tight_layout()
        plt.show()
        return

    # Single capture mode
    duration = 5.0
    print(f"Recording from {len(devices_to_use)} device(s) simultaneously...")
    t, data_list = record_from_devices(devices_to_use, duration=duration)
    print("Recording complete.")

    # Try to load calibration data (will be None if no calibration file exists)
    calibration_data = load_calibration()
    if calibration_data:
        print("Loaded calibration data - noise floor will be subtracted from FFT.")
    else:
        print("No calibration data found - showing raw FFT.")

    if args.save:
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)

    # Calculate and plot FFT (with optional calibration subtraction)
    fft_data_list = [calculate_fft(data) for data in data_list]
    fig3 = plot_fft(fft_data_list, serial_numbers, calibration_data=calibration_data)
    if args.save:
        fig3.savefig(os.path.join(output_dir, "fft.png"), dpi=150, bbox_inches='tight')
        print(f"Saved: {output_dir}/fft.png")

    plt.show()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        plt.close('all')
