import logging
import datetime
import os

import traceback

bcolors = {"HEADER": '\033[95m',
        "OKBLUE": '\033[94m',
        "OKCYAN": '\033[96m',
        "OKGREEN": '\033[92m',
        "WARNING": '\033[93m',
        "FAIL": '\033[91m',
        "ENDC": '\033[0m',
        "BOLD": '\033[1m',
        "UNDERLINE": '\033[4m'
        }

def printWithColor(data, ErrorReason="" , type="ERROR"):  
    if type == "WARNING":
        print(bcolors["WARNING"], "[" + type + "]", data, bcolors["ENDC"])

    elif type == "ERROR":
        print(bcolors["FAIL"], "[" + type + "]", data, ErrorReason, ". Try again", bcolors["ENDC"])

    elif type == "CRITICAL":
        print(bcolors["FAIL"], "[" + type + "]", data, ErrorReason, bcolors["ENDC"])

    elif type == "INFO":
        print(bcolors["OKCYAN"], "[" + str(datetime.datetime.now()) + "]", data, bcolors["ENDC"])
    
    else:
        print(data)

logger = logging.getLogger()

# ----------------------------------logging config----------------------------------
def fileLogConfig(fileName):
    try:
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(fileName)
        logger.addHandler(fh)
    except Exception as e:
        print(bcolors["FAIL"] , ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), bcolors["ENDC"])

def writeDataLogFile(data, ErrorReason="", type="ERROR"):  
    try:
        if type == "CRITICAL":
            logger.critical("[" + str(datetime.datetime.now()) + "] " +
                            "[" + type + "]" + " " + data + " " + ErrorReason + "\n"
                            )
        elif type == "ERROR":
            logger.error("[" + str(datetime.datetime.now()) + "] " +
                            "[" + type + "]" + " " + data + " " + ErrorReason + ". Try again" + "\n"
                        )
        elif type == "INFO":
            logger.info(data + "\n")

        else:
            logger.info(data + "\n")

    except Exception as e:
        print(bcolors["ERROR"] , ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), bcolors["ENDC"])

def init():
    try:
        path = "./"
        dir = os.listdir(path)
        file = "manager.log"
        if file in dir:
            os.remove(path + file)
        open("manager.log", "a")
    except Exception as e:
        print(bcolors["FAIL"] , ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), bcolors["ENDC"])
