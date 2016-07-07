#!/usr/bin/python2

import os
import sys
import shutil

import json
import urllib
import zipfile
import argparse
import subprocess
import HTMLParser
import multiprocessing
import xml.etree.ElementTree


'''
    Common directories and files declarations
'''
USER_HOME = os.path.expanduser("~")

TOOL_DIR = USER_HOME + "/.stm32tool"

TEMPLATES_DIR = TOOL_DIR + "/templates"
TEMP_DIR = TOOL_DIR + "/temp"

MCU_DB_FILE = TOOL_DIR + "/mcu_db.json"


'''
    Common declarations
'''
TABLE_FLASH_SIZE = {
    '4': 16,
    '6': 32,
    '8': 64,
    'B': 128,
    'C': 256,
    'D': 384,
    'E': 512,
    'F': 768,
    'G': 1024,
    'I': 2048,
    'Z': 192
}

WEBSITE_BASE_URL = "http://www.st.com"

MCU_DATABASE_URL = (WEBSITE_BASE_URL +
                    "/content/st_com/en/products/microcontrollers"
                    "/stm32-32-bit-arm-cortex-mcus.product-grid.html"
                    "/SC1169.json")

HAL_PACKAGE_PAGE_URL = (WEBSITE_BASE_URL +
                        "/content/st_com/en/products"
                        "/embedded-software/mcus-embedded-software"
                        "/stm32-embedded-software/stm32cube-embedded-software"
                        "/stm32cube{}{}.html")

HAL_PACKAGE_PAGE_LINK_SEARCH_TAG = 'div' # Search for this kind of HTML tag
HAL_PACKAGE_PAGE_LINK_SEARCH_ATTRS = {'id': 'dlLink'} # With these attributes
HAL_PACKAGE_PAGE_LINK_ATTR = 'data-download-path' # Get link from attribute

class CLIFormat:
    INFO = '\033[34m'
    WARNING = '\033[33m'
    ERROR = '\033[31m\033[1m'
    ROWNAME = '\033[33m\033[1m'
    ENDF = '\033[0m'


'''
    Configuration exceptions
'''
# Sometimes something wrong occurs while selecting the right CMSIS include and
# startup file because the names are different or there is no correct file
# available. For example this happens with the popular STM32F103C8.
# Here we define these exceptions
CMSIS_NAME_EXCEPTIONS = {
    'STM32F103C8': 'STM32F103CB'
}


'''
    Error handling
'''
def INFO(content):
    print CLIFormat.INFO + "[INFO] " + content + CLIFormat.ENDF

def WARNING(content):
    print CLIFormat.WARNING + "[WARNING] " + content + CLIFormat.ENDF

def ERROR(content, extra=None):
    print CLIFormat.ERROR + "[ERROR] " + content + CLIFormat.ENDF
    if extra is not None:
        INFO(extra)
    sys.exit(1)


'''
    Utility functions
'''
# Copies the content of srcDir to dstDir recursively
# NOTE: both directories must exist
def copyDirContent(srcDir, dstDir):
    for f in os.listdir(srcDir):
        if os.path.isdir(srcDir + "/" + f):
            if not os.path.isdir(dstDir + "/" + f):
                os.makedirs(dstDir + "/" + f)
            copyDirContent(srcDir + "/" + f, dstDir + "/" + f)
        else:
            shutil.copyfile(srcDir + "/" + f, dstDir + "/" + f)

# ZIPs the entire content of a directory in a new ZIP file
# NOTE: the ZIP file will have the directory content at its root, it will not
#       contain the specified directory itself
def zipDirContent(path, zipFilename):
    zipHandle = zipfile.ZipFile(zipFilename, 'w', zipfile.ZIP_DEFLATED)
    for root, dirs, files in os.walk(path):
        for file in dirs + files:
            srcFilename = os.path.join(root, file)
            arcFilename = os.path.relpath(os.path.join(root, file),
                                          os.path.join(path, '.'))
            zipHandle.write(srcFilename, arcFilename)
    zipHandle.close()

