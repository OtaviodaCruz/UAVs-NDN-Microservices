from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor, defer

import simplejson as json
import time
import log
import socket
import traceback

#from pprint import pprint

def jsonSerial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, set):
        return list(obj)
    raise TypeError("Type %s not serializable" % type(obj))

class ModulesSocket(DatagramProtocol): 
    def __init__(self):
        self.routes = {"report": self.handleReport, "request": self.handleRequest, "reply": self.handleReply}
        self.request_routes = {}
        self.reply_results = {"add_face": "face_id", "del_face": "status", "edit_config": "changes", "add_route": "status", "del_route": "status", "network_ingress": "result", "device_mode": "result"}

        self.request_counter = 1
        self.pending_requests = {}

        ## Server listen 
        self.initListen()

    def datagramReceived(self, data, addr):
        try:
            print(data)
            j = json.loads(data.decode())
            self.routes.get(j.get("type", None), self.unknown)(j, addr)
                    
        except ValueError:  #add: includes simplejson.decoder.JSONDecodeError
            log.printWithColor("Decoding JSON has failed:" + data.decode())

    def unknown(self, j: dict, addr):
        log.printWithColor(json.dumps(j))

    def handleReport(self, j: dict, addr):
        if all(field in j for field in ["name", "action"]):
            self.report_routes.get(j.get("action", None), self.unknown)(j, addr)

    def handleRequest(self, j: dict, addr):
        if all(field in j for field in ["name", "action"]):
            self.request_routes.get(j.get("action", None), self.unknown)(j, addr)

    def handleReply(self, j: dict, addr):
        log.printWithColor("[ handleReply ]" + str(json.dumps(j)), type="WARNING")
        deferred = self.pending_requests.get(j.get("id", 0), None)
        if deferred:
            deferred.callback(j.get(self.reply_results.get(j.get("action", "unknown"), "unknown"), None))
        else:
            log.printWithColor(self.pending_requests, type="WARNING")

    def sendDatagram(self, data: dict, ip, port):
        try:
            # print("[", str(datetime.datetime.now()), "]", "send", data, "to", ip, port)
            # deferred to fire when the corresponding reply is received
            d = defer.Deferred()
            d.addTimeout(5, reactor, onTimeoutCancel=self.onTimeout)
            d.addBoth(self.removeRequest, self.request_counter)
            self.pending_requests[self.request_counter] = d
            self.request_counter += 1

            dataBytes = json.dumps(data, default=jsonSerial).encode()
            
            self.transport.write(dataBytes, (ip, port))
            return d
        except Exception as e:
            log.printWithColor("Unknown error when try send Datagram" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()))
            return False

    def onTimeout(self, result, timeout):
        log.printWithColor("Got {0!r} but actually timed out after {1} seconds".format(result, timeout), type="CRITICAL")
        return None

    def removeRequest(self, value, key):
        #print("[", str(datetime.datetime.now()), "]", value, key)
        self.pending_requests.pop(key, None)
        return value

    def sendNetworkIngress(self, device_obj , addr: str):
        """ {
            "type": "request",
            "id": ,
            "action": "network_ingress"
            "network_role": 
            "resources": 
            {
                "cpu":
                "memory":
            }
            "position_in_formation":
        } """

        data = {
            "type": "request",
            "id": self.request_counter,
            "action": "network_ingress",
            "network_role": device_obj.network_role,
            "resources": device_obj.resources,
            "position_in_formation": device_obj.position_in_formation,
            "device_type": device_obj.device_type
        } 
        
        return self.sendDatagram(data, addr, 9999)

    def sendDeviceMode(self, device_obj , addr: str):
        """ {
            "type": "report",
            "id": ,
            "action": "device_mode",
            "name": ,
            "mode": 
        } """

        data = {
            "type": "report",
            "id": self.request_counter,
            "action": "device_mode",
            "name": device_obj.name,
            "mode": device_obj.state
        } 
        
        return self.sendDatagram(data, addr, 9999)


    def initListen(self):
        reactor.listenUDP(10000, self, maxPacketSize=1 << 16)