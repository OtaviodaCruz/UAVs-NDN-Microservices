import copy

import static.config as config
import log
from decimal import *

from kubernetes import utils

import traceback
import time


locked_nodes = set()

def addPodToGraph(graphObj, podObj, IPaddr:str, podType, podMonitorName, nodeK8sName, is_scalable=True, namespace="ndn",
                  stats = config.node_default_stats, node_attrs = config.specific_node_default_attrs, node_metrics=config.default_metrics):
    try:
        graphObj.add_node(podObj.metadata.name, monitorName = podMonitorName, editable=True, scalable=is_scalable, namespace = namespace, #cpuLimits=podObj.spec.containers[0].resources.limits['cpu'], memoryLimits=podObj.spec.containers[0].resources.limits['memory'],
                        addresses={"data": IPaddr, "command": IPaddr}, metrics = node_metrics[podType], nodeK8s = nodeK8sName, 
                        **copy.deepcopy(stats), **copy.deepcopy(node_attrs[podType])
                        )

        graphObj.nodes[podObj.metadata.name]["lastScaled"] = time.time()

        return True

    except Exception as e: 
        log.printWithColor("Add node graph error ", ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
        log.writeDataLogFile("Add node graph error", ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
        return False

# gets
def getCpuLimits(graphObj, podName:str):
    return graphObj[podName]["cpuLimits"]

def getMemoryLimits(graphObj, podName:str):
    return graphObj[podName]["memoryLimits"]

def getType(graphObj, podName:str):
    return graphObj[podName]['type']

def getCommandAddr(graphObj, podName:str):
    return graphObj[podName]["addresses"]["command"]
    
def getDataAddr(graphObj, podName:str):
    return graphObj[podName]["addresses"]["data"]

def getNamespace(graphObj, podName:str):
    return graphObj[podName]["namespace"]


def listNodes(graphObj):
    for i, j in graphObj.graph.nodes(data=True):
        print(i)

def setLimits(graphObj, podObj):        
    total_limits_cpu = Decimal(0)
    total_limits_memory = Decimal(0)

    for i in podObj.spec.containers:
        if i.resources:
            limit_cpu = utils.parse_quantity(i.resources.limits["cpu"])  
            total_limits_cpu += limit_cpu
    
            limit_memory = utils.parse_quantity(i.resources.limits["memory"])
            total_limits_memory =+ limit_memory
        else:
            log.printWithColor(podObj.metadata.name + " don't have field named resources", type="CRITICAL")
            log.writeDataLogFile(podObj.metadata.name, " don't have field named resources",  type="CRITICAL")
            return False  
    
    graphObj.nodes[podObj.metadata.name]["cpu_stats"]["cpu_total"] = total_limits_cpu
    graphObj.nodes[podObj.metadata.name]["memory_stats"]["memory_total"] = total_limits_memory

    return True

def setNodeK8s(graphObj, podName, nodeK8sName):        
    graphObj.nodes[podName]["nodeName"] = nodeK8sName
    return True

"""
def cretePodNode(pod_name, pod_type, is_scalable=True) -> bool:
    list_args = set_args(pod_type, pod_name, arg_default[pod_type])
    if list_args != False:
        pod_obj = create_pod_object(pod_type, pod_default_attrs[pod_type], pod_name, list_args)
        if pod_obj != False:
                if create_pod(pod_obj, namespace="ndn", field_manager="ndn_manager"):
                    if add_pod_node(pod_obj, pod_type, is_scalable, namespace="ndn"):
                        if add_node_limits(pod_obj):
                            print(bcolors.WARNING + "[INFO] Pod ", pod_name, " create success" + bcolors.ENDC)
                            logger.info("[" + str(datetime.datetime.now()) + "] " + "[INFO] Pod " + pod_name + " create success" + "\n")
                            if reportAddress(pod_name):
                                print(bcolors.WARNING + "[INFO] Manager report address success" + "\n")
                                return True
    return False          
"""    



""" def addMetric(graphObj, podName:str, metric:dict) -> bool:
    try:
        graphObj.node[podName]['metrics'].append(metric)
        return True
    except:
        print("Error addMetric")
        return False


def deleteMetric(graphObj, podName:str, metricName:str) -> bool:
    metricsList = graphObj.node[podName]['metrics']
    try:
        for idx, metric in enumerate(metricsList):
            if metric == metricName:
                graphObj.node[podName]['metrics'].pop(idx)
                return True
    except:
        print("Error deleteMetric")
        return False """


def changeMetricPerName(graphObj, podName:str, metricName:str, dataDict:dict) -> bool:
    try:
        if "status" in dataDict.keys():
            graphObj.nodes[podName]["metrics"][metricName]["status"] = dataDict["status"]

        if "timeStep" in dataDict.keys():
            graphObj.nodes[podName]["metrics"][metricName]["timeStep"] = dataDict["timeStep"]
        
        graphObj.nodes(data=True)

        return True
        
    except:
        log.printWithColor("When try chage metric " + metricName + " of " + podName, type="CRITICAL")
        log.writeDataLogFile("When try chage metric " + metricName + " of " + podName,  type="CRITICAL")
        return False

def getMetricNode(graphObj, podName) -> list:
    return graphObj.node[podName]["metrics"]



