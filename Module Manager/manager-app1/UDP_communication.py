from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor, defer

import simplejson as json

import time
import datetime

import NR
import CS
import log
import static.server as appServer
import static.config as managerConfig
import operations
import nodeK8s

import socket
import traceback
import networkx as nx

class ModulesSocket(DatagramProtocol): 
    def __init__(self, graphMicroservices, graphDevices):
        self.routes = {"report": self.handleReport, "request": self.handleRequest, "reply": self.handleReply}
        self.report_routes = {"producer_disconnection": self.handleProducerDisconnectionReport, "device_mode": self.handleDeviceModeReport}
        self.request_routes = {"route_registration": self.handlePrefixRegistration, "network_ingress": self.handleNetworkIngress}
        self.reply_results = {"add_face": "face_id", "del_face": "status", "edit_config": "changes", "add_route": "status", "del_route": "status", "add_keys": "status", "del_keys": "status"}
        
        self.graphMicroservices = graphMicroservices
        self.graphDevices = graphDevices
        
        self.request_counter = 1
        self.pending_requests = {}

        ## -------Metrics---------

        self.metricsReceive = {"receiveCount": 0, "receiveBytes":0}
        self.metricsSend = {"sendCount": 0, "sendBytes":0}

        ## Server listen 
        self.initListen()

    def receivePerformance(self, data:dict):
        for metric in self.metricsReceive:
            if metric in data:
                self.metricsReceive[metric] = self.metricsReceive[metric] + data[metric]

    def getReceivePerformance(self):
        return self.metricsReceive

    def resetCountReceive(self):
        for metrics in self.metricsReceive:
            self.metricsReceive[metrics] = 0

    def sendPerformance(self, data:dict):
        for metric in self.metricsSend:
            if metric in data:
                self.metricsSend[metric] = self.metricsSend[metric] + data[metric]

    def getSendPerformance(self):
        return self.metricsSend

    def resetCountSend(self):
        for metrics in self.metricsSend:
            self.metricsSend[metrics] = 0

    def stringToCSV(self):
        stringData = ""
        recevePerf = self.getReceivePerformance()
        stringData = stringData + str(recevePerf["receiveCount"]) + ";"
        stringData = stringData + str(recevePerf["receiveBytes"]) + ";"
        
        sendPerf = self.getSendPerformance()
        stringData = stringData + str(sendPerf["sendCount"]) + ";"
        stringData = stringData + str(sendPerf["sendBytes"]) + ";"

        self.resetCountReceive()
        self.resetCountSend()

        return stringData

    def datagramReceived(self, data, addr):
        if managerConfig.is_debug:
            print("Received: ", data)
        try:
            j = json.loads(data.decode())
            self.routes.get(j.get("type", None), self.unknown)(j, addr)
            
            self.receivePerformance({"receiveCount": 1, "receiveBytes":len(data)})
        
        except ValueError:  #add: includes simplejson.decoder.JSONDecodeError
            log.printWithColor("Decoding JSON has failed:" + data.decode())

    def unknown(self, j: dict, addr):
        log.printWithColor("Unknown name function" + json.dumps(j))

    def handleReport(self, j: dict, addr):
        if all(field in j for field in ["name", "action"]):
            self.report_routes.get(j.get("action", None), self.unknown)(j, addr)

    def face_error(self, j: dict, addr):
        if all(field in j for field in ["face_id"]) and self.graphMicroservices.has_node(j["name"]):
            print(j["name"], "droped package")

    def handleProducerDisconnectionReport(self, j: dict, addr):
        log.printWithColor("[ handleProducerDisconnectionReport ]" + json.dumps(j), type="WARNING")
        if all(field in j for field in ["face_id"]) and self.graphMicroservices.has_node(j["name"]):
            prefixes = list(self.graphMicroservices.nodes[j["name"]]["static_routes"].pop(j["face_id"], set()))
            if prefixes:
                NR.propagateDelRoutes(self.graphMicroservices, self, j["name"], prefixes)

    def handleRequest(self, j: dict, addr):
        #if all(field in j for field in ["name", "action"]):
        if all(field in j for field in ["action"]):
            self.request_routes.get(j.get("action", None), self.unknown)(j, addr)

    def handlePrefixRegistration(self, j: dict, addr):
        log.printWithColor("[ handlePrefixRegistration ]" + json.dumps(j), type="WARNING")
        if all(field in j for field in ["face_id", "prefix"]) and self.graphMicroservices.has_node(j.get("name", None)):
            print("[", str(datetime.datetime.now()), "] [ handlePrefixRegistration ] new route", j["prefix"], "via", j["name"])
            
            data = {"action": "reply", "id": j.get("id", 0), "result": True}
            self.sendDatagram(data, addr[0], addr[1])
            
            routes = self.graphMicroservices.nodes[j["name"]]["static_routes"]
            face_routes = routes.get(j["face_id"], set())
            face_routes.add(j["prefix"])
            routes[j["face_id"]] = face_routes

            print("STATIC ROUTE ADD ", j["prefix"], "? ", self.graphMicroservices.nodes[j["name"]]["static_routes"])

            #self.graphMicroservices.nodes[j["name"]]["routes"] = routes
            NR.propagateNewRoutes(self.graphMicroservices, self, j["name"], [j["prefix"]])

    def handleReply(self, j: dict, addr):
        if managerConfig.is_debug:
            log.printWithColor("[ handleReply ]" + " [" + str(datetime.datetime.now()) + "] " + str(json.dumps(j)), type="INFO")
        deferred = self.pending_requests.get(j.get("id", 0), None)
        if deferred:
            deferred.callback(j.get(self.reply_results.get(j.get("action", "unknown"), "unknown"), None))
        else:
            log.printWithColor(self.pending_requests, type="WARNING")

    def editConfig(self, source, data: dict):
        source_addrs = self.graphMicroservices.nodes[source]["addresses"]
        json_data = {"action": "edit_config", "id": self.request_counter}
        json_data.update(data)

        log.printWithColor("Sending Manager address to " + source, type="WARNING")

        return self.sendDatagram(json_data, source_addrs["command"], 10000)

    def newFace(self, source, target, port=6363):
        try:
            source_addrs = self.graphMicroservices.nodes[source]["addresses"]
            target_addrs = self.graphMicroservices.nodes[target]["addresses"]
            json_data = {"action": "add_face", "id": self.request_counter, "layer": "tcp", "address": target_addrs["data"], "port": 6362 if self.graphMicroservices.nodes[target]["type"] == "NR" else 6363}

            log.printWithColor("Sending command new face to " + source, type="WARNING")

            return self.sendDatagram(json_data, source_addrs["command"], 10000)
        except Exception as e:
                log.printWithColor("Unknown error when try execute newFace()" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()))
                return False

    def delFace(self, source, target):
        source_addrs = self.graphMicroservices.nodes[source]["addresses"]
        face_id = self.graphMicroservices.edges[source, target]["face_id"]
        json_data = {"action": "del_face", "id": self.request_counter, "face_id": face_id}

        log.printWithColor("Sending command delete face to " + source, type="WARNING")
        
        return self.sendDatagram(json_data, source_addrs["command"], 10000)

    def newRoute(self, source, face_id, prefixes: (list, set)):
        source_addrs = self.graphMicroservices.nodes[source]["addresses"]
        json_data = {"action": "add_route", "id": self.request_counter, "face_id": face_id, "prefixes": prefixes}

        log.printWithColor("Sending command new route to " + source, type="WARNING")
        
        return self.sendDatagram(json_data, source_addrs["command"], 10000)

    def delRoute(self, source, face_id, prefix: str): 
        source_addrs = self.graphMicroservices.nodes[source]["addresses"]
        json_data = {"action": "del_route", "id": self.request_counter, "face_id": face_id, "prefixes": prefix}
        
        log.printWithColor("Sending command del route to " + source, type="WARNING")
        log.printWithColor(json_data, type="WARNING") 

        return self.sendDatagram(json_data, source_addrs["command"], 10000)

    def list(self, source):
        source_addrs = self.graphMicroservices.nodes[source]["addresses"]
        json_data = {"action": "list", "id": self.request_counter}
        
        log.printWithColor("Sending command list to " + source, type="WARNING")

        return self.sendDatagram(json_data, source_addrs["command"], 10000)

    def sendDatagram(self, data: dict, ip, port, onTimeout = True):
        try:
            # print("[", str(datetime.datetime.now()), "]", "send", data, "to", ip, port)
            # deferred to fire when the corresponding reply is received
            d = defer.Deferred()
            if onTimeout:
                d.addTimeout(20, reactor, onTimeoutCancel=self.onTimeout)
            d.addBoth(self.removeRequest, self.request_counter)
            self.pending_requests[self.request_counter] = d
            self.request_counter += 1

            dataBytes = json.dumps(data, default=appServer.jsonSerial).encode()

            self.sendPerformance({"sendCount": 1, "sendBytes":len(dataBytes)})
            
            self.transport.write(dataBytes, (ip, port))
            return d
        except Exception as e:
            log.printWithColor("Unknown error when try send Datagram" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()))
            return False

    def onTimeout(self, result, timeout):
        print("[" + str(datetime.datetime.now()) + "] " + "onTimeout")
        log.printWithColor("Got {0!r} but actually timed out after {1} seconds".format(result, timeout), type="CRITICAL")
        return None
    
    def removeRequest(self, value, key):
        #print("[", str(datetime.datetime.now()), "]", value, key)
        self.pending_requests.pop(key, None)
        return value

    @defer.inlineCallbacks
    def reportAddress(self, podName, portAddr=int(9999)) -> bool: 
        max_attempt = 2

        for attempt in range(max_attempt + 1):   
            try:
                self.graphMicroservices.nodes[podName]["addresses"]
                d = {}

                hostname = socket.gethostname()
                IPAddr = socket.gethostbyname(hostname)

                d["manager_address"] = IPAddr
                d["manager_port"] = portAddr
                resp = yield self.editConfig(podName, d)

                if resp != None:
                    log.printWithColor("Manager IP sended to " + podName, type="WARNING")
                    return True
                if attempt > max_attempt:
                    log.printWithColor("When try get IP pod " + podName , type="CRITICAL")
                    log.writeDataLogFile("When try get IP pod " + podName, type="CRITICAL")    
                    return False

            except Exception as e:               
                log.printWithColor("When try get IP pod " + podName  + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
                log.writeDataLogFile("When try get IP pod " + podName  + ". Error: " + str(e), type="CRITICAL")    
                return False
                
    def initListen(self):
        reactor.listenUDP(9999, self, maxPacketSize=1 << 16)

    def handleNetworkIngress(self, j, adds):
        """
        handleNetworkIngress received a request of an device to ingress on the NDN network. 
        :param j: message received as a dictionary
        :param adds: ip address and port of sender
        """ 
        #generate a name
        name = j["device_type"] + str(managerConfig.graph_counters_devices[j["device_type"]])
        managerConfig.graph_counters_devices[j["device_type"]] += 1
        #add node
        self.graphDevices.add_node(name)
        
        #add edge
        self.graphDevices.add_edge(
            managerConfig.dynamic_graph_devives[name]["edge"][0], 
            managerConfig.dynamic_graph_devives[name]["edge"][1],
            link_delay=managerConfig.dynamic_graph_devives[name]["link_delay"])
        
        #add attributes
        for tupleAttrs in managerConfig.dynamic_graph_devives[name]["attrs"]:
            self.graphDevices.nodes[name][tupleAttrs[0]] = tupleAttrs[1]

        nodeK8s.getNodeResources(self.graphDevices, name)

        #response
        #example: {"type": "reply", "action": "network_ingress", "id": 1, "result": (True, name)}
        data = {
            "type": "reply",
            "action": "network_ingress",
            "id": j["id"],
            "result": (True, name)
        }
        self.sendDatagram(data, adds[0], adds[1], onTimeout = False)

    def handleDeviceModeReport(self, j, adds):
        """
        handleDeviceModeReport received a report about device mode. 
        If device mode is on, so microservices are deployed and linked
        If device mode is off, so microservices are destroyed
        :param j: message received as a dictionary
        :param adds: ip address and port of sender
        """ 
        if j["mode"] == "on" and self.graphDevices.nodes[j["name"]]["mode"] == "off":
            #deploy microservices
            micro_types = operations.chooseChain(self.graphDevices, j["name"])
            micro_names = []
            for micro_type in micro_types:
                micro_name = micro_type + str(managerConfig.graph_counters[micro_type])
                if micro_type == "cs":
                    CS_len = CS.chooseCSLen(self.graphDevices, j["name"])
                    CS_args = arg_default["cs"]
                    CS_args["size"] = str(CS_len)
                    if not operations.createPodAndNode(micro_name, micro_type, self.graphMicroservices, self, 
                                            is_scalable=False, nodeName=j["name"], curstom_args_pod = CS_args): 
                        return False
                    micro_names.append(micro_name)
                else:
                    if not operations.createPodAndNode(micro_name, micro_type, self.graphMicroservices, self, 
                                            is_scalable=False, nodeName=j["name"]): 
                        return False
                    micro_names.append(micro_name)
            
            self.graphDevices.nodes[j["name"]]["microservices_chain"] = micro_names

            #link deployed microservices (on the same host)
            if not operations.createHostLink(self, self.graphMicroservices, micro_names):
                return False
            #connect nodes: link microservices of differents nodes 
            if not operations.createLinkMicroNodes(self.graphDevices, self.graphMicroservices, self, j["name"]):
                return False

        if j["mode"] == "off" and self.graphDevices.nodes[j["name"]]["mode"] == "on":
            #delete microservices
            for microservice in self.graphDevices.nodes[j["name"]]["microservices_chain"]:
                operations.deletePodAndNode(self.graphMicroservices, microservice)
        
        self.graphDevices.nodes[j["name"]]["mode"] = j["mode"]
        #response
        #example: {"type": "reply", "action": "device_mode", "id": 1, "result": True}
        data = {
            "type": "reply",
            "action": "device_mode",
            "id": j["id"],
            "result": True
        }
        self.sendDatagram(data, adds[0], adds[1], onTimeout = False)