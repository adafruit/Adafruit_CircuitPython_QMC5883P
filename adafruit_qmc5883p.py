# SPDX-FileCopyrightText: Copyright (c) 2025 Liz Clark for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`adafruit_qmc5883p`
================================================================================

CircuitPython driver for the Adafruit QMC5883P - Triple Axis Magnetometer - STEMMA QT


* Author(s): Liz Clark

Implementation Notes
--------------------

**Hardware:**

* `Adafruit QMC5883P - Triple Axis Magnetometer <https://www.adafruit.com/product/6388>`_"

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads

* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
* Adafruit's Register library: https://github.com/adafruit/Adafruit_CircuitPython_Register
"""

import struct
import time

from adafruit_bus_device.i2c_device import I2CDevice
from adafruit_register.i2c_bit import ROBit, RWBit
from adafruit_register.i2c_bits import RWBits
from adafruit_register.i2c_struct import ROUnaryStruct
from micropython import const

try:
    from typing import Tuple

    import busio
except ImportError:
    pass

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_QMC5883P.git"

# I2C Address
_DEFAULT_ADDR = const(0x2C)

# Registers
_CHIPID = const(0x00)
_XOUT_LSB = const(0x01)
_XOUT_MSB = const(0x02)
_YOUT_LSB = const(0x03)
_YOUT_MSB = const(0x04)
_ZOUT_LSB = const(0x05)
_ZOUT_MSB = const(0x06)
_STATUS = const(0x09)
_CONTROL1 = const(0x0A)
_CONTROL2 = const(0x0B)

# Operating modes
MODE_SUSPEND = const(0x00)
MODE_NORMAL = const(0x01)
MODE_SINGLE = const(0x02)
MODE_CONTINUOUS = const(0x03)

# Output data rates
ODR_10HZ = const(0x00)
ODR_50HZ = const(0x01)
ODR_100HZ = const(0x02)
ODR_200HZ = const(0x03)

# Over sample ratios
OSR_8 = const(0x00)
OSR_4 = const(0x01)
OSR_2 = const(0x02)
OSR_1 = const(0x03)

# Downsample ratios
DSR_1 = const(0x00)
DSR_2 = const(0x01)
DSR_4 = const(0x02)
DSR_8 = const(0x03)

# Field ranges
RANGE_30G = const(0x00)
RANGE_12G = const(0x01)
RANGE_8G = const(0x02)
RANGE_2G = const(0x03)

# Set/Reset modes
SETRESET_ON = const(0x00)
SETRESET_SETONLY = const(0x01)
SETRESET_OFF = const(0x02)

# LSB per Gauss for each range
_LSB_PER_GAUSS = {RANGE_30G: 1000.0, RANGE_12G: 2500.0, RANGE_8G: 3750.0, RANGE_2G: 15000.0}


class QMC5883P:
    """Driver for the QMC5883P 3-axis magnetometer.

    :param ~busio.I2C i2c_bus: The I2C bus the QMC5883P is connected to.
    :param int address: The I2C address of the device. Defaults to :const:`0x3C`
    """

    # Register definitions using adafruit_register
    _chip_id = ROUnaryStruct(_CHIPID, "<B")

    # Status register bits
    data_ready = ROBit(_STATUS, 0)
    """Check if new magnetic data is ready."""
    overflow = ROBit(_STATUS, 1)
    """Check if data overflow has occurred."""

    # Control register 1 bits
    _mode = RWBits(2, _CONTROL1, 0)
    _odr = RWBits(2, _CONTROL1, 2)
    _osr = RWBits(2, _CONTROL1, 4)
    _dsr = RWBits(2, _CONTROL1, 6)

    # Control register 2 bits
    _setreset = RWBits(2, _CONTROL2, 0)
    _range = RWBits(2, _CONTROL2, 2)
    _selftest = RWBit(_CONTROL2, 6)
    _reset = RWBit(_CONTROL2, 7)

    def __init__(self, i2c_bus: busio.I2C, address: int = _DEFAULT_ADDR) -> None:
        self.i2c_device = I2CDevice(i2c_bus, address)

        # Check chip ID
        if self._chip_id != 0x80:
            raise RuntimeError("Failed to find QMC5883P chip")

        # Initialize with default settings
        self.mode = MODE_NORMAL
        self.data_rate = ODR_50HZ
        self.oversample_ratio = OSR_4
        self.downsample_ratio = DSR_2
        self.range = RANGE_8G
        self.setreset_mode = SETRESET_ON

    @property
    def magnetic(self) -> Tuple[float, float, float]:
        """The magnetic field measured in microteslas (uT).

        :return: A 3-tuple of X, Y, Z axis values in microteslas
        """
        # Wait for data ready
        while not self.data_ready:
            time.sleep(0.001)

        # Read all 6 bytes at once
        buf = bytearray(6)
        with self.i2c_device as i2c:
            i2c.write_then_readinto(bytes([_XOUT_LSB]), buf)

        # Unpack as signed 16-bit integers
        raw_x, raw_y, raw_z = struct.unpack("<hhh", buf)

        # Get conversion factor based on current range
        lsb_per_gauss = _LSB_PER_GAUSS[self._range]

        # Convert to Gauss then to microteslas (1 Gauss = 100 uT)
        x = raw_x / lsb_per_gauss
        y = raw_y / lsb_per_gauss
        z = raw_z / lsb_per_gauss

        return (x, y, z)

    @property
    def magnetic_raw(self) -> Tuple[int, int, int]:
        """The raw magnetic field sensor values as signed 16-bit integers.

        :return: A 3-tuple of X, Y, Z axis raw values
        """
        # Wait for data ready
        while not self._data_ready:
            time.sleep(0.001)

        # Read all 6 bytes at once
        buf = bytearray(6)
        with self.i2c_device as i2c:
            i2c.write_then_readinto(bytes([_XOUT_LSB]), buf)

        # Unpack as signed 16-bit integers
        return struct.unpack("<hhh", buf)

    @property
    def mode(self) -> int:
        """The operating mode of the sensor.

        Options are:
        - MODE_SUSPEND (0x00): Suspend mode
        - MODE_NORMAL (0x01): Normal mode
        - MODE_SINGLE (0x02): Single measurement mode
        - MODE_CONTINUOUS (0x03): Continuous mode
        """
        return self._mode

    @mode.setter
    def mode(self, value: int) -> None:
        if value not in {MODE_SUSPEND, MODE_NORMAL, MODE_SINGLE, MODE_CONTINUOUS}:
            raise ValueError("Invalid mode")
        self._mode = value

    @property
    def data_rate(self) -> int:
        """The output data rate in Hz.

        Options are:
        - ODR_10HZ (0x00): 10 Hz
        - ODR_50HZ (0x01): 50 Hz
        - ODR_100HZ (0x02): 100 Hz
        - ODR_200HZ (0x03): 200 Hz
        """
        return self._odr

    @data_rate.setter
    def data_rate(self, value: int) -> None:
        if value not in {ODR_10HZ, ODR_50HZ, ODR_100HZ, ODR_200HZ}:
            raise ValueError("Invalid output data rate")
        self._odr = value

    @property
    def oversample_ratio(self) -> int:
        """The over sample ratio.

        Options are:
        - OSR_8 (0x00): Over sample ratio = 8
        - OSR_4 (0x01): Over sample ratio = 4
        - OSR_2 (0x02): Over sample ratio = 2
        - OSR_1 (0x03): Over sample ratio = 1
        """
        return self._osr

    @oversample_ratio.setter
    def oversample_ratio(self, value: int) -> None:
        if value not in {OSR_8, OSR_4, OSR_2, OSR_1}:
            raise ValueError("Invalid oversample ratio")
        self._osr = value

    @property
    def downsample_ratio(self) -> int:
        """The downsample ratio.

        Options are:
        - DSR_1 (0x00): Downsample ratio = 1
        - DSR_2 (0x01): Downsample ratio = 2
        - DSR_4 (0x02): Downsample ratio = 4
        - DSR_8 (0x03): Downsample ratio = 8
        """
        return self._dsr

    @downsample_ratio.setter
    def downsample_ratio(self, value: int) -> None:
        if value not in {DSR_1, DSR_2, DSR_4, DSR_8}:
            raise ValueError("Invalid downsample ratio")
        self._dsr = value

    @property
    def range(self) -> int:
        """The magnetic field range.

        Options are:
        - RANGE_30G (0x00): ±30 Gauss range
        - RANGE_12G (0x01): ±12 Gauss range
        - RANGE_8G (0x02): ±8 Gauss range
        - RANGE_2G (0x03): ±2 Gauss range
        """
        return self._range

    @range.setter
    def range(self, value: int) -> None:
        if value not in {RANGE_30G, RANGE_12G, RANGE_8G, RANGE_2G}:
            raise ValueError("Invalid range")
        self._range = value

    @property
    def setreset_mode(self) -> int:
        """The set/reset mode.

        Options are:
        - SETRESET_ON (0x00): Set and reset on
        - SETRESET_SETONLY (0x01): Set only on
        - SETRESET_OFF (0x02): Set and reset off
        """
        return self._setreset

    @setreset_mode.setter
    def setreset_mode(self, value: int) -> None:
        if value not in {SETRESET_ON, SETRESET_SETONLY, SETRESET_OFF}:
            raise ValueError("Invalid set/reset mode")
        self._setreset = value

    def soft_reset(self) -> None:
        """Perform a soft reset of the chip."""
        self._reset = True
        time.sleep(0.05)  # Wait 50ms for reset to complete

        # Verify chip ID after reset
        if self._chip_id != 0x80:
            raise RuntimeError("Chip ID invalid after reset")

    def self_test(self) -> bool:
        """Perform self-test of the chip.

        :return: True if self-test passed, False otherwise
        """
        self._selftest = True
        time.sleep(0.005)  # Wait 5ms for self-test to complete

        # Check if self-test bit auto-cleared (indicates completion)
        return not self._selftest
