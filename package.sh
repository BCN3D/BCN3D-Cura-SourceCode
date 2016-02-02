#!/usr/bin/env bash

set -e
set -u

# This script is to package the Cura package for Windows/Linux and Mac OS X
# This script should run under Linux and Mac OS X, as well as Windows with Cygwin.

#############################
# CONFIGURATION
#############################

##Select the build target
#BUILD_TARGET=${1:-none}
#BUILD_TARGET=win32
BUILD_TARGET=darwin
#BUILD_TARGET=debian_i386
#BUILD_TARGET=debian_amd64
#BUILD_TARGET=debian_armhf
#BUILD_TARGET=freebsd

##Do we need to create the final archive
ARCHIVE_FOR_DISTRIBUTION=1
##Which version name are we appending to the final archive
export BUILD_NAME=0.1.4
TARGET_DIR=Cura-BCN3D-${BUILD_NAME}

##Which versions of external programs to use
WIN_PORTABLE_PY_VERSION=2.7.2.1

##Which CuraEngine to use
if [ -z ${CURA_ENGINE_REPO:-} ]; then
	CURA_ENGINE_REPO="https://github.com/Ultimaker/CuraEngine.git"
fi
if [ -z ${CURA_ENGINE_REPO_PUSHURL:-} ]; then
	CURA_ENGINE_REPO_PUSHURL="git@github.com:Ultimaker/CuraEngine.git"
fi
if [ -z ${CURA_ENGINE_BRANCH:-} ]; then
	CURA_ENGINE_BRANCH="legacy"
fi

JOBS=${JOBS:-3}

#############################
# Support functions
#############################
function checkTool
{
	if [ -z "`which $1`" ]; then
		echo "The $1 command must be somewhere in your \$PATH."
		echo "Fix your \$PATH or install $2"
		exit 1
	fi
}

function downloadURL
{
	filename=`basename "$1"`
	echo "Checking for $filename"
	if [ ! -f "$filename" ]; then
		echo "Downloading $1"
		curl -L -O "$1"
		if [ $? != 0 ]; then
			echo "Failed to download $1"
			exit 1
		fi
	fi
}

function extract
{
	echo "Extracting $*"
	echo "7z x -y $*" >> log.txt
	7z x -y $* >> log.txt
	if [ $? != 0 ]; then
        echo "Failed to extract $*"
        exit 1
	fi
}

function gitClone
{
	echo "Cloning $1 into $3"
	echo "  with push URL $2"
	if [ -d $3 ]; then
		cd $3
		git clean -dfx
		git reset --hard
		if [ ! -z "${4-}" ]; then
			git checkout $4
		fi
		git pull
		cd -
	else
		if [ ! -z "${4-}" ]; then
			git clone $1 $3 --branch $4
		else
			git clone $1 $3
		fi
		git config remote.origin.pushurl "$2"
	fi
}

#############################
# Actual build script
#############################
if [ "$BUILD_TARGET" = "none" ]; then
	echo "You need to specify a build target with:"
	echo "$0 win32"
	echo "$0 debian_i386"
	echo "$0 debian_amd64"
	echo "$0 debian_armhf"
	echo "$0 darwin"
	echo "$0 freebsd"
	echo "$0 fedora                         # current   system"
	echo "$0 fedora \"mock_config_file\" ...  # different system(s)"
	exit 0
fi

if [ -z `which make` ]; then
	MAKE=mingw32-make
else
	MAKE=make
fi

# Change working directory to the directory the script is in
# http://stackoverflow.com/a/246128
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

checkTool git "git: http://git-scm.com/"
checkTool curl "curl: http://curl.haxx.se/"
if [ $BUILD_TARGET = "win32" ]; then
	checkTool avr-gcc "avr-gcc: http://winavr.sourceforge.net/ "
	#Check if we have 7zip, needed to extract and packup a bunch of packages for windows.
	checkTool 7z "7zip: http://www.7-zip.org/"
	checkTool $MAKE "mingw: http://www.mingw.org/"
fi
#For building under MacOS we need gnutar instead of tar
if [ -z `which gnutar` ]; then
	TAR=tar
else
	TAR=gnutar
fi

#############################
# Build the required firmwares
#############################

#############################
# Darwin
#############################

