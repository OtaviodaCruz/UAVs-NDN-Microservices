import log
from kubernetes.client.rest import ApiException
from kubernetes import client, utils
import time
import static.config as managerConfig

import traceback

from decimal import *

max_attempt = 2

## -------Metrics---------
metricsReceive = {"receiveCount": 0, "receiveBytes":0, "attemptCount": 0}

metricsSend = {"sendCount": 0, "sendBytes":0, "attemptCount": 0}

def receivePerformance(data:dict):
    for metric in metricsReceive:
        if metric in data:
            metricsReceive[metric] = metricsReceive[metric] + data[metric]

def getReceivePerformance():
    return metricsReceive

def plusReceiveCount(plustVal=1):
    metricsReceive["receiveCount"] = metricsReceive["receiveCount"] + plustVal

def resetCountReceive():
    for metrics in metricsReceive:
        metricsReceive[metrics] = 0

def sendPerformance(data:dict):
    for metric in metricsSend:
        if metric in data:
            metricsSend[metric] = metricsSend[metric] + data[metric]

def getSendPerformance():
    return metricsSend

def plusSendCount(plustVal=1):
    metricsSend["sendCount"] = metricsSend["sendCount"] + plustVal

def resetCountSend():
    for metrics in metricsSend:
        metricsSend[metrics] = 0

def stringToCSV():
    stringData = ""
    recevePerf = getReceivePerformance()
    stringData = stringData + str(recevePerf["receiveCount"]) + ";"
    stringData = stringData + str(recevePerf["receiveBytes"]) + ";"
    stringData = stringData + str(recevePerf["attemptCount"]) + ";"

    sendPerf = getSendPerformance()
    stringData = stringData + str(sendPerf["sendCount"]) + ";"
    stringData = stringData + str(sendPerf["sendBytes"]) + ";"
    stringData = stringData + str(sendPerf["attemptCount"]) + ";"

    resetCountSend()
    resetCountReceive()


    return stringData

