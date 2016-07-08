__author__ = 'rmelbourne'

import os
import webbrowser
import threading
import time
import math
import wx
import sys
import time
import serial
import subprocess
import Queue as queue
import glob
import platform
import traceback

import wx
import wx.wizard

try:
    import _winreg
except:
    pass

from Cura.gui import firmwareInstall
from Cura.gui import printWindow
from Cura.util import gcodeGenerator
from Cura.util import resources
from Cura.avr_isp import stk500v2
from Cura.avr_isp import ispBase
from Cura.avr_isp import intelHex

from Cura.gui.util import taskbar
from Cura.util import machineCom
from Cura.util import profile
from Cura.util import resources
from Cura.util import version
from Tkinter import *

class InfoBox(wx.Panel):
    def __init__(self, parent):
        super(InfoBox, self).__init__(parent)
        self.SetBackgroundColour('#FFFF80')

        self.sizer = wx.GridBagSizer(5, 5)
        self.SetSizer(self.sizer)

        self.attentionBitmap = wx.Bitmap(resources.getPathForImage('attention.png'))
        self.errorBitmap = wx.Bitmap(resources.getPathForImage('error.png'))
        self.readyBitmap = wx.Bitmap(resources.getPathForImage('ready.png'))
        self.busyBitmap = [
            wx.Bitmap(resources.getPathForImage('busy-0.png')),
            wx.Bitmap(resources.getPathForImage('busy-1.png')),
            wx.Bitmap(resources.getPathForImage('busy-2.png')),
            wx.Bitmap(resources.getPathForImage('busy-3.png'))
        ]

        self.bitmap = wx.StaticBitmap(self, -1, wx.EmptyBitmapRGBA(24, 24, red=255, green=255, blue=255, alpha=1))
        self.text = wx.StaticText(self, -1, '')
        self.extraInfoButton = wx.Button(self, -1, 'i', style=wx.BU_EXACTFIT)
        self.sizer.Add(self.bitmap, pos=(0, 0), flag=wx.ALL, border=5)
        self.sizer.Add(self.text, pos=(0, 1), flag=wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border=5)
        self.sizer.Add(self.extraInfoButton, pos=(0,2), flag=wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, border=5)
        self.sizer.AddGrowableCol(1)

        self.extraInfoButton.Show(False)

        self.extraInfoUrl = ''
        self.busyState = None
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.doBusyUpdate, self.timer)
        self.Bind(wx.EVT_BUTTON, self.doExtraInfo, self.extraInfoButton)
        self.timer.Start(100)

    def SetInfo(self, info):
        self.SetBackgroundColour('#FFFF80')
        self.text.SetLabel(info)
        self.extraInfoButton.Show(False)
        self.Refresh()

    def SetError(self, info, extraInfoUrl):
        self.extraInfoUrl = extraInfoUrl
        self.SetBackgroundColour('#FF8080')
        self.text.SetLabel(info)
        self.extraInfoButton.Show(True)
        self.Layout()
        self.SetErrorIndicator()
        self.Refresh()

    def SetAttention(self, info):
        self.SetBackgroundColour('#FFFF80')
        self.text.SetLabel(info)
        self.extraInfoButton.Show(False)
        self.SetAttentionIndicator()
        self.Layout()
        self.Refresh()

    def SetBusy(self, info):
        self.SetInfo(info)
        self.SetBusyIndicator()

    def SetBusyIndicator(self):
        self.busyState = 0
        self.bitmap.SetBitmap(self.busyBitmap[self.busyState])

    def doExtraInfo(self, e):
        webbrowser.open(self.extraInfoUrl)

    def doBusyUpdate(self, e):
        if self.busyState is None:
            return
        self.busyState += 1
        if self.busyState >= len(self.busyBitmap):
            self.busyState = 0
        self.bitmap.SetBitmap(self.busyBitmap[self.busyState])

    def SetReadyIndicator(self):
        self.busyState = None
        self.bitmap.SetBitmap(self.readyBitmap)

    def SetErrorIndicator(self):
        self.busyState = None
        self.bitmap.SetBitmap(self.errorBitmap)

    def SetAttentionIndicator(self):
        self.busyState = None
        self.bitmap.SetBitmap(self.attentionBitmap)