if [ "$BUILD_TARGET" = "darwin" ]; then
    TARGET_DIR=Cura-BCN3D-${BUILD_NAME}

	rm -rf scripts/darwin/build
	rm -rf scripts/darwin/dist

	python build_app.py py2app
	rc=$?
	if [[ $rc != 0 ]]; then
		echo "Cannot build app."
		exit 1
	fi

    #Add cura version file (should read the version from the bundle with pyobjc, but will figure that out later)
    echo $BUILD_NAME > scripts/darwin/dist/Cura-BCN3D.app/Contents/Resources/version
	rm -rf CuraEngine
	gitClone \
	  ${CURA_ENGINE_REPO} \
	  ${CURA_ENGINE_REPO_PUSHURL} \
	  CuraEngine \
	  ${CURA_ENGINE_BRANCH}
    if [ $? != 0 ]; then echo "Failed to clone CuraEngine"; exit 1; fi
	$MAKE -C CuraEngine VERSION=${BUILD_NAME}
    if [ $? != 0 ]; then echo "Failed to build CuraEngine"; exit 1; fi
	cp CuraEngine/build/CuraEngine scripts/darwin/dist/Cura-BCN3D.app/Contents/Resources/CuraEngine

	cd scripts/darwin

	# Install QuickLook plugin
	mkdir -p dist/Cura-BCN3D.app/Contents/Library/QuickLook
	cp -a STLQuickLook.qlgenerator dist/Cura-BCN3D.app/Contents/Library/QuickLook/

	# Archive app
	cd dist
	$TAR cfp - Cura-BCN3D.app | gzip --best -c > ../../../${TARGET_DIR}.tar.gz
	cd ..

	# Create sparse image for distribution
	hdiutil detach /Volumes/Cura\ -\ Ultimaker/ || true
	rm -rf Cura-BCN3D.dmg.sparseimage
	hdiutil convert DmgTemplateCompressed.dmg -format UDSP -o Cura-BCN3D.dmg
	hdiutil resize -size 500m Cura-BCN3D.dmg.sparseimage
	hdiutil attach Cura-BCN3D.dmg.sparseimage
	cp -a dist/Cura-BCN3D.app /Volumes/Cura\ -\ Ultimaker/Cura/
	hdiutil detach /Volumes/Cura\ -\ Ultimaker
	hdiutil convert Cura-BCN3D.dmg.sparseimage -format UDZO -imagekey zlib-level=9 -ov -o ../../${TARGET_DIR}.dmg
	exit
fi

#############################
# Rest
#############################

#############################
# Download all needed files.
#############################

if [ $BUILD_TARGET = "win32" ]; then
	#Get portable python for windows and extract it. (Linux and Mac need to install python themselfs)
	downloadURL http://ftp.nluug.nl/languages/python/portablepython/v2.7/PortablePython_${WIN_PORTABLE_PY_VERSION}.exe
	downloadURL http://sourceforge.net/projects/pyserial/files/pyserial/2.5/pyserial-2.5.win32.exe
	downloadURL http://sourceforge.net/projects/pyopengl/files/PyOpenGL/3.0.1/PyOpenGL-3.0.1.win32.exe
	downloadURL http://sourceforge.net/projects/numpy/files/NumPy/1.6.2/numpy-1.6.2-win32-superpack-python2.7.exe
	downloadURL http://videocapture.sourceforge.net/VideoCapture-0.9-5.zip
	#downloadURL http://ffmpeg.zeranoe.com/builds/win32/static/ffmpeg-20120927-git-13f0cd6-win32-static.7z
	downloadURL http://sourceforge.net/projects/comtypes/files/comtypes/0.6.2/comtypes-0.6.2.win32.exe
	downloadURL http://www.uwe-sieber.de/files/ejectmedia.zip
	#Get the power module for python
	gitClone \
	  https://github.com/GreatFruitOmsk/Power \
	  git@github.com:GreatFruitOmsk/Power \
	  Power
    if [ $? != 0 ]; then echo "Failed to clone Power"; exit 1; fi
	gitClone \
	  ${CURA_ENGINE_REPO} \
	  ${CURA_ENGINE_REPO_PUSHURL} \
	  CuraEngine
    if [ $? != 0 ]; then echo "Failed to clone CuraEngine"; exit 1; fi
fi

#############################
# Build the packages
#############################
rm -rf ${TARGET_DIR}
mkdir -p ${TARGET_DIR}

