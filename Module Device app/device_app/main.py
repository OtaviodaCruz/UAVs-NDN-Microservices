import udp
import log
import device

from twisted.internet import reactor, defer
import sys

# -------------------------- Global Initializations -----------------------------

number_of_argv = 3

log.init()

device_obj = device.Device()

print(device_obj.resources)

uav_name = sys.argv[1]
operation_time = float(sys.argv[2])
manager_ip = sys.argv[3]

if len(sys.argv) > number_of_argv:
    print("Init UAV", uav_name, "for", operation_time, "seg")
else:
    print("Incorrect Number of Arguments")
    exit()

modules_socket = udp.ModulesSocket()

## ------------------------ Functions -------------------------

@defer.inlineCallbacks
def requestIngress(modules_socket, device_obj, manager_ip):
    try:
        resp = yield modules_socket.sendNetworkIngress(device_obj, manager_ip)
        if resp == None:
            # try again
            resp = yield modules_socket.sendNetworkIngress(device_obj , manager_ip)
        if resp[0]:
            device_obj.name = resp[1]
            device_obj.state = "on"
            testModeChange()
            return True
        else: 
            log.printWithColor("Response equal to False to resqueting ingress") 
            return False
    except Exception as e:
        log.printWithColor("Error during resquet ingress" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()))
        return False

@defer.inlineCallbacks
def modeChange(modules_socket, device_obj, manager_ip):
    try:
        resp = yield modules_socket.sendDeviceMode(device_obj, manager_ip)
        if resp == None:
            # try again
            resp = yield modules_socket.sendDeviceMode(device_obj , manager_ip)
            return True
    except Exception as e:
        log.printWithColor("Error when try to send the device mode" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()))
        return False

## ------------------------ Tests -------------------------
def testRequestIngress():
   requestIngress(modules_socket, device_obj, manager_ip)
        

def testModeChange():
    device_obj.state = "off"
    modeChange(modules_socket, device_obj, manager_ip)

# ---------------------- Main ----------------------------

def main():

        try:        
            reactor.callLater(1, testRequestIngress)

            #device off
            reactor.callLater(60, testModeChange)

            reactor.run()
        except Exception as e:
            log.printWithColor("Error during main code" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()))
        

if __name__ == "__main__":
    main()