class InfoPage(wx.wizard.WizardPageSimple):
    def __init__(self, parent, title):
        wx.wizard.WizardPageSimple.__init__(self, parent)

        sizer = wx.GridBagSizer(5, 5)
        self.sizer = sizer
        self.SetSizer(sizer)

        title = wx.StaticText(self, -1, title)
        title.SetFont(wx.Font(18, wx.SWISS, wx.NORMAL, wx.BOLD))
        sizer.Add(title, pos=(0, 0), span=(1, 2), flag=wx.ALIGN_CENTRE | wx.ALL)
        sizer.Add(wx.StaticLine(self, -1), pos=(1, 0), span=(1, 2), flag=wx.EXPAND | wx.ALL)
        sizer.AddGrowableCol(1)

        self.rowNr = 2

    def AddText(self, info):
        text = wx.StaticText(self, -1, info)
        self.GetSizer().Add(text, pos=(self.rowNr, 0), span=(1, 2), flag=wx.LEFT | wx.RIGHT)
        self.rowNr += 1
        return text

    def AddSeperator(self):
        self.GetSizer().Add(wx.StaticLine(self, -1), pos=(self.rowNr, 0), span=(1, 2), flag=wx.EXPAND | wx.ALL)
        self.rowNr += 1

    def AddHiddenSeperator(self):
        self.AddText("")

    def AddInfoBox(self):
        infoBox = InfoBox(self)
        self.GetSizer().Add(infoBox, pos=(self.rowNr, 0), span=(1, 2), flag=wx.LEFT | wx.RIGHT | wx.EXPAND)
        self.rowNr += 1
        return infoBox

    def AddRadioButton(self, label, style=0):
        radio = wx.RadioButton(self, -1, label, style=style)
        self.GetSizer().Add(radio, pos=(self.rowNr, 0), span=(1, 2), flag=wx.EXPAND | wx.ALL)
        self.rowNr += 1
        return radio

    def AddCheckbox(self, label, checked=False):
        check = wx.CheckBox(self, -1)
        text = wx.StaticText(self, -1, label)
        check.SetValue(checked)
        self.GetSizer().Add(text, pos=(self.rowNr, 0), span=(1, 1), flag=wx.LEFT | wx.RIGHT)
        self.GetSizer().Add(check, pos=(self.rowNr, 1), span=(1, 2), flag=wx.ALL)
        self.rowNr += 1
        return check

    def AddButton(self, label):
        button = wx.Button(self, -1, label)
        self.GetSizer().Add(button, pos=(self.rowNr, 0), span=(1, 2), flag=wx.LEFT)
        self.rowNr += 1
        return button

    def AddDualButton(self, label1, label2):
        button1 = wx.Button(self, -1, label1)
        self.GetSizer().Add(button1, pos=(self.rowNr, 0), flag=wx.RIGHT)
        button2 = wx.Button(self, -1, label2)
        self.GetSizer().Add(button2, pos=(self.rowNr, 1))
        self.rowNr += 1
        return button1, button2

    def AddTextCtrl(self, value):
        ret = wx.TextCtrl(self, -1, value)
        self.GetSizer().Add(ret, pos=(self.rowNr, 0), span=(1, 2), flag=wx.LEFT)
        self.rowNr += 1
        return ret

    def AddLabelTextCtrl(self, info, value):
        text = wx.StaticText(self, -1, info)
        ret = wx.TextCtrl(self, -1, value)
        self.GetSizer().Add(text, pos=(self.rowNr, 0), span=(1, 1), flag=wx.LEFT)
        self.GetSizer().Add(ret, pos=(self.rowNr, 1), span=(1, 1), flag=wx.LEFT)
        self.rowNr += 1
        return ret

    def AddTextCtrlButton(self, value, buttonText):
        text = wx.TextCtrl(self, -1, value)
        button = wx.Button(self, -1, buttonText)
        self.GetSizer().Add(text, pos=(self.rowNr, 0), span=(1, 1), flag=wx.LEFT)
        self.GetSizer().Add(button, pos=(self.rowNr, 1), span=(1, 1), flag=wx.LEFT)
        self.rowNr += 1
        return text, button

    def AddBitmap(self, bitmap):
        bitmap = wx.StaticBitmap(self, -1, bitmap)
        self.GetSizer().Add(bitmap, pos=(self.rowNr, 0), span=(1, 2), flag=wx.LEFT | wx.RIGHT)
        self.rowNr += 1
        return bitmap

    def AddCheckmark(self, label, bitmap):
        check = wx.StaticBitmap(self, -1, bitmap)
        text = wx.StaticText(self, -1, label)
        self.GetSizer().Add(text, pos=(self.rowNr, 0), span=(1, 1), flag=wx.LEFT | wx.RIGHT)
        self.GetSizer().Add(check, pos=(self.rowNr, 1), span=(1, 1), flag=wx.ALL)
        self.rowNr += 1
        return check

    def AddCombo(self, label, options):
        combo = wx.ComboBox(self, -1, options[0], choices=options, style=wx.CB_DROPDOWN|wx.CB_READONLY)
        text = wx.StaticText(self, -1, label)
        self.GetSizer().Add(text, pos=(self.rowNr, 0), span=(1, 1), flag=wx.LEFT | wx.RIGHT)
        self.GetSizer().Add(combo, pos=(self.rowNr, 1), span=(1, 1), flag=wx.LEFT | wx.RIGHT)
        self.rowNr += 1
        return combo

    def AllowNext(self):
        return True

    def AllowBack(self):
        return True

    def StoreData(self):
        pass