rm -f log.txt
if [ $BUILD_TARGET = "win32" ]; then
	if [ -z `which i686-w64-mingw32-g++` ]; then
		CXX=g++
	else
		CXX=i686-w64-mingw32-g++
	fi

	#For windows extract portable python to include it.
	extract PortablePython_${WIN_PORTABLE_PY_VERSION}.exe \$_OUTDIR/App
	extract PortablePython_${WIN_PORTABLE_PY_VERSION}.exe \$_OUTDIR/Lib/site-packages
	extract pyserial-2.5.win32.exe PURELIB
	extract PyOpenGL-3.0.1.win32.exe PURELIB
	extract numpy-1.6.2-win32-superpack-python2.7.exe numpy-1.6.2-sse2.exe
	extract numpy-1.6.2-sse2.exe PLATLIB
	extract VideoCapture-0.9-5.zip VideoCapture-0.9-5/Python27/DLLs/vidcap.pyd
	#extract ffmpeg-20120927-git-13f0cd6-win32-static.7z ffmpeg-20120927-git-13f0cd6-win32-static/bin/ffmpeg.exe
	#extract ffmpeg-20120927-git-13f0cd6-win32-static.7z ffmpeg-20120927-git-13f0cd6-win32-static/licenses
	extract comtypes-0.6.2.win32.exe
	extract ejectmedia.zip Win32

	mkdir -p ${TARGET_DIR}/python
	mkdir -p ${TARGET_DIR}/Cura/
	mv \$_OUTDIR/App/* ${TARGET_DIR}/python
	mv \$_OUTDIR/Lib/site-packages/wx* ${TARGET_DIR}/python/Lib/site-packages/
	mv PURELIB/serial ${TARGET_DIR}/python/Lib
	mv PURELIB/OpenGL ${TARGET_DIR}/python/Lib
	mv PURELIB/comtypes ${TARGET_DIR}/python/Lib
	mv PLATLIB/numpy ${TARGET_DIR}/python/Lib
	mv Power/power ${TARGET_DIR}/python/Lib
	mv VideoCapture-0.9-5/Python27/DLLs/vidcap.pyd ${TARGET_DIR}/python/DLLs
	#mv ffmpeg-20120927-git-13f0cd6-win32-static/bin/ffmpeg.exe ${TARGET_DIR}/Cura/
	#mv ffmpeg-20120927-git-13f0cd6-win32-static/licenses ${TARGET_DIR}/Cura/ffmpeg-licenses/
	mv Win32/EjectMedia.exe ${TARGET_DIR}/Cura/

	rm -rf Power/
	rm -rf \$_OUTDIR
	rm -rf PURELIB
	rm -rf PLATLIB
	rm -rf VideoCapture-0.9-5
	rm -rf numpy-1.6.2-sse2.exe
	#rm -rf ffmpeg-20120927-git-13f0cd6-win32-static

	#Clean up portable python a bit, to keep the package size down.
	rm -rf ${TARGET_DIR}/python/PyScripter.*
	rm -rf ${TARGET_DIR}/python/Doc
	rm -rf ${TARGET_DIR}/python/locale
	rm -rf ${TARGET_DIR}/python/tcl
	rm -rf ${TARGET_DIR}/python/Lib/test
	rm -rf ${TARGET_DIR}/python/Lib/distutils
	rm -rf ${TARGET_DIR}/python/Lib/site-packages/wx-2.8-msw-unicode/wx/tools
	rm -rf ${TARGET_DIR}/python/Lib/site-packages/wx-2.8-msw-unicode/wx/locale
	#Remove the gle files because they require MSVCR71.dll, which is not included. We also don't need gle, so it's safe to remove it.
	rm -rf ${TARGET_DIR}/python/Lib/OpenGL/DLLS/gle*

    #Build the C++ engine
	$MAKE -C CuraEngine VERSION=${BUILD_NAME} OS=Windows_NT CXX=${CXX}
    if [ $? != 0 ]; then echo "Failed to build CuraEngine"; exit 1; fi
fi

#add Cura
mkdir -p ${TARGET_DIR}/Cura ${TARGET_DIR}/resources ${TARGET_DIR}/plugins
cp -a Cura/* ${TARGET_DIR}/Cura
cp -a resources/* ${TARGET_DIR}/resources
cp -a plugins/* ${TARGET_DIR}/plugins
#Add cura version file
echo $BUILD_NAME > ${TARGET_DIR}/Cura/version

#add script files
if [ $BUILD_TARGET = "win32" ]; then
    cp -a scripts/${BUILD_TARGET}/*.bat $TARGET_DIR/
    cp CuraEngine/build/CuraEngine.exe $TARGET_DIR
	cp /usr/lib/gcc/i686-w64-mingw32/4.8/libgcc_s_sjlj-1.dll $TARGET_DIR
    cp /usr/i686-w64-mingw32/lib/libwinpthread-1.dll $TARGET_DIR
    cp /usr/lib/gcc/i686-w64-mingw32/4.8/libstdc++-6.dll $TARGET_DIR
fi

#package the result
if (( ${ARCHIVE_FOR_DISTRIBUTION} )); then
	if [ $BUILD_TARGET = "win32" ]; then
		#rm ${TARGET_DIR}.zip
		#cd ${TARGET_DIR}
		#7z a ../${TARGET_DIR}.zip *
		#cd ..

		if [ ! -z `which wine` ]; then
			#if we have wine, try to run our nsis script.
			rm -rf scripts/win32/dist
			ln -sf `pwd`/${TARGET_DIR} scripts/win32/dist
			wine ~/.wine/drive_c/Program\ Files\ \(x86\)/NSIS/makensis.exe /DVERSION=${BUILD_NAME} scripts/win32/installer.nsi
            if [ $? != 0 ]; then echo "Failed to package NSIS installer"; exit 1; fi
			mv scripts/win32/Cura-BCN3D-${BUILD_NAME}.exe ./
		fi
		if [ -f '/c/Program Files (x86)/NSIS/makensis.exe' ]; then
			rm -rf scripts/win32/dist
			mv "`pwd`/${TARGET_DIR}" scripts/win32/dist
			'/c/Program Files (x86)/NSIS/makensis.exe' -DVERSION=${BUILD_NAME} 'scripts/win32/installer.nsi' >> log.txt
            if [ $? != 0 ]; then echo "Failed to package NSIS installer"; exit 1; fi
			mv scripts/win32/Cura-BCN3D-${BUILD_NAME}.exe ./
		fi
	else
		echo "Archiving to ${TARGET_DIR}.tar.gz"
		$TAR cfp - ${TARGET_DIR} | gzip --best -c > ${TARGET_DIR}.tar.gz
	fi
else
	echo "Installed into ${TARGET_DIR}"
fi
