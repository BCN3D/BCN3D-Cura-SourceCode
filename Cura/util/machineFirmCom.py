__author__ = 'rmelbourne'
import os
import glob
import sys
import time
import math
import re
import traceback
import threading
import platform
import Queue as queue

import serial

from Cura.avr_isp import stk500v2
from Cura.avr_isp import ispBase

from Cura.util import profile
from Cura.util import version
from Cura.util import machineCom

try:
    import _winreg
except:
    pass


def serialList(forAutoDetect=False):
    """
		Retrieve a list of serial ports found in the system.
	:param forAutoDetect: if true then only the USB serial ports are listed. Else all ports are listed.
	:return: A list of strings where each string is a serial port.
	"""
    baselist = []
    if platform.system() == "Windows":
        try:
            key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, "HARDWARE\\DEVICEMAP\\SERIALCOMM")
            i = 0
            while True:
                values = _winreg.EnumValue(key, i)
                if not forAutoDetect or 'USBSER' in values[0]:
                    baselist += [values[1]]
                i += 1
        except:
            pass
    if forAutoDetect:
        baselist = baselist + glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*') + glob.glob("/dev/cu.usb*")
        baselist = filter(lambda s: not 'Bluetooth' in s, baselist)
        prev = profile.getMachineSetting('serial_port_auto')
        if prev in baselist:
            baselist.remove(prev)
            baselist.insert(0, prev)
    else:
        baselist = baselist + glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*') + glob.glob(
            "/dev/cu.*") + glob.glob("/dev/tty.usb*") + glob.glob("/dev/rfcomm*") + glob.glob('/dev/serial/by-id/*')
    if version.isDevVersion() and not forAutoDetect:
        baselist.append('VIRTUAL')
    return baselist


def baudrateList():
    """
	:return: a list of integers containing all possible baudrates at which we can communicate.
			Used for auto-baudrate detection as well as manual baudrate selection.
	"""
    ret = [250000, 230400, 115200, 57600, 38400, 19200, 9600]
    if profile.getMachineSetting('serial_baud_auto') != '':
        prev = int(profile.getMachineSetting('serial_baud_auto'))
        if prev in ret:
            ret.remove(prev)
            ret.insert(0, prev)
    return ret


class VirtualPrinter():
    """
	A virtual printer class used for debugging. Acts as a serial.Serial class, but without connecting to any port.
	Only available when running the development version of Cura.
	"""

    def __init__(self):
        self.readList = ['start\n', 'Marlin: Virtual Marlin!\n', '\x80\n']
        self.temp = 0.0
        self.targetTemp = 0.0
        self.lastTempAt = time.time()
        self.bedTemp = 1.0
        self.bedTargetTemp = 1.0

    def write(self, data):
        if self.readList is None:
            return
        # print "Send: %s" % (data.rstrip())
        if 'M104' in data or 'M109' in data:
            try:
                self.targetTemp = float(re.search('S([0-9]+)', data).group(1))
            except:
                pass
        if 'M140' in data or 'M190' in data:
            try:
                self.bedTargetTemp = float(re.search('S([0-9]+)', data).group(1))
            except:
                pass
        if 'M105' in data:
            self.readList.append(
                "ok T:%.2f /%.2f B:%.2f /%.2f @:64\n" % (self.temp, self.targetTemp, self.bedTemp, self.bedTargetTemp))
        elif len(data.strip()) > 0:
            self.readList.append("ok\n")

    def readline(self):
        if self.readList is None:
            return ''
        n = 0
        timeDiff = self.lastTempAt - time.time()
        self.lastTempAt = time.time()
        if abs(self.temp - self.targetTemp) > 1:
            self.temp += math.copysign(timeDiff * 10, self.targetTemp - self.temp)
        if abs(self.bedTemp - self.bedTargetTemp) > 1:
            self.bedTemp += math.copysign(timeDiff * 10, self.bedTargetTemp - self.bedTemp)
        while len(self.readList) < 1:
            time.sleep(0.1)
            n += 1
            if n == 20:
                return ''
            if self.readList is None:
                return ''
        time.sleep(0.001)
        # print "Recv: %s" % (self.readList[0].rstrip())
        return self.readList.pop(0)

    def close(self):
        self.readList = None