class MachineSelectPage(InfoPage):
    def __init__(self, parent):
        super(MachineSelectPage, self).__init__(parent, _("Automatic Firmware Updater"))
        self.AddText(_("Check updates for which machine:"))

        sigmaButton = self.AddButton('BCN3D Sigma')
        sigmaButton.Bind(wx.EVT_BUTTON, self.OnBCN3DSigmaSelect)
        plusButton = self.AddButton('BCN3D +')
        plusButton.Bind(wx.EVT_BUTTON, self.OnBCN3DPlusSelect)
        rButton = self.AddButton('BCN3D R')
        rButton.Bind(wx.EVT_BUTTON, self.OnBCN3DRSelect)

        plusButton.Enable(False)
        rButton.Enable(False)

    def OnBCN3DSigmaSelect(self,e):
        self.GetParent().FindWindowById(wx.ID_FORWARD).Enable()
        self.GetParent().ShowPage(self.GetNext())

    def OnBCN3DPlusSelect(self,e):
        wx.wizard.WizardPageSimple.Chain(self, self.GetParent().decidetoupdateplus)

    def OnBCN3DRSelect(self,e):
        wx.wizard.WizardPageSimple.Chain(self, self.GetParent().decidetoupdater)

    def AllowBack(self):
        return False

class decideToUpdateSigma(InfoPage):

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

    def __init__(self, parent):
        super(decideToUpdateSigma, self).__init__(parent, _('Upgrade BCN3D Sigma Firmware'))

        self.checkBitmap = wx.Bitmap(resources.getPathForImage('checkmark.png'))
        self.crossBitmap = wx.Bitmap(resources.getPathForImage('cross.png'))
        self.unknownBitmap = wx.Bitmap(resources.getPathForImage('question.png'))

        connectPritner = self.AddButton(_("Upgrade Now"))
        connectPritner.Bind(wx.EVT_BUTTON, self.OnCheckClick)
        connectPritner = self.AddButton(_("Now"))
        connectPritner.Bind(wx.EVT_BUTTON, self.Go)
        connectPritner.Enable(True)
        self.AddSeperator()
        self.commState = self.AddCheckmark(_("Communication:"), self.unknownBitmap)
        self.unknownBitmap = wx.Bitmap(resources.getPathForImage('question.png'))
        self.infoBox = self.AddInfoBox()
        self.machineState = self.AddText("")
        self.errorLogButton = self.AddButton(_("Show error log"))
        self.errorLogButton.Show(False)
        self.comm = None
        self.Bind(wx.EVT_BUTTON, self.OnErrorLog, self.errorLogButton)


    def __del__(self):
        if self.comm is not None:
            self.comm.close()

    def AllowNext(self):
        return False

    def OnCheckClick(self, e=None):
        self.errorLogButton.Show(False)
        if self.comm is not None:
            self.comm.close()
            del self.comm
            self.comm = None
            wx.CallAfter(self.OnCheckClick)
            return
        self.infoBox.SetBusy(_("Connecting to machine."))
        self.commState.SetBitmap(self.unknownBitmap)
        self.comm = MachineConnect(callbackObject=self)
        self.checkupState = 0



    def OnErrorLog(self, e):
        printWindow.LogWindow('\n'.join(self.comm.getLog()))

    def mcLog(self, message):
        pass

    def mcStateChange(self, state):
        if self.comm is None:
            return
        if self.comm.isOperational():
            wx.CallAfter(self.commState.SetBitmap, self.checkBitmap)
            wx.CallAfter(self.machineState.SetLabel, _("%s") % (self.comm.getStateString()))
            wx.CallAfter(self.infoBox.SetReadyIndicator)
        elif self.comm.isError():
            wx.CallAfter(self.commState.SetBitmap, self.crossBitmap)
            wx.CallAfter(self.infoBox.SetError, _("Failed to establish connection with the printer."),
                         'https://github.com/BCN3D/BCN3D-Cura-Windows/issues')
            wx.CallAfter(self.machineState.SetLabel, '%s' % (self.comm.getErrorString()))
            wx.CallAfter(self.errorLogButton.Show, True)
            wx.CallAfter(self.Layout)
        elif self.comm.isClosed():
            wx.CallAfter(self.commState.SetBitmap, self.crossBitmap)
            wx.CallAfter(self.machineState.SetLabel, _("Failed to establish connection with the printer."))
            wx.CallAfter(self.infoBox.SetErrorIndicator)
        else:
            wx.CallAfter(self.machineState.SetLabel, _("Communication State: %s") % (self.comm.getStateString()))

    def mcMessage(self, message):
        if self.checkupState >= 3 and self.checkupState < 10 and ('_min' in message or '_max' in message):
            for data in message.split(' '):
                if ':' in data:
                    tag, value = data.split(':', 1)
                    if tag == 'x_min':
                        self.xMinStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'x_max':
                        self.xMaxStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'y_min':
                        self.yMinStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'y_max':
                        self.yMaxStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'z_min':
                        self.zMinStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'z_max':
                        self.zMaxStop = (value == 'H' or value == 'TRIGGERED')
            if ':' in message:
                tag, value = map(str.strip, message.split(':', 1))
                if tag == 'x_min':
                    self.xMinStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'x_max':
                    self.xMaxStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'y_min':
                    self.yMinStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'y_max':
                    self.yMaxStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'z_min':
                    self.zMinStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'z_max':
                    self.zMaxStop = (value == 'H' or value == 'TRIGGERED')
            if 'z_max' in message:
                self.comm.sendCommand('M119')

            if self.checkupState == 3:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    if profile.getMachineSetting('machine_type') == 'ultimaker_plus':
                        self.checkupState = 5
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the left X endstop."))
                    else:
                        self.checkupState = 4
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the right X endstop."))
            elif self.checkupState == 4:
                if not self.xMinStop and self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    self.checkupState = 5
                    wx.CallAfter(self.infoBox.SetAttention, _("Please press the left X endstop."))
            elif self.checkupState == 5:
                if self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    self.checkupState = 6
                    wx.CallAfter(self.infoBox.SetAttention, _("Please press the front Y endstop."))
            elif self.checkupState == 6:
                if not self.xMinStop and not self.xMaxStop and self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    if profile.getMachineSetting('machine_type') == 'ultimaker_plus':
                        self.checkupState = 8
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the top Z endstop."))
                    else:
                        self.checkupState = 7
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the back Y endstop."))
            elif self.checkupState == 7:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    self.checkupState = 8
                    wx.CallAfter(self.infoBox.SetAttention, _("Please press the top Z endstop."))
            elif self.checkupState == 8:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and self.zMinStop and not self.zMaxStop:
                    if profile.getMachineSetting('machine_type') == 'ultimaker_plus':
                        self.checkupState = 10
                        self.comm.close()
                        wx.CallAfter(self.infoBox.SetInfo, _("Checkup finished"))
                        wx.CallAfter(self.infoBox.SetReadyIndicator)
                    else:
                        self.checkupState = 9
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the bottom Z endstop."))
            elif self.checkupState == 9:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and self.zMaxStop:
                    self.checkupState = 10
                    self.comm.close()
                    wx.CallAfter(self.infoBox.SetInfo, _("Checkup finished"))
                    wx.CallAfter(self.infoBox.SetReadyIndicator)

    def mcProgress(self, lineNr):
        pass

    def mcZChange(self, newZ):
        pass

    def Go(self, e=None):
        self.comm.readFirstLine()
        self.comm.getFirmwareHardware()

