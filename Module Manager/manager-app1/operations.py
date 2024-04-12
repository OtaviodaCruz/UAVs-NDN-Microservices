import microservice_graph
import pod
import CS
import microservice_graph
import static.config as managerConfig
import log
import nodeK8s
import NR

from twisted.internet import defer, threads

import time

import networkx as nx
import traceback

import datetime

"""
Para escolher a configuração de microsserviços, o Manager verifica as funções de rede do dispositivo e a quantidade de recursos disponiveis (cpu e memoria).
Começa verificando os recursos:
    Se o dispositivo tem uma quantidade de recursos menor que um certo threshold, então, apenas os microsserviços essenciais (BR e NR) são implantados, em CS.
Caso tenha quantidade de recursos suficientes, verifica a função de rede do dispositivo. 
Se a função de rede permite a implantação de CS, então, implanta  BR, CS e NR.

Funções de rede para os dispositivos: router, router_without_CS
"""
def chooseChain(graphDevices, nodeName):
    node_network_role = graphDevices.nodes[nodeName]["network_role"] 
    node_resources = graphDevices.nodes[nodeName]["resources"] 
    
    if node_resources["cpu"] < CS.CS_threshold["cpu"] or node_resources["memory"] < CS.CS_threshold["memory"]:
        return ("br", "nr")
    else:
        return ("br", "cs", "nr")

@defer.inlineCallbacks
def createHostLink(modules_socket, graphMicro, micro_names: list):
    try:   
        n = len(micro_names) - 1
        for index in list(range(0, n)):
            for attempt in range(managerConfig.max_attempt_udp): 
                resp = yield modules_socket.newFace(micro_names[index], micro_names[index+1])
                if resp and resp > 0:
                    graphMicro.add_edge(micro_names[index], micro_names[index + 1], face_id=resp)
                    NR.appendExistingRoutes(graphMicro, modules_socket, micro_names[index], micro_names[index + 1])
                    log.printWithColor("Link between " + micro_names[index] + " and " + micro_names[index + 1] + " created", type="INFO")
                else:
                    log.printWithColor("When try create link between " + micro_names[index] + " and " + micro_names[index + 1], type="CRITICAL")
                    log.writeDataLogFile("When try create link between " + micro_names[index] + " and " + micro_names[index + 1], type="CRITICAL")
                    if attempt == managerConfig.max_attempt_udp:
                        return False
        return True
    except Exception as e:  
        log.printWithColor("When try to create link between microservices in the same host "  + str(e.args[0]) + ". " + str(traceback.format_exc()), type = "CRITICAL")
        return False