class MachineFirmCom(object):
    """
	Class for (USB) serial communication with 3D printers.
	This class keeps track of if the connection is still live, can auto-detect serial ports and baudrates.
	"""
    STATE_NONE = 0
    STATE_OPEN_SERIAL = 1
    STATE_DETECT_SERIAL = 2
    STATE_DETECT_BAUDRATE = 3
    STATE_CONNECTING = 4
    STATE_OPERATIONAL = 5
    STATE_PRINTING = 6
    STATE_PAUSED = 7
    STATE_CLOSED = 8
    STATE_ERROR = 9
    STATE_CLOSED_WITH_ERROR = 10

    def __init__(self, port=None, baudrate=None, callbackObject=None):
        if port is None:
            port = profile.getMachineSetting('serial_port')
        if baudrate is None:
            if profile.getMachineSetting('serial_baud') == 'AUTO':
                baudrate = 0
            else:
                baudrate = int(profile.getMachineSetting('serial_baud'))

        self._port = port
        self._baudrate = baudrate
        self._callback = callbackObject
        self._state = self.STATE_NONE
        self._serial = None
        self._serialDetectList = []
        self._baudrateDetectList = baudrateList()
        self._baudrateDetectRetry = 0
        self._extruderCount = int(profile.getMachineSetting('extruder_amount'))
        self._temperatureRequestExtruder = 0
        self._temp = [0] * self._extruderCount
        self._targetTemp = [0] * self._extruderCount
        self._bedTemp = 0
        self._bedTargetTemp = 0
        self._gcodeList = None
        self._gcodePos = 0
        self._commandQueue = queue.Queue()
        self._logQueue = queue.Queue(256)
        self._feedRateModifier = {}
        self._currentZ = -1
        self._heatupWaitStartTime = 0
        self._heatupWaitTimeLost = 0.0
        self._printStartTime100 = None

        self.thread = threading.Thread(target=self._monitor)
        self.thread.daemon = True
        self.thread.start()

    def getState(self):
        return self._state

    def getStateString(self):
        if self._state == self.STATE_NONE:
            return "Offline"
        if self._state == self.STATE_OPEN_SERIAL:
            return "Opening serial port"
        if self._state == self.STATE_DETECT_SERIAL:
            return "Detecting serial port"
        if self._state == self.STATE_DETECT_BAUDRATE:
            return "Detecting baudrate"
        if self._state == self.STATE_CONNECTING:
            return "Connecting"
        if self._state == self.STATE_OPERATIONAL:
            return "Operational"
        if self._state == self.STATE_PRINTING:
            return "Printing"
        if self._state == self.STATE_PAUSED:
            return "Paused"
        if self._state == self.STATE_CLOSED:
            return "Closed"
        if self._state == self.STATE_ERROR:
            return "Error: %s" % (self.getShortErrorString())
        if self._state == self.STATE_CLOSED_WITH_ERROR:
            return "Error: %s" % (self.getShortErrorString())
        return "?%d?" % (self._state)

    def getShortErrorString(self):
        if len(self._errorValue) < 35:
            return self._errorValue
        return self._errorValue[:35] + "..."

    def getErrorString(self):
        return self._errorValue

    def isClosed(self):
        return self._state == self.STATE_CLOSED_WITH_ERROR or self._state == self.STATE_CLOSED

    def isClosedOrError(self):
        return self._state == self.STATE_ERROR or self._state == self.STATE_CLOSED_WITH_ERROR or self._state == self.STATE_CLOSED

    def isError(self):
        return self._state == self.STATE_ERROR or self._state == self.STATE_CLOSED_WITH_ERROR

    def isOperational(self):
        return self._state == self.STATE_OPERATIONAL or self._state == self.STATE_PRINTING or self._state == self.STATE_PAUSED

    def isPrinting(self):
        return self._state == self.STATE_PRINTING

    def isPaused(self):
        return self._state == self.STATE_PAUSED

    def getPrintPos(self):
        return self._gcodePos

    def getPrintTime(self):
        return time.time() - self._printStartTime

    def getPrintTimeRemainingEstimate(self):
        if self._printStartTime100 is None or self.getPrintPos() < 200:
            return None
        printTime = (time.time() - self._printStartTime100) / 60
        printTimeTotal = printTime * (len(self._gcodeList) - 100) / (self.getPrintPos() - 100)
        printTimeLeft = printTimeTotal - printTime
        return printTimeLeft

    def getTemp(self):
        return self._temp

    def getBedTemp(self):
        return self._bedTemp

    def getLog(self):
        ret = []
        while not self._logQueue.empty():
            ret.append(self._logQueue.get())
        for line in ret:
            self._logQueue.put(line, False)
        return ret

    def _monitor(self):
        programmer = stk500v2.Stk500v2()
        if self._port == 'AUTO':
            while not programmer.isConnected():
                for self._port in machineCom.serialList(False):
                    try:
                        programmer.connect(self._port)
                        if programmer.isConnected():
                            return self._serial
                    except ispBase.IspError:
                        programmer.close()
                time.sleep(1)
                if not self:
                    #Window destroyed
                    return
        else:
            try:
                programmer.connect(self._port)
            except ispBase.IspError:
                programmer.close()