def createPodObj(podType, podName, dictParamsPod=managerConfig.pod_default_attrs, nodeName=None, 
                    commdPod = managerConfig.command_default, argsPod = managerConfig.arg_default):    
    try:
        # Configureate Pod template container
        container = client.V1Container(
            name=dictParamsPod[podType]["container_name"],
            image=dictParamsPod[podType]["container_image"],
            ports=[client.V1ContainerPort(container_port=8000, name="metrics", protocol="TCP")],
            resources = client.V1ResourceRequirements(
                requests={"cpu":dictParamsPod[podType]["requests"]["cpu"], 
                          "memory":dictParamsPod[podType]["requests"]["memory"]},
                #limits={"cpu":dictParamsPod[podType]["limits"]["cpu"], 
                #        "memory":dictParamsPod[podType]["limits"]["memory"]},
            ),
            command=["/bin/bash","-c"], 
            args=[commdPod[podType] + managerConfig.set_args(podType, podName, argsPod[podType])],  
            #env=[]
        )

        # Create the specification of deployment
        spec = client.V1PodSpec(containers=[container], node_name=nodeName)

        # Instantiate the pod object
        pod_obj = client.V1Pod(
            api_version="v1",
            kind="Pod",
            metadata = client.V1ObjectMeta(name=podName, labels={"app": podName}), 
            spec=spec,
        )

        return pod_obj
        
    except Exception as e:
        log.printWithColor("Unknown error when try create pod object Pod", ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
        log.writeDataLogFile("Unknown error when try create pod object Pod",  ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
        return False


def podIsRunning(podName, namespace) -> bool:   
    failed = False
    start = time.time()
    while (time.time() - start < 120):       
        
        sendPerformance({"sendCount": 1, "sendBytes":0, "attemptCount": 0})

        api_response = client.CoreV1Api().read_namespaced_pod(name=podName, namespace=namespace)           
        
        receivePerformance({"receiveCount": 1, "receiveBytes":0, "attemptCount": 0})

        if api_response.status.phase == 'Running':                
            return True           
        if api_response == "Failed":
            failed = True
        time.sleep(1)

    if failed:
        log.printWithColor("Timeout, Pod " + podName + "isn't runnig. Failed at least once")
        log.writeDataLogFile("Timeout, Pod isn't runnig. Failed at least once")
    else:
        log.printWithColor("Timeout, Pod " + podName + "isn't runnig. Failed at least once", type="CRITICAL")
        log.writeDataLogFile("Timeout, Pod isn't runnig. Failed at least once", type="CRITICAL")
    return False

def createPod(podObj, namespace="ndn", field_manager="ndn_manager") -> bool:
    for attempt in range(max_attempt + 1):    
        try:
            #pod_obj = createPodObj(podType, podName)
            if podObj:

                sendPerformance({"sendCount": 1, "sendBytes":0, "attemptCount": 0})

                # Create pod
                resp = client.CoreV1Api().create_namespaced_pod(
                    body=podObj, 
                    namespace=namespace, 
                    field_manager=field_manager,
                )

                receivePerformance({"receiveCount": 1, "receiveBytes":0, "attemptCount": 0})

                if podIsRunning(podObj.metadata.name, namespace="ndn"):
                    return True
                
                return False
            else:
                return False
            
        except ApiException as e:
            if attempt < max_attempt:
                log.printWithColor("Create Pod" + ", code (" + str(e.status) + "):", str(e.reason))
                log.writeDataLogFile("Create Pod" + ", code (" + str(e.status) + "):", str(e.reason))
                
                sendPerformance({"sendCount": 0, "sendBytes":0, "attemptCount": 1})

            else: 
                log.printWithColor("Create Pod" + ", code (" + str(e.status) + "):", str(e.reason), type="CRITICAL")
                log.writeDataLogFile("Create Pod" + ", code (" + str(e.status) + "):", str(e.reason), type="CRITICAL" )
                return False
        
def deletePod(podName, namespace="ndn") -> bool:
    for attempt in range(max_attempt + 1):    
        try:
            sendPerformance({"sendCount": 1, "sendBytes":0, "attemptCount": 0})

            # Delete Pod
            resp = client.CoreV1Api().delete_namespaced_pod(
                name=podName,
                namespace=namespace,
            )

            receivePerformance({"receiveCount": 1, "receiveBytes":0, "attemptCount": 0})

            log.printWithColor("Pod " + podName + " destroyed", type="WARNING")

            return True

        except ApiException as e:
            if attempt < max_attempt:
                log.printWithColor("Delete Pod" + ", code (" + str(e.status) + "):", str(e.reason))
                log.writeDataLogFile("Delete Pod" + ", code (" + str(e.status) + "):" + " ", str(e.reason))

                sendPerformance({"sendCount": 0, "sendBytes":0, "attemptCount": 1})

            else:
                log.printWithColor("Delete Pod" + ", code (" + str(e.status) + "):", str(e.reason), type="CRITICAL")
                log.writeDataLogFile("Delete Pod" + ", code (" + str(e.status) + "):" + " ", str(e.reason), type="CRITICAL")
                return False
            
def getPodInfo(podName, namespace="ndn") -> str:
    try:
        for attempt in range(max_attempt + 1): 
            sendPerformance({"sendCount": 1, "sendBytes":0, "attemptCount": 0})

            ret = client.CoreV1Api().read_namespaced_pod(name=podName, namespace=namespace)

            receivePerformance({"receiveCount": 1, "receiveBytes":0, "attemptCount": 0})

            return ret
    
    except ApiException as e:
        if attempt < max_attempt:
            log.printWithColor("Get info Pod" + ", code (" + str(e.status) + "):" + " ", str(e.reason))
            log.writeDataLogFile("Get info Pod" + ", code (" + str(e.status) + "):" + " ", str(e.reason))

            sendPerformance({"sendCount": 0, "sendBytes":0, "attemptCount": 1})

        else:
            log.printWithColor("Get info Pod" + ", code (" + str(e.status) + "):", str(e.reason), type="CRITICAL")
            log.writeDataLogFile("Get info Pod" + ", code (" + str(e.status) + "):" + " ", str(e.reason), type="CRITICAL")
            return False
        

def getPodIp(APIresult):
    try:
        return APIresult.status.pod_ip
    except Exception as e:
        print(e)
        return False
##------------------Manager Resources##------------------
        
""" def getCurrentResourcesPod() -> list:
    resource = client.CustomObjectsApi().list_namespaced_custom_object(group="metrics.k8s.io",version="v1beta1", namespace="default", plural="pods")
    #ret = v1.list_pod_for_all_namespaces(watch=False)
    #ret.items.spec.containers.resources.limits['cpu']
    len_pods = len(resource["items"])
    len_containers = len(resource["items"]["containers"])
    CPU_total = 0
    memory_total = 0

    listResources = list()

    for i in len_pods:
        for j in len_containers:
            container_name = resource["items"][i]["containers"][j]["name"]
            container_CPU = resource["items"][i]["containers"][j]["usage"]["cpu"]
            v = resource["items"][i]["containers"][j]["usage"]["memory"]

            CPU_total += container_CPU
            memory_total += memory_total
        listResources.append({"cpu": CPU_total, "memory": memory_total}) #falta um nome

    return listResources """

""" def getPodResource(podName, namespace="ndn"):
    for attempt in range(max_attempt + 1):    
        try:
            resource = client.CustomObjectsApi().get_namespaced_custom_object(group="metrics.k8s.io", version="v1beta1", namespace=namespace, plural="pods", name=podName)
            #len_containers = range(len(resource["containers"]))
            CPU_total = Decimal(0)
            memory_total = Decimal(0)

            for i in resource["containers"]:
                container_CPU = Decimal(utils.parse_quantity(i["usage"]["cpu"]))
                CPU_total += container_CPU

                container_memory = Decimal(utils.parse_quantity(i["usage"]["memory"]))
                memory_total += container_memory
            
            return {"cpu": CPU_total,
                    "memory": memory_total}
        
        except ApiException as e:
            if attempt < max_attempt:
                log.printWithColor(" Get resources" + " (" + e.status + ")", e.reason)
                # waiting befor retry
                time.sleep(5)
            else: 
                log.printWithColor("API get resources" + " (" + e.status + ")" + e.reason, type="CRITICAL")
                log.writeDataLogFile("API get resources" + " ("+ str(e.status) + ")", e.reason, data="CRITICAL")
                log.writeDataLogFile("It's possible that the Pod not start yet.", type="INFO")
                return False
        except ValueError as e:
            if attempt < max_attempt:
                log.printWithColor("During convertion" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()))
            else: 
                log.printWithColor("During convertion" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
                log.writeDataLogFile("During convertion", type="CRITICAL")
                return False            
        except TypeError as e:
            if attempt < max_attempt:
                log.printWithColor("During math operation" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()))
            else: 
                log.printWithColor("During math operation" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
                log.writeDataLogFile("During math operation", type="CRITICAL")
                return False
        except Exception as e:
            if attempt < max_attempt:
                log.printWithColor("Unknown error when try get pod resource" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()))
            else: 
                log.printWithColor("Unknown error when try get pod resource" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
                log.writeDataLogFile("Unknown error when try get pod resource", type="CRITICAL")
                return False  """



def createCustomResource(bodyParam, groupParam="monitoring.coreos.com", versionParam="v1", namespaceParam="ndn", pluralParam="podmonitors"):
    for attempt in range(max_attempt + 1):  
        try:
            
            sendPerformance({"sendCount": 1, "sendBytes":0, "attemptCount": 0})
            
            client.CustomObjectsApi().create_namespaced_custom_object(
                group=groupParam, 
                version=versionParam, 
                namespace=namespaceParam, 
                plural=pluralParam, 
                body=bodyParam,
                )
            
            receivePerformance({"receiveCount": 1, "receiveBytes":0, "attemptCount": 0})

            return True
        except ApiException as e:
            if attempt < max_attempt:
                log.printWithColor("Create Custom Resource" + ", code (" + str(e.status) + "):", str(e.reason))
                log.writeDataLogFile("Create Custom Resource" + ", code (" + str(e.status) + "):", str(e.reason))

                sendPerformance({"sendCount": 0, "sendBytes":0, "attemptCount": 1})

            else: 
                log.printWithColor("Create Custom Resource" + ", code (" + str(e.status) + "):", str(e.reason), type="CRITICAL")
                log.writeDataLogFile("Create Custom Resource" + ", code (" + str(e.status) + "):", str(e.reason), type="CRITICAL" )
                return False
        

def deleteCustomResource(nameCustomResource, groupParam="monitoring.coreos.com", versionParam="v1", namespaceParam="default", pluralParam="podmonitors"):
    for attempt in range(max_attempt + 1):  
        try:

            sendPerformance({"sendCount": 1, "sendBytes":0, "attemptCount": 0})

            client.CustomObjectsApi().delete_namespaced_custom_object(
                group=groupParam,
                version=versionParam,
                name=nameCustomResource,
                namespace=namespaceParam,
                plural=pluralParam,
                body=client.V1DeleteOptions(),
            )

            receivePerformance({"receiveCount": 1, "receiveBytes":0, "attemptCount": 0})

            return True
        except ApiException as e:
            if attempt < max_attempt:
                log.printWithColor("When try delete Custom Resource" + ", code (" + str(e.status) + "):", str(e.reason))
                log.writeDataLogFile("When try delete Custom Resource" + ", code (" + str(e.status) + "):", str(e.reason))

                sendPerformance({"sendCount": 0, "sendBytes":0, "attemptCount": 1})

            else: 
                log.printWithColor("When try delete Custom Resource" + ", code (" + str(e.status) + "):", str(e.reason), type="CRITICAL")
                log.writeDataLogFile("When try delete Custom Resource" + ", code (" + str(e.status) + "):", str(e.reason), type="CRITICAL" )
                return False