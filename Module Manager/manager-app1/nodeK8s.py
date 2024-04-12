from kubernetes import client, utils
from kubernetes.client.rest import ApiException

def getNodesResources(graphDevices):
    result = client.CoreV1Api().list_node()

    for node in result.items:
        nodeName = node.metadata.name
        if graphDevices.has_node(nodeName):
            graphDevices.nodes[nodeName]["resources"] = {
                "cpu": utils.parse_quantity(node.status.capacity['cpu']),
                "memory": utils.parse_quantity(node.status.capacity['memory'])
            }

def getNodeResources(graphDevices, nodeNameParam):
    result = client.CoreV1Api().list_node()
    for node in result.items:
        nodeName = node.metadata.name
        if nodeName == nodeNameParam:
            if graphDevices.has_node(nodeName):
                graphDevices.nodes[nodeName]["resources"] = {
                    "cpu": utils.parse_quantity(node.status.capacity['cpu']),
                    "memory": utils.parse_quantity(node.status.capacity['memory'])
                }

def getAllK8sNodesInfo(): 
    listK8sNodes = []
    try:
        k8s_api = client.CoreV1Api()
        response = k8s_api.list_node()

        if len(response.items) > 0:
            for node in response.items:
                listK8sNodes.append(node.metadata.name)
        
        return listK8sNodes
    
    except ApiException as e:
        print('Found exception in reading the logs')

def getNodeK8s(APIresult):
    try:
        return APIresult.spec.node_name
    except Exception as e:
        print(e)
        return False