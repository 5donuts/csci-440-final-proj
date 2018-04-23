#!/usr/bin/env python3

import sounddevice as sd
import numpy as np
from socket import *
import hashlib
from time import sleep
from bitstring import BitArray
from scipy.io.wavfile import write
from math import ceil

# global variables
TONE_DURATION = 0.05  # seconds (if this is changed, make sure to modify SAMPLES_PER_TONE)
AUDIO_SAMPLES_PER_TONE = 6616  # at 44100Hz TODO find a way to programmatically determine this
TONE_HIGH = 5000  # Hz
TONE_LOW = 0  # Hz
AUDIO_SAMPLE_RATE = 44100  # Hz
INTER_TRANSMISSION_PAUSE = 5  # seconds
PACKET_REPETITIONS = 2  # number of times each packet will be transmitted
TRANSMITTER_ADDR = '192.168.0.1'  # TODO find a way to programmatically determine this


# setup TCP server
def setup():
    port = 4000
    sock = socket(AF_INET, SOCK_STREAM)
    sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', port))
    sock.listen(1)

    return sock


# build the list of tones representing a modulated packet
def build_transmission(packet):
    # initialize list
    transmission_data = []

    # get array of bits to transmit
    b = BitArray(packet)

    # modulate the packet data
    for bit in b.bin:
        if bit == '1':
            transmission_data.append(gen_tone(TONE_DURATION, TONE_HIGH))
        else:
            transmission_data.append(gen_tone(TONE_DURATION, TONE_LOW))

    return transmission_data


# build the transmission data for all packets
def build_multiple_transmissions(packets):
    full_transmission_data = []
    print("Building transmission data...", end='', flush=True)
    for packet in packets:
        # build data for single packet
        full_transmission_data.append(build_transmission(packet))
    print("done")
    return full_transmission_data


# play the transmission data
def send_transmission(transmission_data):
    # play all tones in the transmission
    for tone in transmission_data:
        sd.play(tone, AUDIO_SAMPLE_RATE)
        sd.wait()


# generate a tone of the given duration (in seconds) at the given frequency
def gen_tone(tone_duration, frequency):
    duration = tone_duration * 3  # this makes a duration of 1 approx. equal to 1 second
    tone = (np.sin(2 * np.pi * np.arange(AUDIO_SAMPLE_RATE * duration) * frequency / AUDIO_SAMPLE_RATE)).astype(
        np.float32)
    return tone


# calculate the md5 hash of the given message
# returns hex string representing hash
def get_hash(message):
    h = hashlib.md5()
    h.update(message)
    return h.hexdigest()


# get a byte representation of a given ip address
def get_ip_addr_bytes(ip_addr):
    addr_bytes = b''

    for part in ip_addr.split('.'):
        addr_bytes += bytes([int(part)])

    return addr_bytes


# build a packet containing the message
# for more information, see docs/packet-structure/info.pdf
def build_packet(source_ip, transmitter_ip, sequence_number, checksum, data):
    packet = b''

    # preamble
    packet += b'\x55' * 32  # alternating pattern of 1s and 0s

    # source ip
    packet += get_ip_addr_bytes(source_ip)

    # transmitter_ip
    packet += get_ip_addr_bytes(transmitter_ip)

    # sequence number
    packet += sequence_number.to_bytes(1, byteorder='big')

    # data length
    packet += len(data).to_bytes(2, byteorder='big')

    # reserved
    packet += b'\x00' * 8

    # checksum
    checksum_bytes = b''
    for digit in checksum:
        checksum_bytes += ord(digit).to_bytes(1, byteorder='big')
    packet += checksum_bytes

    # data (comes in as bytes)
    packet += data

    return packet


# save a numpy array as a wave file
def save_wav(filename, audio_data):
    write(filename, AUDIO_SAMPLE_RATE, audio_data)
    print("Saved file " + filename + " successfully.")


# save transmission data into a wave file
def save_transmission_data(transmission_data):
    print("Building data for wave file...", end='', flush=True)
    # generate tone data for pauses between repetitions
    num_tones = ceil(INTER_TRANSMISSION_PAUSE / TONE_DURATION)
    pause_tones = []
    for i in range(0, num_tones):
        pause_tones.append(gen_tone(TONE_DURATION, TONE_LOW))

    # build numpy array to store tones to be saved
    wav_data = np.array(0, ndmin=1)  # need initial value for array
    i = 0
    for transmission in transmission_data:
        # store all tones for transmission
        for tone in transmission:
            wav_data = np.concatenate([wav_data, tone])

            # remove leading 0 of wav_data
            if i == 0:
                wav_data = wav_data[1:]

        # store empty tones between transmission
        for tone in pause_tones:
            wav_data = np.concatenate([wav_data, tone])

        i += 1
    print("done")

    # save the generated audio to a file
    save_wav("multi_transmission.wav", wav_data)


if __name__ == "__main__":
    sock = setup()

    # listen for connections until SIGTERM is received
    print("Transmitter started. Use ^C to exit")

    while True:
        # establish connection with client
        connection, source_addr = sock.accept()

        # get the message
        message = connection.recv(4096)
        print("Processing message: ", end='')
        print(message)

        # build the packets
        packets = []
        print("Building packets...", end='', flush=True)
        for i in range(0, PACKET_REPETITIONS):
            packets.append(build_packet(source_addr[0], TRANSMITTER_ADDR, i + 1, get_hash(message), message))
        print("done")

        # build transmission data for packets
        transmission_data = build_multiple_transmissions(packets)

        # transmit all data
        # i = 1
        # for transmission in transmission_data:
        #     print("Transmission " + str(i) + " of " + str(PACKET_REPETITIONS) + "...", end='', flush=True)
        #     send_transmission(transmission)
        #     print("done")
        #     sleep(INTER_TRANSMISSION_PAUSE)
        #     i += 1
        # del i

        # for testing purposes, save the audio data to a wave file
        save_transmission_data(transmission_data)

        # close the connection
        connection.close()