class getVersion(InfoPage):
    def __init__(self, parent):
        super(getVersion, self).__init__(parent, _("Automatic Firmware Updater"))

        self.AddText(_('YAAAY'))


#Where you edit the pages and how they work
class ConfigFirmware(wx.wizard.Wizard):
    def __init__(self, addNew = False):
        super(ConfigFirmware, self).__init__(None, -1, _("Machine Firmware Updater"))

        self._old_machine_index = int(profile.getPreferenceFloat('active_machine'))
        if addNew:
            profile.setActiveMachine(profile.getMachineCount())

        self.Bind(wx.wizard.EVT_WIZARD_CANCEL, self.OnCancel)
        self.Bind(wx.wizard.EVT_WIZARD_PAGE_CHANGED, self.OnPageChanged)
        self.Bind(wx.wizard.EVT_WIZARD_PAGE_CHANGING, self.OnPageChanging)
        self.Bind(wx.wizard.EVT_WIZARD_FINISHED, self.OnFinish)


        self.machineSelectPage = MachineSelectPage(self)
        self.decidetoupdatesigma = decideToUpdateSigma(self)
        self.getversion = getVersion(self)



        if profile.getMachineSetting('machine_type') == 'BCN3DSigma':
            wx.wizard.WizardPageSimple.Chain(self.machineSelectPage, self.decidetoupdatesigma)
            wx.wizard.WizardPageSimple.Chain(self.decidetoupdatesigma, self.getversion)

        self.FitToPage(self.machineSelectPage)
        self.GetPageAreaSizer().Add(self.machineSelectPage)

        self.RunWizard(self.machineSelectPage)
        self.Destroy()

    def OnPageChanging(self, e):
        e.GetPage().StoreData()

    def OnPageChanged(self, e):
        if e.GetPage().AllowNext():
            self.FindWindowById(wx.ID_FORWARD).Enable()
        else:
            self.FindWindowById(wx.ID_FORWARD).Disable()
        if e.GetPage().AllowBack():
            self.FindWindowById(wx.ID_BACKWARD).Enable()
        else:
            self.FindWindowById(wx.ID_BACKWARD).Disable()

    def OnCancel(self, e):
        self.Destroy()

    def OnFinish(self, e):
        self.Destroy()




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