# Count number of files with specified extensions in 'path', without searching
# in directories listed in 'noDirs'
# Returns a dictionary with the number of files for each extension, and also
# the number of files that do not belong to any of the extensions given. The
# dictionary also contains the total number of files
def countFiles(path, extensions, noDirs=()):
    output = { 'other': 0, 'total': 0 }
    for e in extensions:
        output[e] = 0
    for root, dirs, files in os.walk(path, topdown=True):
        dirs[:] = [d for d in dirs if d not in noDirs]
        if root in noDirs:
            continue
        for f in files:
            extension = f.split('.')[-1]
            if extension in output:
                output[extension] += 1
            else:
                output['other'] += 1
        output['total'] += len(files)
    return output

# Counts the number of code lines in path (searching all subdirectories)
# Considers only files with the given extensions
def countCodeLines(path, extensions):
    count = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            if f.split('.')[-1] in extensions:
                with open(os.path.join(root, f), 'r') as fh:
                    count += sum(1 for line in fh)
    return count

# Return the number of CPU cores of the machine, used to run 'make' on
# multiple cores to improve compiling speed
def getCPUcount():
    return multiprocessing.cpu_count()

# Replace a string in a file with another string
def replaceInFile(filename, search, replace):
    content = None
    with open(filename, 'r') as f:
        content = f.read()
    content = content.replace(search, replace)
    with open(filename, 'w') as f:
        f.write(content)

# Downloads a file and shows a text-based progress bar.
# If 'saveToDisk' is True, the file is saved to 'location' and the complete
# filename is returned, otherwise the file content is returned as a string
def downloadFile(url, saveToDisk=True, location='.'):
    filename = url.split('/')[-1]

    def computeBestSizeUnit(size):
        unit = 'bytes'
        div = 1
        if size >= (1024 / 2):
            unit = 'kB'
            div = 1024
        if size >= (1024 * 1024 / 2):
            unit = 'MB'
            div = 1024 * 1024
        return (unit, div)

    def printProgress(count, blockSize, totalSize):
        if totalSize == -1:
            bytesSoFar = count * blockSize
            sizeUnit = computeBestSizeUnit(bytesSoFar)
            sys.stdout.write("\x1b[2K\rDownloading %s [%.1f %s]" % (filename, float(bytesSoFar) / float(sizeUnit[1]), sizeUnit[0]))
            sys.stdout.flush()
        else:
            bytesSoFar = count * blockSize
            if bytesSoFar > totalSize: totalSize = bytesSoFar
            sizeUnit = computeBestSizeUnit(totalSize)
            percent = int(float(count * blockSize) / float(totalSize) * 100.0)
            sys.stdout.write("\x1b[2K\rDownloading %s [%d%% of %.1f %s]" % (filename, percent, float(totalSize) / float(sizeUnit[1]), sizeUnit[0]))
            sys.stdout.flush()

    if saveToDisk == False:
        if not os.path.isdir(TEMP_DIR):
            os.makedirs(TEMP_DIR)
        location = TEMP_DIR

    completeFilename = location + "/" + filename

    try:
        urllib.urlretrieve(url, completeFilename, reporthook=printProgress)
    except KeyboardInterrupt:
        print "\b\b [INTERRUPTED]"
        if os.path.isfile(completeFilename):
            os.remove(completeFilename)
        return None

    sys.stdout.write('\n')
    sys.stdout.flush()

    if saveToDisk == False:
        content = ""
        with open(completeFilename, 'r') as f:
            content = f.read()
        os.remove(completeFilename)
        return content
    else:
        return completeFilename


'''
    Templates management functions
'''
# Given a template "basename" (the name without extension of the local
# template JSON and ZIP file), return the content of the JSON which provides
# information about the given template
def getTemplateInfo(basename):
    try:
        with open(TEMPLATES_DIR + "/" + basename + ".json") as jsonFile:
            return json.load(jsonFile)
    except:
        return None

# Search for a compatible local template for the specified MCU family and series
def getTemplateBasenameFor(familyID, seriesID):
    for f in os.listdir(TEMPLATES_DIR):
        if not os.path.isfile(TEMPLATES_DIR + "/" + f): continue
        if f.split('.')[-1] == 'json':
            basename = f.split('.')[0]
            info = getTemplateInfo(basename)
            if info is None: continue
            if  (int(info['familyID']) == familyID) and \
                (int(info['seriesID']) == seriesID):
                return basename
    return None


