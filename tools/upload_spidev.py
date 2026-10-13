#!/usr/bin/env python3
"""Optional Linux SPI upload tool (requires spidev & electrically compatible I/O).
Use a master SPI clock well below sysclk/4; at 12 MHz use <= 500 kHz.
"""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('program', type=Path, help='assembled .bin, including WRITE command')
    parser.add_argument('--bus', type=int, default=0)
    parser.add_argument('--device', type=int, default=0)
    parser.add_argument('--speed', type=int, default=250_000)
    parser.add_argument('--entry', type=int, default=0)
    options = parser.parse_args()
    if not 0 <= options.entry < 64:
        parser.error('--entry must be 0..63')
    data = options.program.read_bytes()
    if len(data) < 4 or data[0] != 0x01 or len(data) % 2 != 0:
        parser.error('file is not a complete WRITE SPI frame')
    import spidev  # install on Raspberry Pi/Linux SPI host, not required for testing
    spi = spidev.SpiDev()
    spi.open(options.bus, options.device)
    spi.max_speed_hz = options.speed
    spi.mode = 0
    try:
        spi.xfer2(list(data))  # one continuous CS-low WRITE transaction
        spi.xfer2([0x02, options.entry])  # new CS-low RUN transaction
    finally:
        spi.close()
    print(f'Loaded {(len(data)-2)//2} instructions and sent RUN PC={options.entry}')

if __name__ == '__main__':
    main()