class MachineComPrintCallback(object):
    """
	Base class for callbacks from the MachineCom class.
	This class has all empty implementations and is attached to the MachineCom if no other callback object is attached.
	"""

    def mcLog(self, message):
        pass

    def mcTempUpdate(self, temp, bedTemp, targetTemp, bedTargetTemp):
        pass

    def mcStateChange(self, state):
        pass

    def mcMessage(self, message):
        pass

    def mcProgress(self, lineNr):
        pass

    def mcZChange(self, newZ):
        pass


class MachineConnect(object):
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
            print 'First we detect the ' + port
        if profile.getMachineSetting('machine_type') == 'BCN3DSigma':
            baudrate = 250000
        if baudrate is None:
            if profile.getMachineSetting('serial_baud') == 'AUTO':
                baudrate = 0
            else:
                baudrate = int(profile.getMachineSetting('serial_baud'))
                print 'Second we get the desired baudrate = ', baudrate
        if callbackObject is None:
            callbackObject = MachineComPrintCallback()

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
        self.thread.join()
        if self.getStateString() == 'Connected':
            print 'despues de acabar'

    def _changeState(self, newState):
        if self._state == newState:
            return
        oldState = self.getStateString()
        self._state = newState
        self._log('Changing monitoring state from \'%s\' to \'%s\'' % (oldState, self.getStateString()))
        self._callback.mcStateChange(newState)

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
            return "Connected"
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
        # Open the serial port.
        if self._port == 'AUTO':
            print 'entramos en port auto despues de baudrate'
            self._changeState(self.STATE_DETECT_SERIAL)
            programmer = stk500v2.Stk500v2()
            if not programmer.isConnected():
                print 'not connected'
                for self._port in serialList(False):
                    try:
                        self._log("Connecting to: %s (programmer)" % (self._port))
                        programmer.connect(self._port)
                        self._serial = programmer.leaveISP()
                        print self._baudrate
                        profile.putMachineSetting('serial_port_auto', self._port)
                        print 'hemos llegado despues del port'
                        print self._port
                        print self._serial
                        self._serial = serial.Serial(str(self._port), self._baudrate, timeout=5, writeTimeout=10000)
                        print self._serial
                        profile.putMachineSetting('self_serial', self._serial)
                        break
                    except ispBase.IspError as (e):
                        self._log("Error while connecting to %s: %s" % (self._port, str(e)))
                        pass
                    except:
                        self._log("Unexpected error while connecting to serial port: %s %s" % (self._port, getExceptionString()))
                    programmer.close()
                if self._serial is None:
                    self._log("Serial port list: %s" % (str(serialList(True))))
                    self._serialDetectList = serialList(True)
        elif self._port == 'VIRTUAL':
            self._changeState(self.STATE_OPEN_SERIAL)
            self._serial = VirtualPrinter()
        else:
            self._changeState(self.STATE_OPEN_SERIAL)
            try:
                if self._baudrate == 0:
                    self._log("Connecting to: %s with baudrate: 115200 (fallback)" % (self._port))
                    self._serial = serial.Serial(str(self._port), 115200, timeout=3, writeTimeout=10000)
                else:
                    self._log("Connecting to: %s with baudrate: %s (configured)" % (self._port, self._baudrate))
                    self._serial = serial.Serial(str(self._port), self._baudrate, timeout=5, writeTimeout=10000)
            except:
                self._log(
                    "Unexpected error while connecting to serial port: %s %s" % (self._port, getExceptionString()))
        if self._serial is None:
            baudrate = self._baudrate
            if baudrate == 0:
                baudrate = self._baudrateDetectList.pop(0)
            if len(self._serialDetectList) < 1:
                self._log("Found no ports to try for auto detection")
                self._errorValue = "Please make sure your printer is connected."
                self._changeState(self.STATE_ERROR)
                return
            port = self._serialDetectList.pop(0)
            self._log("Connecting to: %s with baudrate: %s (auto)" % (port, baudrate))
            try:
                self._serial = serial.Serial(port, baudrate, timeout=3, writeTimeout=10000)
            except:
                pass
        else:
            self._log("Connected to: %s, starting monitor" % (self._serial))
            if self._baudrate != 250000:
                self._changeState(self.STATE_DETECT_BAUDRATE)
            else:
                print 'entramos en state connecting'
                self._changeState(self.STATE_CONNECTING)

        if self._state == self.STATE_CONNECTING:
            timeout = time.time() + 15
        else:
            timeout = time.time() + 5
        tempRequestTimeout = timeout

        while True:
            line = self._readline()
            if line is None:
                break

            # No matter the state, if we see an fatal error, goto the error state and store the error for reference.
            # Only goto error on known fatal errors.
            if line.startswith('Error:'):
                # Oh YEAH, consistency.
                # Marlin reports an MIN/MAX temp error as "Error:x\n: Extruder switched off. MAXTEMP triggered !\n"
                #	But a bed temp error is reported as "Error: Temperature heated bed switched off. MAXTEMP triggered !!"
                #	So we can have an extra newline in the most common case. Awesome work people.
                if re.match('Error:[0-9]\n', line):
                    line = line.rstrip() + self._readline()
                # Skip the communication errors, as those get corrected.
                if 'Extruder switched off' in line or 'Temperature heated bed switched off' in line or 'Something is wrong, please turn off the printer.' in line:
                    if not self.isError():
                        self._errorValue = line[6:]
                        self._changeState(self.STATE_ERROR)
            if ' T:' in line or line.startswith('T:'):
                try:
                    self._temp[self._temperatureRequestExtruder] = float(re.search("T: *([0-9\.]*)", line).group(1))
                except:
                    pass
                if 'B:' in line:
                    try:
                        self._bedTemp = float(re.search("B: *([0-9\.]*)", line).group(1))
                    except:
                        pass
                #self._callback.mcTempUpdate(self._temp, self._bedTemp, self._targetTemp, self._bedTargetTemp)
                # If we are waiting for an M109 or M190 then measure the time we lost during heatup, so we can remove that time from our printing time estimate.
                if not 'ok' in line and self._heatupWaitStartTime != 0:
                    t = time.time()
                    self._heatupWaitTimeLost = t - self._heatupWaitStartTime
                    self._heatupWaitStartTime = t
            elif line.strip() != '' and line.strip() != 'ok' and not line.startswith('Resend:') and not line.startswith(
                    'Error:checksum mismatch') and not line.startswith(
                    'Error:Line Number is not Last Line Number+1') and line != 'echo:Unknown command:""\n' and self.isOperational():
                self._callback.mcMessage(line)

            if self._state == self.STATE_DETECT_BAUDRATE or self._state == self.STATE_DETECT_SERIAL:
                if line == '' or time.time() > timeout:
                    if len(self._baudrateDetectList) < 1:
                        self.close()
                        self._errorValue = "No more baudrates to test, and no suitable baudrate found."
                        self._changeState(self.STATE_ERROR)
                    elif self._baudrateDetectRetry > 0:
                        self._baudrateDetectRetry -= 1
                        self._serial.write('\n')
                        self._log("Baudrate test retry: %d" % (self._baudrateDetectRetry))
                        self._sendCommand("M105")
                        self._testingBaudrate = True
                    else:
                        if self._state == self.STATE_DETECT_SERIAL:
                            if len(self._serialDetectList) == 0:
                                if len(self._baudrateDetectList) == 0:
                                    self._log(
                                        "Tried all serial ports and baudrates, but still not printer found that responds to M105.")
                                    self._errorValue = 'Failed to autodetect serial port.'
                                    self._changeState(self.STATE_ERROR)
                                    return
                                else:
                                    self._serialDetectList = serialList(True)
                                    baudrate = self._baudrateDetectList.pop(0)
                            self._serial.close()
                            self._serial = serial.Serial(self._serialDetectList.pop(0), baudrate, timeout=2.5,
                                                         writeTimeout=10000)
                        else:
                            baudrate = self._baudrateDetectList.pop(0)
                        try:
                            self._setBaudrate(baudrate)
                            self._serial.timeout = 0.5
                            self._log("Trying baudrate: %d" % (baudrate))
                            self._baudrateDetectRetry = 5
                            self._baudrateDetectTestOk = 0
                            timeout = time.time() + 5
                            self._serial.write('\n')
                            self._sendCommand("M105")
                            self._testingBaudrate = True
                        except:
                            self._log(
                                "Unexpected error while setting baudrate: %d %s" % (baudrate, getExceptionString()))
                elif 'T:' in line:
                    self._baudrateDetectTestOk += 1
                    if self._baudrateDetectTestOk < 10:
                        self._log("Baudrate test ok: %d" % (self._baudrateDetectTestOk))
                        self._sendCommand("M105")
                    else:
                        self._sendCommand("M999")
                        self._serial.timeout = 2
                        profile.putMachineSetting('serial_baud_auto', self._serial.baudrate)
                        print self._serial
                        self._changeState(self.STATE_OPERATIONAL)
                        break
                else:
                    self._testingBaudrate = False
            elif self._state == self.STATE_CONNECTING:
                if line == '' or 'wait' in line:  # 'wait' needed for Repetier (kind of watchdog)
                    self._sendCommand("M105")
                elif 'ok' in line:
                    self._changeState(self.STATE_OPERATIONAL)
                if time.time() > timeout:
                    self.close()
            elif self._state == self.STATE_OPERATIONAL:
                # Request the temperature on comm timeout (every 2 seconds) when we are not printing.
                if line == '':
                    if self._extruderCount > 0:
                        self._temperatureRequestExtruder = (self._temperatureRequestExtruder + 1) % self._extruderCount
                        self.sendCommand("M105 T%d" % (self._temperatureRequestExtruder))
                    else:
                        self.sendCommand("M105")
                    tempRequestTimeout = time.time() + 5
            elif self._state == self.STATE_PRINTING:
                # Even when printing request the temperature every 5 seconds.
                if time.time() > tempRequestTimeout:
                    if self._extruderCount > 0:
                        self._temperatureRequestExtruder = (self._temperatureRequestExtruder + 1) % self._extruderCount
                        self.sendCommand("M105 T%d" % (self._temperatureRequestExtruder))
                    else:
                        self.sendCommand("M105")
                    tempRequestTimeout = time.time() + 5
                if line == '' and time.time() > timeout:
                    self._log("Communication timeout during printing, forcing a line")
                    line = 'ok'
                if 'ok' in line:
                    timeout = time.time() + 5
                    if not self._commandQueue.empty():
                        self._sendCommand(self._commandQueue.get())
                    else:
                        self._sendNext()
                elif "resend" in line.lower() or "rs" in line:
                    try:
                        self._gcodePos = int(line.replace("N:", " ").replace("N", " ").replace(":", " ").split()[-1])
                    except:
                        if "rs" in line:
                            self._gcodePos = int(line.split()[1])
        self._log("Connection closed, closing down monitor")

    def _setBaudrate(self, baudrate):
        try:
            self._serial.baudrate = baudrate
        except:
            print getExceptionString()

    def _log(self, message):
        self._callback.mcLog(message)
        try:
            self._logQueue.put(message, False)
        except:
            # If the log queue is full, remove the first message and append the new message again
            self._logQueue.get()
            try:
                self._logQueue.put(message, False)
            except:
                pass

    def _readline(self):
        if self._serial is None:
            return None
        try:
            ret = self._serial.readline()
        except:
            self._log("Unexpected error while reading serial port: %s" % (getExceptionString()))
            self._errorValue = getExceptionString()
            self.close(True)
            return None
        if ret == '':
            # self._log("Recv: TIMEOUT")
            return ''
        self._log("Recv: %s" % (unicode(ret, 'ascii', 'replace').encode('ascii', 'replace').rstrip()))
        return ret

    def close(self, isError=False):
        if self._serial != None:
            self._serial.close()
            if isError:
                self._changeState(self.STATE_CLOSED_WITH_ERROR)
            else:
                self._changeState(self.STATE_CLOSED)
        self._serial = None

    def __del__(self):
        self.close()

    def _sendCommand(self, cmd):
        if self._serial is None:
            return
        if 'M109' in cmd or 'M190' in cmd:
            self._heatupWaitStartTime = time.time()
        if 'M104' in cmd or 'M109' in cmd:
            try:
                t = 0
                if 'T' in cmd:
                    t = int(re.search('T([0-9]+)', cmd).group(1))
                self._targetTemp[t] = float(re.search('S([0-9]+)', cmd).group(1))
            except:
                pass
        if 'M140' in cmd or 'M190' in cmd:
            try:
                self._bedTargetTemp = float(re.search('S([0-9]+)', cmd).group(1))
            except:
                pass
        self._log('Send: %s' % (cmd))
        try:
            self._serial.write(cmd + '\n')
        except serial.SerialTimeoutException:
            self._log("Serial timeout while writing to serial port, trying again.")
            try:
                time.sleep(0.5)
                self._serial.write(cmd + '\n')
            except:
                self._log("Unexpected error while writing serial port: %s" % (getExceptionString()))
                self._errorValue = getExceptionString()
                self.close(True)
        except:
            self._log("Unexpected error while writing serial port: %s" % (getExceptionString()))
            self._errorValue = getExceptionString()
            self.close(True)

    def _sendNext(self):
        if self._gcodePos >= len(self._gcodeList):
            self._changeState(self.STATE_OPERATIONAL)
            return
        if self._gcodePos == 100:
            self._printStartTime100 = time.time()
        line = self._gcodeList[self._gcodePos]
        if type(line) is tuple:
            self._printSection = line[1]
            line = line[0]
        try:
            if line == 'M0' or line == 'M1':
                # self.setPause(True)
                line = 'M105'  # Don't send the M0 or M1 to the machine, as M0 and M1 are handled as an LCD menu pause.
            if self._printSection in self._feedRateModifier:
                line = re.sub('F([0-9]*)',
                              lambda m: 'F' + str(int(int(m.group(1)) * self._feedRateModifier[self._printSection])),
                              line)
            if ('G0' in line or 'G1' in line) and 'Z' in line:
                z = float(re.search('Z([0-9\.]*)', line).group(1))
                if self._currentZ != z:
                    self._currentZ = z
                    self._callback.mcZChange(z)
        except:
            self._log("Unexpected error: %s" % (getExceptionString()))
        checksum = reduce(lambda x, y: x ^ y, map(ord, "N%d%s" % (self._gcodePos, line)))
        self._sendCommand("N%d%s*%d" % (self._gcodePos, line, checksum))
        self._gcodePos += 1
        self._callback.mcProgress(self._gcodePos)

    def sendCommand(self, cmd):
        cmd = cmd.encode('ascii', 'replace')
        if self.isPrinting():
            self._commandQueue.put(cmd)
        elif self.isOperational():
            self._sendCommand(cmd)

    def printGCode(self, gcodeList):
        if not self.isOperational() or self.isPrinting():
            return
        self._gcodeList = gcodeList
        self._gcodePos = 0
        self._printStartTime100 = None
        self._printSection = 'CUSTOM'
        self._changeState(self.STATE_PRINTING)
        self._printStartTime = time.time()
        for i in xrange(0, 4):
            self._sendNext()

    def cancelPrint(self):
        if self.isOperational():
            self._changeState(self.STATE_OPERATIONAL)

    def setPause(self, pause):
        if not pause and self.isPaused():
            self._changeState(self.STATE_PRINTING)
            for i in xrange(0, 6):
                self._sendNext()
        if pause and self.isPrinting():
            self._changeState(self.STATE_PAUSED)

    def setFeedrateModifier(self, type, value):
        self._feedRateModifier[type] = value

    def readFirstLine(self):
        if self.isOperational():
            print self._port
            port = self._port
            ser = self._serial
            ser.close()
            ser = serial.Serial(
            port=port,\
            baudrate=250000,\
            parity=serial.PARITY_NONE,\
            stopbits=serial.STOPBITS_ONE,\
            bytesize=serial.EIGHTBITS,\
                timeout=2)

            print ser
            print("connected to: " + ser.portstr)

            line = []

            self._version = ser.read(8)
            print self._version

            ser.close()


    def getFirmwareHardware(self):
        ver = self._version

        if profile.getMachineSetting('machine_type') != 'BCN3DSigma' and profile.getMachineSetting(
                'machine_type') != 'BCN3DPlus' and profile.getMachineSetting('machine_type') != 'BCN3DR':
            wx.MessageBox(_("I am sorry, but Cura does not process firmware updates for your machine configuration."),
                          _("Firmware update"), wx.OK | wx.ICON_ERROR)
            return
        elif profile.getMachineSetting('machine_type') == 'BCN3DSigma' or profile.getMachineSetting(
                'machine_type') == 'BCN3DPlus' or profile.getMachineSetting('machine_type') == 'BCN3DR':
            myVersion = version.getLatestFHVersion(ver)

            if myVersion == None:
                return

            if version.downloadLatestFHVersion != None:
                org = os.getcwd()
                if sys.platform.startswith('win'):
                    self._dir = os.getcwd() + '\Compiled Firmware'
                    os.chdir(self._dir)
                elif sys.platform.startswith('darwin'):
                    self._dir = os.getcwd() + '/Compiled Firmware/'
                    os.chdir(self._dir)

                for filename in os.listdir(self._dir):
                    if filename.endswith(".hex"):
                        machineCom.InstallFirmware(self, filename)

                for filename in os.listdir(org):
                    if filename.startswith("SD"):
                        choice = wx.MessageBox(_("You need to update the files on your printers SD Card\n"
                                                 "Press 'OK' to learn how to do it."), _("Firmware update"), wx.OK)
                        if choice == wx.OK:
                            webbrowser.open(
                                'https://github.com/BCN3D/BCN3D-Cura-Windows/wiki/Updating-the-SD-Files-from-the-LCD-Display')


def getExceptionString():
    locationInfo = traceback.extract_tb(sys.exc_info()[2])[0]
    return "%s: '%s' @ %s:%s:%d" % (
    str(sys.exc_info()[0].__name__), str(sys.exc_info()[1]), os.path.basename(locationInfo[0]), locationInfo[2],
    locationInfo[1])
