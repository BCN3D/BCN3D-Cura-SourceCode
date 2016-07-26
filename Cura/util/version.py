"""
The version utility module is used to get the current Cura version, and check for updates.
It can also see if we are running a development build of Cura.
"""
__copyright__ = "Copyright (C) 2013 David Braam - Released under terms of the AGPLv3 License"

import os
import re
import sys
import urllib
import urllib2
import platform
import subprocess
import zipfile
import wx
import ssl
import socket


#Uncomment this line if you are going to do package in MAC version
#ssl._create_default_https_context = ssl._create_unverified_context

try:
    from xml.etree import cElementTree as ElementTree
except:
    from xml.etree import ElementTree

from Cura.util import resources
import profile

def getVersion(getGitVersion = True):
    gitPath = os.path.abspath(os.path.join(os.path.split(os.path.abspath(__file__))[0], "../.."))
    if hasattr(sys, 'frozen'):
        versionFile = os.path.normpath(os.path.join(resources.resourceBasePath, "version"))
    else:
        versionFile = os.path.abspath(os.path.join(os.path.split(os.path.abspath(__file__))[0], "../version"))

    if getGitVersion:
        try:
            gitProcess = subprocess.Popen(args = "git show -s --pretty=format:%H", shell = True, cwd = gitPath, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
            (stdoutdata, stderrdata) = gitProcess.communicate()

            if gitProcess.returncode == 0:
                return stdoutdata
        except:
            pass

    gitHeadFile = gitPath + "/.git/refs/heads/SteamEngine"
    if os.path.isfile(gitHeadFile):
        if not getGitVersion:
            return "dev"
        f = open(gitHeadFile, "r")
        version = f.readline()
        f.close()
        return version.strip()
    if os.path.exists(versionFile):
        f = open(versionFile, "r")
        version = f.readline()
        f.close()
        return version.strip()
    versionFile = os.path.abspath(os.path.join(os.path.split(os.path.abspath(__file__))[0], "../../version"))
    if os.path.exists(versionFile):
        f = open(versionFile, "r")
        version = f.readline()
        f.close()
        return version.strip()
    return "UNKNOWN" #No idea what the version is. TODO:Tell the user.

def isDevVersion():
    gitPath = os.path.abspath(os.path.join(os.path.split(os.path.abspath(__file__))[0], "../../.git"))
    hgPath  = os.path.abspath(os.path.join(os.path.split(os.path.abspath(__file__))[0], "../../.hg"))
    return os.path.exists(gitPath) or os.path.exists(hgPath)

##############################################
def getLatestFHVersion(ver):
 
    #Go to a different url depending on the printer to get the desired firmware
    if profile.getMachineSetting('machine_type') == 'BCN3DSigma':
 
        if haveInternet() != True:
            wx.MessageBox(_("It seems like you do not have an internet connection.\n"
                            "In order to check whether you have the latest version\n"
                            "you need to be connected to the internet.\n\n"
                            "Please check your connection and try again!"), _("Alert!"), wx.OK | wx.ICON_EXCLAMATION)
        elif haveInternet() == True:
            base_url = 'https://github.com/BCN3D/BCN3DSigma-Firmware/archive/'
            url = 'https://github.com/BCN3D/BCN3DSigma-Firmware/releases'
            urlContent = urllib2.urlopen(url)
            data = urlContent.read()
 
 
            first_v = ver[:2]
            second_v = ver[:2]
 
            if first_v == '01':
                versionMatch = re.search(r'(01-[\d.]+)\.(zip)', data)
                if not versionMatch:
                    sys.exit('Couldn\'t find the Latest Version!')
                version = versionMatch.group(1)
                print 'The latest firmware version available is:',version
                print ver
 
                if ver == version:
                    wx.MessageBox(_("Your firmware is already up to date!"), _("Firmware Information"), wx.OK)
                    return None
 
                elif ver != version:
                    mychoice = wx.MessageBox(_("Your firmware version is: " + ver + "\nThe latest firmware version available is: " + version + "\nWant to download the new version?"), _("New Version"), wx.YES_NO | wx.ICON_QUESTION)
 
                    if mychoice == wx.NO:
                        return None
                    else:
                        isDownloaded = downloadLatestFHVersion(version, base_url)
                        if isDownloaded == None:
                            return None
                        elif isDownloaded != None:
                            return version
 
            elif second_v == '02':
                versionMatch = re.search(r'(02-[\d.]+)\.(zip)', data)
                if not versionMatch:
                    sys.exit('Couldn\'t find the Latest Version!')
                version = versionMatch.group(1)
                print 'The latest firmware version available is:',version
 
                if ver == version:
                    wx.MessageBox(_("Your firmware is already up to date!"), _("Firmware Information"), wx.OK)
                    return None
 
                elif ver != version:
                    mychoice = wx.MessageBox(_("Your firmware version is: " + ver + "\nThe latest firmware version available is: " + version + "\nWant to download the new version?"), _("New Version"), wx.YES_NO)
 
                    if mychoice == wx.NO:
                        return None
                    else:
                        isDownloaded = downloadLatestFHVersion(version, base_url)
                        if isDownloaded == None:
                            return None
                        elif isDownloaded != None:
                            return version

    elif profile.getMachineSetting('machine_type') == 'BCN3DPlus':
        wx.MessageBox(_("Couldn\'t find the latest version!"), _("Firmware Information"), wx.OK)
        return None
 
    elif profile.getMachineSetting('machine_type') == 'BCN3DR':
        wx.MessageBox(_("Couldn\'t find the latest version!"), _("Firmware Information"), wx.OK)
        return None
 
def haveInternet():
    REMOTE_SERVER = "www.google.com"
    try:
        host = socket.gethostbyname(REMOTE_SERVER)
        s = socket.create_connection((host, 443))
        return True
    except:
        pass
    return False
 
def downloadLatestFHVersion(version,base_url):
 
    version_url = base_url + version + '.zip'
    print version_url
 
    if sys.platform.startswith('win'):
        os.chdir(os.path.expanduser('~') + '\Downloads')
    elif sys.platform.startswith('darwin'):
        os.chdir(os.path.expanduser('~') + '/Downloads')
 
    myVar = firmwareHAlreadyInstalled(version)
 
    if myVar != None:
        print 'Downloading Version... ',version
        urllib.urlretrieve(version_url, version + '.zip')
        print 'Done downloading!'
 
        print 'Inflating files...'
 
        if sys.platform.startswith('win'):
            os.chdir(os.path.expanduser('~') + '\Downloads')
        elif sys.platform.startswith('darwin'):
            os.chdir(os.path.expanduser('~') + '/Downloads')
 
        with zipfile.ZipFile(version + '.zip') as z:
            z.extractall()
        print 'Done unziping the files!'
 
        if sys.platform.startswith('win'):
            os.chdir(os.path.expanduser('~') + '\Downloads\BCN3DSigma-Firmware-' + version)
        elif sys.platform.startswith('darwin'):
            os.chdir(os.path.expanduser('~') + '/Downloads/BCN3DSigma-Firmware-'+version)
 
        return version
 
    elif myVar == None:
        return None
 
def firmwareHAlreadyInstalled(version):
 
    if sys.platform.startswith('win'):
        os.chdir(os.path.expanduser('~') + '\Downloads')
    elif sys.platform.startswith('darwin'):
        os.chdir(os.path.expanduser('~') + '/Downloads')
 
    print 'la cosa de los downloads',version
    fname = version + '.zip'
    print fname
    if sys.platform.startswith('win'):
        dir = os.path.expanduser('~') + '\Downloads'
        yes = fname in os.listdir(dir)
        if yes == True:
 
            print 'Repositories up to date!'
            wx.MessageBox(_(
                "You already have the newest version downloaded.\nIf you wish to reinstall the firmware please go to\n"
                "Machine -> Install custom firmware\n"
                "and find the path to the file, which should be in the Downloads folder"),
                          _("Repository Information"), wx.OK)
            return None
        else:
            print 'Entramos en none porque fname es', yes
            return not None
    elif sys.platform.startswith('darwin'):
        dir = os.path.expanduser('~') + '/Downloads/'
        yes = fname in os.listdir(dir)
 
        if yes == True:
            print 'Repositories up to date!'
            wx.MessageBox(_(
                "You already have the newest version downloaded.\nIf you wish to reinstall the firmware please go to\n"
                "Machine -> Install custom firmware\n"
                "and find the path to the file, which should be in the Downloads folder"),
                          _("Repository Information"), wx.OK)
            return None
        else:
            print 'Entramos en none porque fname es', yes
            return not None
 
 
 
 
#######################################################################

def checkForNewerVersion():
    if isDevVersion():
        return None
    try:
        updateBaseURL = 'http://software.ultimaker.com'
        localVersion = map(int, getVersion(False).split('.'))
        while len(localVersion) < 3:
            localVersion += [1]
        latestFile = urllib2.urlopen("%s/latest.xml" % (updateBaseURL))
        latestXml = latestFile.read()
        latestFile.close()
        xmlTree = ElementTree.fromstring(latestXml)
        for release in xmlTree.iter('release'):
            os = str(release.attrib['os'])
            version = [int(release.attrib['major']), int(release.attrib['minor']), int(release.attrib['revision'])]
            filename = release.find("filename").text
            if platform.system() == os:
                if version > localVersion:
                    return "%s/current/%s" % (updateBaseURL, filename)
    except:
        #print sys.exc_info()
        return None
    return None

#############################################################################
 
def checkForNewVersion():
 
    ver = getVersion()
 
    print 'My current version is ', ver
    
    if sys.platform.startswith('win'):
        url = 'https://github.com/BCN3D/BCN3D-Cura-Windows/releases'
        urlContent = urllib2.urlopen(url)
        data = urlContent.read()
 
        versionMatch = re.search(r'([\d.]+)\.(zip)', data)
 
        if not versionMatch:
            sys.exit('Couldn\'t find the Latest Version!')
        version = versionMatch.group(1)
        print 'The latest Cura-BCN3D version available is:',version
 
        if ver == version:
            return None
 
        elif ver != version:
            return "%s/tag/%s" % (url, version)
 
    elif sys.platform.startswith('darwin'):
        url = 'https://github.com/BCN3D/BCN3D-Cura-Mac/releases'
        urlContent = urllib2.urlopen(url)
        data = urlContent.read()
 
        versionMatch = re.search(r'([\d.]+)\.(zip)', data)
 
        if not versionMatch:
            sys.exit('Couldn\'t find the Latest Version!')
        version = versionMatch.group(1)
        print 'The latest Cura-BCN3D version available is:',version
 
        if ver == version:
            return None
 
        elif ver != version:
            return "%s/tag/%s" % (url, version)

if __name__ == '__main__':
    print(getVersion())
