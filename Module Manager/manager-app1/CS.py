from decimal import Decimal

CS_threshold = {"cpu": Decimal(3), "memory": Decimal(2684354560)} #quantidade de nucleos e memoria em bytes

max_packet_size = 10000 # considerei 8800 bytes mais um valor por precaução

def chooseCSLen(graphDevices, nodeName):
    """
    chooseCSLen is used to choose the len of microservice CS. 
    The CS size is calculated from the resources exceeding a CS_threshold considering a certain data packet size
    :param graphDevices: graph of networkx used to store device nodes
    :param nodeName: name of the node
    return len of CS
    """ 
    node_memory = graphDevices.nodes[nodeName]["resources"]["memory"]
    
    remain_memory = node_memory - CS_threshold["memory"] 

    return (remain_memory * 1000000) / max_packet_size