'''
    HAL package fetching functions
'''
# Find the download link for the HAL package required by
# the specified MCU family and series
def getHALDownloadLink(familyID, seriesID):

    def compareAttributes(attrs, mustMatch):
        found = True
        for search in mustMatch:
            if not search in attrs:
                found = False
            elif attrs[search] != mustMatch[search]:
                found = False
            if found == False: break
        return found

    class PackagePageHTMLParser(HTMLParser.HTMLParser):
        def __init__(self):
            HTMLParser.HTMLParser.__init__(self)
            self.downloadLink = None
        def handle_starttag(self, tag, tupledAttrs):
            if tag != HAL_PACKAGE_PAGE_LINK_SEARCH_TAG: return
            attrs = { key: value for (key, value) in tupledAttrs }
            if compareAttributes(attrs, HAL_PACKAGE_PAGE_LINK_SEARCH_ATTRS):
                link = WEBSITE_BASE_URL + attrs[HAL_PACKAGE_PAGE_LINK_ATTR]
                self.downloadLink = link

    packagePageParser = PackagePageHTMLParser()

    familyLetter = 'F' if familyID == 0 else 'L'
    url = HAL_PACKAGE_PAGE_URL.format(familyLetter.lower(), seriesID)

    response = downloadFile(url, saveToDisk=False)
    if response is None:
        return None
    packagePageParser.feed(response)

    return packagePageParser.downloadLink


'''
    MCU model selection functions (used during project creation)
'''
# This function compares a MCU name to names that contain 'X' in them, like
# for example STM32F072XB. It is used to select the right CMSIS startup and
# include file from the available ones in a template package
def compareNames(reference, nameToCheck):
    if len(reference) != len(nameToCheck): return False
    for i in range(len(reference)):
        if reference.lower()[i] != 'x':
            if reference.lower()[i] != nameToCheck.lower()[i]:
                return False
    return True

# Return all the CMSIS 'models' available
def getAvailableModels(projectDir):
    models = []
    for f in os.listdir(projectDir + "/system/cmsis"):
        if len(f.split('.')[0]) >= 11 and f[0:5].lower() == "stm32":
            models.append(f.split('.')[0])
    return models

# Return the right CMSIS startup and include file for the specified MCU name
def getModelFileForMCU(projectDir, mcuName):
    if mcuName in CMSIS_NAME_EXCEPTIONS:
        mcuName = CMSIS_NAME_EXCEPTIONS[mcuName]
    models = getAvailableModels(projectDir)
    for model in models:
        if compareNames(model, mcuName):
            return model
    return None

# Return the name of the CMSIS device family include file,
# for example 'stm32f0xx.h'
def getCMSISinclude(projectDir):
    for f in os.listdir(projectDir + "/system/cmsis"):
        if len(f.split('.')[0]) == 9 and f[0:5].lower() == "stm32":
            return f


'''
    MCU database management functions
'''
# Download the latest MCU database, parse it and save a local database
# with just the useful fields (to reduce size and DB management complessity).
# Return the new database JSON/dictionary object
def updateMCUdatabase():

    def getColumnValue(row, columnID):
        for cell in row['cells']:
            if int(cell['columnId']) == columnID:
                return cell['value']
        return None

    newDB = { }

    try:
        stringData = downloadFile(MCU_DATABASE_URL, saveToDisk=False)
        if stringData is None:
            return None
        data = json.loads(stringData)
        columnIDs = {'name': 1}
        for column in data['columns']:
            if "FLASH" in column['name']:
                columnIDs['flash'] = int(column['id'])
            if "RAM" in column['name']:
                columnIDs['ram'] = int(column['id'])
        if not all (key in columnIDs for key in ('flash', 'ram')):
            return None
        for row in data['rows']:
            try:
                name = getColumnValue(row, columnIDs['name'])
                flashSize = getColumnValue(row, columnIDs['flash'])
                ramSize = getColumnValue(row, columnIDs['ram'])
                if not None in (name, flashSize, ramSize):
                    newDB[name] = { 'flash': flashSize, 'ram': ramSize }
            except:
                pass
        with open(MCU_DB_FILE, 'w') as dbJSONFile:
            json.dump(newDB, dbJSONFile)
        return newDB
    except:
        return None