@defer.inlineCallbacks
def createLinkMicroNodes(graphDevices, graphMicro, modules_socket, nodeName):
    try:
        #link between node and successors
        successorsNodes = list(graphDevices.successors(nodeName))
        for edge in successorsNodes:
            source = graphDevices.nodes[nodeName]["microservices_chain"][-1]
            destination = graphDevices.nodes[edge]["microservices_chain"][0]
            
            for attempt in range(managerConfig.max_attempt_udp): 
                resp = yield modules_socket.newFace(source, destination)
                if resp and resp > 0:
                    graphMicro.add_edge(source, destination, face_id=resp)
                    NR.appendExistingRoutes(graphMicro, modules_socket, source, destination)
                    log.printWithColor("Link between " + source + " and " + destination + "created", type="INFO")
                else:
                    log.printWithColor("When try create Link between " + source + " and " + destination, type="CRITICAL")
                    log.writeDataLogFile("When try create Link between " + source + " and " + destination, type="CRITICAL")
                    if attempt == managerConfig.max_attempt_udp:
                        return False
        #link between predecessors and node
        predecessorsNodes = list(graphDevices.predecessors(nodeName))
        for edge in predecessorsNodes:
            source = graphDevices.nodes[edge]["microservices_chain"][-1]
            destination = graphDevices.nodes[nodeName]["microservices_chain"][0]
            
            for attempt in range(managerConfig.max_attempt_udp):    
                resp = yield modules_socket.newFace(source, destination)
                if resp and resp > 0:
                    graphMicro.add_edge(source, destination, face_id=resp)
                    NR.appendExistingRoutes(graphMicro, modules_socket, source, destination)
                    log.printWithColor("Link between " + source + " and " + destination + "created", type="INFO")
                else:
                    log.printWithColor("When try create Link between " + source + " and " + destination, type="CRITICAL")
                    log.writeDataLogFile("When try create Link between " + source + " and " + destination, type="CRITICAL")
                    if attempt == managerConfig.max_attempt_udp:
                        return False
        return True
    except Exception as e:  
        log.printWithColor("Error when try create link between microservices nodes " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
        return False


def createPodAndNode(podName, podType, graphObj, socketObj, namespace="ndn", is_scalable=True, nodeName=None, curstom_args_pod = managerConfig.arg_default):
    podObj = pod.createPodObj(podType, podName, nodeName=nodeName, argsPod=curstom_args_pod)
    if podObj:
        if pod.createPod(podObj, namespace=namespace, field_manager="ndn_manager"):
            APIresult = pod.getPodInfo(podName, namespace=namespace)
            IPaddr = pod.getPodIp(APIresult)
            nodeK8sName = nodeK8s.getNodeK8s(APIresult)

            customResourceName = False

            if IPaddr and nodeK8sName:
                if microservice_graph.addPodToGraph(graphObj, podObj, IPaddr, podType, customResourceName, nodeK8sName, is_scalable=is_scalable, namespace=namespace):
                    if podType == "nr":
                        socketObj.reportAddress(podName)
                    if microservice_graph.setRequests(graphObj, podObj):
                        log.printWithColor("Pod " + podName + " created and added to graph", type="INFO")
                        return True
                else:
                    pod.deletePod(podName, namespace="ndn")
                    return False
    return False

def deleteAllK8sResources(graphObj): 
    for node in graphObj.nodes(data=True):
        pod.deletePod(node[0], namespace="ndn")
    print("Pods deleted")

def deletePodAndNode(graphObj, podName, namespace="ndn"):
    try:
        if pod.deletePod(podName, namespace=namespace):
            if graphObj.has_node(podName):
                graphObj.remove_node(podName)
                return True
        else:
            return False
    except nx.NetworkXError as e:
        log.printWithColor("When try remove node ", e, type="CRITICAL")
        return False

@defer.inlineCallbacks
def detachNode(name, graphObj, socketObj):
    log.printWithColor("[ detachNode ] start", type="Warning")
    #       OUT
    #      / |
    #  3(del)|
    #    /   |
    #  NODE  1(add)
    #    \   |
    #  2(del)|
    #      \ |
    #       IN
    in_node_names = list(graphObj.predecessors(name))
    out_node_names = list(graphObj.successors(name))
    for out_node_name in out_node_names:
        for in_name in in_node_names:
            resp = yield socketObj.newFace(in_name, out_node_name)
            if resp and resp > 0:
                log.printWithColor("[ detachNode ] link " + in_name + " to " + out_node_name, type="Warning")
                graphObj.add_edge(in_name, out_node_name, face_id=resp)
                resp = yield socketObj.delFace(in_name, name)
                if resp:
                    log.printWithColor("[ detachNode ] unlink " + in_name + " and " + name, type="Warning")
                    graphObj.remove_edge(in_name, name)
        resp = yield socketObj.delFace(name, out_node_name)
        if resp:
            log.printWithColor("[ detachNode ] unlink " + name + " and " + out_node_name, type="Warning")
            graphObj.remove_edge(name, out_node_name)
    log.printWithColor("[ detachNode ] end ", type="Warning")


@defer.inlineCallbacks
def attachNode(name, in_node_names: list, out_node_names: list, graphObj, socketObj, new_link=False):
    
    print("\n")
    log.printWithColor("[ attachNode ] start", type="INFO")
    print("\n")

    # Process:
    #       OUT
    #      / |
    #  1(add)|
    #    /   |
    #  NODE  3(del)
    #    \   |
    #  2(add)|
    #      \ |
    #       IN
    # step 1

    for out_node_name in out_node_names:
        resp = yield socketObj.newFace(name, out_node_name)
        if resp and resp > 0:
            log.printWithColor("[ attachNode ] " + name + " linked to " + out_node_name, type="INFO")
            graphObj.add_edge(name, out_node_name, face_id=resp)
    # step 2
    for in_node_name in in_node_names:
        resp = yield socketObj.newFace(in_node_name, name)
        if resp and resp > 0:
            log.printWithColor("[ attachNode ] " + in_node_name + " linked to " + name, type="INFO")
            graphObj.add_edge(in_node_name, name, face_id=resp)
            # step 3
            if not new_link:
                for out_node_name in out_node_names:
                    if graphObj.has_edge(in_node_name, out_node_name):
                        resp = yield socketObj.delFace(in_node_name, out_node_name)
                        if resp and resp > 0:
                            log.printWithColor("[ attachNode ] " + in_node_name + " no longer linked to " + out_node_name, type="INFO")
                            graphObj.remove_edge(in_node_name, out_node_name)
    log.printWithColor("[ attachNode ] end", type="INFO")


@defer.inlineCallbacks
def delFaceAndEdge(graphObj, socketObj, podSources:list, podDestinations:list) -> bool:  
    try:
        for podSource in podSources: 
            for podDestination in podDestinations:
                log.printWithColor("Deleting link between " + podSource + " and " + podDestination, type="INFO")
                resp1 = yield socketObj.delFace(podSource, podDestination)
                if resp1:   
                    #log.printWithColor("Deleting edge " + podSource + " and " + podDestination, type="INFO")
                    graphObj.remove_edge(podSource, podDestination)
                else:
                    return False
        return True
    except Exception as e:
        log.printWithColor("When try delete face(s) and Edge(s). Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
        return False    

