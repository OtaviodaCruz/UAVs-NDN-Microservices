from decimal import *

import networkx as nx

from twisted.internet import reactor, defer
from twisted.internet.task import LoopingCall

import datetime
import traceback
from klein import Klein
import time

import static.server as appServer
import operations
import log
import UDP_communication 
import pod
import NR
import nodeK8s 
import static.config as managerConfig

from kubernetes import client, config, utils
from kubernetes.client.rest import ApiException

## Declare objects
app = Klein()

graphMicro = nx.DiGraph()
graphDevices = nx.DiGraph() # o ideial aqui seria utilizar Graph(), mas como conheço o cenário, esse servirá melhor
managerConfig.data_graph_devives(graphDevices)

modules_socket = UDP_communication.ModulesSocket(graphMicro, graphDevices)

log.init()

log.fileLogConfig("manager.log")

def configK8s():
    try:
        # load authenication from kube-config
        # I think that kube-conf is a file named config in $HOME/.kube. 
        # This file have information about: cluster, users, namespaces, authentication mechanisms
        config.load_incluster_config()
        return True
    except Exception as e:
        print("Error getting kubernetes client")
        return False


if not configK8s():
    exit()


# def processCreateMicroservice(typeMicro):
#     try:   
#         name = typeMicro + str(managerConfig.graph_counters[typeMicro])
#         managerConfig.graph_counters[typeMicro] += 1
#         if not (operations.createPodAndNode(name, typeMicro, graphMicro, modules_socket, namespace="ndn", is_scalable=False, nodeName=nodeName)):
#             return False 
#         return name
#     except Exception:  
#         log.printWithColor("Error when try create pod and node ")
#         return False


# -------------------------------------- Defaut microservices  --------------------------------------

#get resources and save
nodeK8s.getNodesResources(graphDevices)

def defaultMicros():
    #get nodes

    #deploy microservices
    try:
        for node in graphDevices.nodes:
            microservice_chain = operations.chooseChain(graphDevices, node)
            micro_names = []
            #create pods and nodes graph
            for typeMicro in microservice_chain:
                name = typeMicro + str(managerConfig.graph_counters[typeMicro])
                managerConfig.graph_counters[typeMicro] += 1
                if operations.createPodAndNode(name, typeMicro, graphMicro, modules_socket, namespace="ndn", is_scalable=False, nodeName=node):
                    micro_names.append(name)
                else:
                    return False
            graphDevices.nodes[node]["microservices_chain"] = micro_names
            time.sleep(5)
            #link microservices on node
            if not operations.createHostLink(modules_socket, graphMicro, micro_names):
                return False
        return True
    except Exception as e:  
        log.printWithColor("Error when try create or link default microservices " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
        return False

@defer.inlineCallbacks
def defaultLinkMicroNodes():
    try:
        for node in graphDevices.nodes: 
            successorsNodes = list(graphDevices.successors(node))
            for edge in successorsNodes:
                source = graphDevices.nodes[node]["microservices_chain"][-1]
                destination = graphDevices.nodes[edge]["microservices_chain"][0]
                
                for attempt in range(managerConfig.max_attempt_udp):    
                    resp = yield modules_socket.newFace(source, destination)
                    if resp and resp > 0:
                        graphMicro.add_edge(source, destination, face_id=resp)
                        NR.appendExistingRoutes(graphMicro, modules_socket, source, destination)
                        log.printWithColor("Link between " + source + " and " + destination + " created", type="INFO")
                        break
                    else:
                        log.printWithColor("When try create link between " + source + " and " + destination, type="CRITICAL")
                        log.writeDataLogFile("When try create link between " + micro_names[index] + " and " + destination, type="CRITICAL")
                        if attempt == managerConfig.max_attempt_udp:
                            log.printWithColor("Try to link " + source + " and " + destination + " again", type="WARNING")
                            return False
    except Exception as e:  
        log.printWithColor("Error when try create link between microservices nodes " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
        return False
#-------------------------------------------------Tests -------------------------------------------------

if __name__ == "__main__":
    reactor.suggestThreadPoolSize(10) 

    appServer.serverGraph = graphMicro
    appServer.serverSocket = modules_socket

    #nodeK8s.getAllK8sNodesInfo()

    if defaultMicros():
        defaultLinkMicroNodes()

    log.printWithColor("Init Manager", type="INFO")

    reactor.run()

    log.printWithColor("Manager killed", type="INFO")
    
    operations.deleteAllK8sResources(graphMicro)