# Load the local DB and return the JSON/dictionary object
def loadMCUdatabase():
    try:
        with open(MCU_DB_FILE) as datafile:
            return json.load(datafile)
    except:
        return None


'''
    MCU object class
'''
# This class represents a MCU.
# It contains all the infos and parameters required to build a project around
# the microcontroller
class MCU:

    def __init__(self):
        self.name = ''
        self.flash = 0
        self.ram = 0
        self.familyID = 0
        self.seriesID = 0
        self.cpuID = 0
        self.cpuName = ''
        self.iset = 'thumb'
        self.fpu = False

    # Static function to get the MCU family and series just from the name
    # Even a partial name would work, like 'STM32F3'
    @staticmethod
    def getSeriesFromName(name):
        name = name.upper()
        data = { }
        if len(name) < 7:
            return None
        if (name[:5] != 'STM32'):
            return None
        if (name[5:6] == 'F'):
            data['family'] = 0
        elif (name[5:6] == 'L'):
            data['family'] = 1
        else:
            return None
        try:
            data['series'] = int(name[6:7])
            return data
        except:
            return None

    @staticmethod
    def trimName(name):
        if len(name) > 11:
            return name[:11]
        else:
            return name


    # Parse an MCU name and extract the MCU parameters
    def loadFromName(self, mcuName):
        self.name = MCU.trimName(mcuName.upper())
        if len(self.name) < 11:
            return False
        series = MCU.getSeriesFromName(self.name)
        if series is None:
            return False
        self.familyID = series['family']
        self.seriesID = series['series']
        if self.seriesID == 0:
            self.cpuID = 0
            self.cpuName = 'cortex-m0'
        elif self.seriesID in (1, 2):
            self.cpuID = 3
            self.cpuName = 'cortex-m3'
        elif self.seriesID in (3, 4):
            self.cpuID = 4
            self.cpuName = 'cortex-m4'
            self.fpu = True
        elif self.seriesID == 7:
            self.cpuID = 7
            self.cpuName = 'cortex-m7'
            self.fpu = True
        else:
            return False

        flashID = self.name[10:11]
        if not flashID in TABLE_FLASH_SIZE:
            return False
        self.flash = TABLE_FLASH_SIZE[flashID]

        return True

    # This function loads just the flash and RAM memories size,
    # the function loadFromName() should be called first
    def loadFromDB(self, mcuDB, mcuName):
        self.name = MCU.trimName(mcuName.upper())
        if not self.name in mcuDB:
            return False
        try:
            mcuDBentry = mcuDB[self.name]
            self.flash = int(mcuDBentry['flash'])
            self.ram = int(mcuDBentry['ram'])
            return True
        except:
            return False

    def exportJSON(self, filename):
        export = {  'name': self.name,
                    'flash': self.flash,
                    'ram': self.ram }
        with open(filename, 'w') as JSONFile:
            json.dump(export, JSONFile)

    def loadFromJSON(self, filename):
        with open(filename) as JSONFile:
            data = json.load(JSONFile)
            self.loadFromName(data['name'])
            self.flash = data['flash']
            self.ram = data['ram']

    def __str__(self):
        return "\"" + self.name + "\": " + self.cpuName.upper() + "(" + str(self.cpuID) + "), FLASH=" + str(self.flash) + "kB, RAM=" + str(self.ram) + "kB, FPU=" + str(self.fpu) + ", Iset='" + self.iset + "'"


'''
    SUBPROGRAM: Project compilation script
'''
def parseMakeOutput(out):
    lines = out.splitlines()[-4:]
    sizeLine = None
    for i in range(len(lines)):
        line = lines[i]
        if 'bss' in line and 'data' in line:
            sizeLine = lines[i + 1]
    if sizeLine is None:
        return None
    tokens = sizeLine.split()
    result = {  'text': int(tokens[0]),
                'data': int(tokens[1]),
                'bss':  int(tokens[2]) }
    return result

def compileProject(projectDir):
    command = ['make', '-j' + str(getCPUcount() + 1)]
    makeProcess = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE, cwd=projectDir)
    out, err = makeProcess.communicate()
    if makeProcess.returncode != 0:
        return (False, err)
    else:
        sizeInfo = parseMakeOutput(out)
        flashUsage = sizeInfo['text'] + sizeInfo['data']
        ramUsage = sizeInfo['data'] + sizeInfo['bss']
        return (True, err, flashUsage, ramUsage)

def cleanProject(projectDir):
    FNULL = open(os.devnull, 'w')
    subprocess.Popen(['make', 'clean'], stdout=FNULL, stderr=subprocess.STDOUT, cwd=projectDir).wait()


'''
    SUBPROGRAM: Project flashing script
'''
def flashProject(projectDir):
    subprocess.Popen(['make', 'program'], cwd=projectDir).wait()

def flashProject_bootloader(projectDir):
    subprocess.Popen(['make', 'program-btl'], cwd=projectDir).wait()


'''
    SUBPROGRAM: HAL package acquisition script
'''
def acquireHALpackage(filename):
    print "Acquiring HAL package from '" + filename + "'"
    if os.path.isdir(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)
    zf = zipfile.ZipFile(filename, 'r')
    print "Extracting HAL package..."
    zf.extractall(TEMP_DIR)

    HAL_PACK_DIR = TEMP_DIR + "/" + os.listdir(TEMP_DIR)[0]

    packageXML = xml.etree.ElementTree.parse(HAL_PACK_DIR + '/package.xml').getroot()
    releaseString = packageXML[0].attrib['Release']
    releaseStringTokens = releaseString.split('.', 2)
    if releaseStringTokens[0] != 'FW':
        ERROR("Invalid HAL package")
    packageFamilyString = releaseStringTokens[1][:1]
    packageFamilyID = 0 if packageFamilyString == 'F' else 1
    packageSeriesID = int(releaseStringTokens[1][1:])
    packageVersionString = releaseStringTokens[2]
    packageVersionNum = int(packageVersionString.replace('.', ''))
    packageFamilySeriesString = "STM32" + ("F" if packageFamilyID == 0 else "L") + str(packageSeriesID)
    print "\n[Package info]\n" + packageFamilySeriesString + " series\nHAL version " + packageVersionString + "\n"

    searchedTemplate = getTemplateBasenameFor(packageFamilyID, packageSeriesID)
    if searchedTemplate is None:
        INFO("A local {} package does not already exist, will now be acquired".format(packageFamilySeriesString))
    else:
        existingVersion = int(getTemplateInfo(searchedTemplate)['versionNum'])
        if packageVersionNum <= existingVersion:
            INFO("There's already a package with same or lower version to the package provided")
            print "Nothing to do, cleaning up..."
            if os.path.isdir(TEMP_DIR):
                shutil.rmtree(TEMP_DIR)
            sys.exit(0)
        else:
            INFO("There's already a {} package but will be updated".format(packageFamilySeriesString))

    print "\nBuilding template from the package..."
    TEMPLATE_DIR = TEMP_DIR + "/template"
    if os.path.isdir(TEMPLATE_DIR):
        shutil.rmtree(TEMPLATE_DIR)
    os.makedirs(TEMPLATE_DIR + "/src")
    os.makedirs(TEMPLATE_DIR + "/libs")
    os.makedirs(TEMPLATE_DIR + "/system/hal")
    os.makedirs(TEMPLATE_DIR + "/system/cmsis")
    os.makedirs(TEMPLATE_DIR + "/ldscripts")

    print "[CMSIS]"
    CMSIS_DRIVER_DIR = HAL_PACK_DIR + "/Drivers/CMSIS"
    CMSIS_DEVICE_DIR = CMSIS_DRIVER_DIR + "/Device/ST/" + os.listdir(CMSIS_DRIVER_DIR + "/Device/ST")[0]
    copyDirContent(CMSIS_DRIVER_DIR + "/Include", TEMPLATE_DIR + "/system/cmsis")
    copyDirContent(CMSIS_DEVICE_DIR + "/Include", TEMPLATE_DIR + "/system/cmsis")
    for f in os.listdir(TEMPLATE_DIR + "/system/cmsis"):
        if "system_" in f:
            shutil.move(TEMPLATE_DIR + "/system/cmsis/" + f, TEMPLATE_DIR + "/system/")
    for f in os.listdir(CMSIS_DEVICE_DIR + "/Source/Templates"):
        if "system_" in f:
            shutil.copyfile(CMSIS_DEVICE_DIR + "/Source/Templates/" + f, TEMPLATE_DIR + "/system/" + f)
    copyDirContent(CMSIS_DEVICE_DIR + "/Source/Templates/gcc", TEMPLATE_DIR + "/system")
    if os.path.isdir(TEMPLATE_DIR + "/system/linker"):
        shutil.rmtree(TEMPLATE_DIR + "/system/linker")

    print "[STM32Cube HAL]"
    HAL_DRIVER_DIR = ""
    for d in os.listdir(HAL_PACK_DIR + "/Drivers"):
        if os.path.isdir(HAL_PACK_DIR + "/Drivers/" + d):
            if "HAL" in d:
                HAL_DRIVER_DIR = HAL_PACK_DIR + "/Drivers/" + d
    if HAL_DRIVER_DIR == "":
        ERROR("Couldn't find HAL driver subfolder")
    copyDirContent(HAL_DRIVER_DIR + "/Src", TEMPLATE_DIR + "/system/hal")
    copyDirContent(HAL_DRIVER_DIR + "/Inc", TEMPLATE_DIR + "/system/hal")
    for f in os.listdir(TEMPLATE_DIR + "/system/hal"):
        if "_conf_template" in f:
            newName = f.replace('_template', '')
            shutil.move(TEMPLATE_DIR + "/system/hal/" + f, TEMPLATE_DIR + "/src/" + newName)

    print "\nPacking the template..."
    templateBasename = "stm32" + packageFamilyString.lower() + str(packageSeriesID)
    if not os.path.isdir(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    zipDirContent(TEMPLATE_DIR + "/", TEMPLATES_DIR + "/" + templateBasename + ".zip")
    print "Writing JSON info..."
    templateInfo = {
        'familyID': packageFamilyID,
        'seriesID': packageSeriesID,
        'versionString': packageVersionString,
        'versionNum': packageVersionNum
    }
    with open(TEMPLATES_DIR + "/" + templateBasename + ".json", 'w') as outfile:
        json.dump(templateInfo, outfile)
    print "Cleaning up..."
    if os.path.isdir(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)

'''
    SUBPROGRAM: Project creation script
'''
def createProject(args):
    if not args.mcu:
        ERROR("No MCU model specified. Use something like 'stm32tool new <name> -m STM32F051K8'")

    mcu = MCU()

    if mcu.loadFromName(args.mcu) == False:
        ERROR("The specified MCU name is not valid")

    if args.ram:
        WARNING("The MCU RAM size has been manually specified, if it's wrong you're going to have problems")
        mcu.ram = int(args.ram)
    else:
        mcuDB = loadMCUdatabase()
        dbExists = False if mcuDB is None else True
        mcuFound = mcu.loadFromDB(mcuDB, args.mcu) if mcuDB is not None else False
        if (not dbExists) or (not mcuFound):
            if mcuDB is None: print "No local MCU database found, downloading now"
            elif not mcuFound: print "The MCU is not in the database. Maybe the DB is obsolete, updating now"
            mcuDB = updateMCUdatabase()
            if mcuDB is None:
                ERROR("Couldn't load or update the database, you must manually specify the MCU RAM size")
        if mcu.loadFromDB(mcuDB, args.mcu) == False:
            if dbExists: ERROR("The MCU isn't in the updated database too, check the MCU name or manually specify the RAM size")
            else: ERROR("The MCU does not exist in the ST database")


    print "Creating new project '" + args.project + "'\n"

    print "Searching a suitable template package..."
    templateBasename = getTemplateBasenameFor(mcu.familyID, mcu.seriesID)
    if templateBasename is None:
        print "Couldn't find a suitable local template package, trying to download..."
        url = getHALDownloadLink(mcu.familyID, mcu.seriesID)
        if url is None:
            ERROR(  "Couldn't find the URL for the required template package",
                    "You must manually download the HAL libraries and acquire the package")
        downloadedPackage = downloadFile(url, saveToDisk=True, location='.')
        if downloadedPackage is None:
            ERROR("Download failed or canceled by the user")
        acquireHALpackage(downloadedPackage)
        templateBasename = getTemplateBasenameFor(mcu.familyID, mcu.seriesID)
        print ""

    print "Initializing project directory..."
    PROJECT_DIR = "./" + args.project
    if os.path.isdir(PROJECT_DIR):
        ERROR(  "A folder with the specified project name already exists",
                "If you want to update the ST HAL, use the <upgrade> command")
    else:
        os.makedirs(PROJECT_DIR)

    print "[CMSIS, HAL and project structure]"
    zf = zipfile.ZipFile(TEMPLATES_DIR + "/" + templateBasename + ".zip", 'r')
    zf.extractall(PROJECT_DIR)

    print "[Startup file]"
    modelFile = getModelFileForMCU(PROJECT_DIR, mcu.name)
    if modelFile is None:
        shutil.rmtree(PROJECT_DIR)
        ERROR("Couldn't find the MCU model file, ensure the MCU name is correct")
    for f in os.listdir(PROJECT_DIR + "/system"):
        if "startup_" in f:
            if f != "startup_" + modelFile + ".s":
                os.remove(PROJECT_DIR + "/system/" + f)

    print "[CMSIS configuration]"
    for f in os.listdir(PROJECT_DIR + "/system/cmsis"):
        if "stm32" in f and len(f.split('.')[0]) >= 11:
            if f != modelFile + ".h":
                os.remove(PROJECT_DIR + "/system/cmsis/" + f)

    print "[Linker script]"
    with open(PROJECT_DIR + "/ldscripts/mem.ld", 'w') as f:
        f.write("MEMORY\n")
        f.write("{\n")
        f.write("  FLASH (rx) : ORIGIN = 0x08000000, LENGTH = " + str(mcu.flash) + "K\n")
        f.write("  RAM (xrw) : ORIGIN = 0x20000000, LENGTH = " + str(mcu.ram) + "K\n")
        f.write("}\n")

    print "[Makefile and common files]"
    copyDirContent(TEMPLATES_DIR + "/common", PROJECT_DIR)
    cmsisInclude = getCMSISinclude(PROJECT_DIR)
    replaceInFile(PROJECT_DIR + "/src/main.c", "!CMSIS_FAMILY_INCLUDE!", cmsisInclude)
    replaceInFile(PROJECT_DIR + "/system/newlib/sbrk.c", "!CMSIS_FAMILY_INCLUDE!", cmsisInclude)

    print "[config.mk]"
    mcuDefine = modelFile.upper().replace('X', 'x')
    fpuFlags = " -mfloat-abi=hard -mfpu=fpv4-sp-d16" if mcu.fpu == True else ""
    with open(PROJECT_DIR + "/config.mk", 'w') as f:
        f.write("# This file has been automatically generated by stm32tool\n")
        f.write("# Feel free to change some options if you like\n\n")
        f.write("CPU = -mcpu=" + mcu.cpuName + fpuFlags + "\n")
        f.write("ISET = -m" + mcu.iset + "\n")
        f.write("OPTIMIZE = -O2\n")
        f.write("CSTD = -std=c99\n")
        f.write("MCU = -D" + mcuDefine + "\n")
        f.write("STARTUP = system/startup_" + modelFile + ".s\n")
        f.write("BTLPORT = /dev/ttyUSB0\n")

    print "[MCU info file]"
    mcu.exportJSON(PROJECT_DIR + "/mcu.json")

    print "[Cleaning up unnecessary files]"
    for f in os.listdir(PROJECT_DIR + "/system/hal"):
        if "_template" in f:
            os.remove(PROJECT_DIR + "/system/hal/" + f)

    print "\nProject is ready, running a test compilation..."
    if compileProject(PROJECT_DIR)[0] == False:
        WARNING("Something went wrong with the compilation, you must manually check, sorry for that")
        WARNING("Please report the error to the developer so it can be fixed, thanks!")
    else:
        print "All went fine! Your new project is ready, it's time to code!"
    cleanProject(PROJECT_DIR)


'''
    ArgParse configuration
'''
parser = argparse.ArgumentParser(description='Simple CLI tool to deal with the creation, compilation, management and distribution of STM32 projects and software under Linux')

parser.add_argument('command', choices=['new', 'info', 'build', 'rebuild', 'flash', 'flash-btl', 'acquire', 'download'], help='The operation to perform')
parser.add_argument('project', help='The name of the project (folder) to operate within')
parser.add_argument('-m', '--mcu', help='The MCU model name when creating a project')
parser.add_argument('-r', '--ram', help='The MCU RAM amount in [kB] when creating a project', type=int)
args = parser.parse_args()

'''
    Initial checks
'''
if not os.path.isdir(TOOL_DIR):
    os.makedirs(TOOL_DIR)
if not os.path.isdir(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR)

'''
    Command execution
'''

# File/directory existance check
if not args.command in ('new', 'download', 'acquire'):
    if not os.path.isdir(args.project):
        ERROR("The project specified does not exist")
if args.command in ('acquire'):
    if not os.path.isfile(args.project):
        ERROR("The file specified does not exist")

# 'new' command
if args.command == 'new':
    createProject(args)

# 'info' command
if args.command == 'info':
    mcu = MCU()
    mcu.loadFromJSON(args.project + "/mcu.json")
    fcount = countFiles(args.project, ('c', 'h'), ('build'))
    print "Project info:"
    print CLIFormat.ROWNAME + "[MCU]      " + CLIFormat.ENDF + str(mcu)
    print CLIFormat.ROWNAME + "[#files]   " + CLIFormat.ENDF + "{} .c, {} .h, {} others ({} total)".format(fcount['c'], fcount['h'], fcount['other'], fcount['total'])
    print CLIFormat.ROWNAME + "[#lines]   " + CLIFormat.ENDF + str(countCodeLines(args.project, ('c', 'h')))

# 'build' and 'rebuild' commands
if 'build' in args.command or args.command == 'flash':
    if args.command == 'rebuild':
        INFO("Cleaning build files")
        cleanProject(args.project)
    INFO("Building project")
    result = compileProject(args.project)
    print result[1]
    if result[0] == False:
        ERROR("Errors during project compilation")
    print "Compilation successful, memory usage:"
    mcu = MCU()
    mcu.loadFromJSON(args.project + "/mcu.json")
    flashUsed = float(result[2]) / 1024
    flashUsage = flashUsed / float(mcu.flash) * 100
    ramUsed = float(result[3]) / 1024
    ramUsage = ramUsed / float(mcu.ram) * 100
    print CLIFormat.ROWNAME + "[FLASH]    " + CLIFormat.ENDF + "{:.1f}/{} kB\t({:.1f}%)".format(flashUsed, mcu.flash, flashUsage)
    print CLIFormat.ROWNAME + "[RAM]      " + CLIFormat.ENDF + "{:.1f}/{} kB\t({:.1f}%)".format(ramUsed, mcu.ram, ramUsage)


# 'flash' command
if args.command == 'flash':
    flashProject(args.project)

# 'flash-btl' command
if args.command == 'flash-btl':
    flashProject_bootloader(args.project)

# 'acquire' command
if args.command == 'acquire':
    acquireHALpackage(args.project)

# 'download' command
if args.command == 'download':
    series = MCU.getSeriesFromName(args.project)
    if series is None:
        ERROR("The specified MCU series is not valid, use something like 'STM32F4'")
    url = getHALDownloadLink(series['family'], series['series'])
    if url is None:
        ERROR(  "Couldn't find the URL for the required template package",
                "You must manually download the HAL libraries and acquire the package")
    downloadedPackage = downloadFile(url, saveToDisk=True, location='.')
    if downloadedPackage is None:
        ERROR("Download failed or canceled by the user")
    acquireHALpackage(downloadedPackage)
