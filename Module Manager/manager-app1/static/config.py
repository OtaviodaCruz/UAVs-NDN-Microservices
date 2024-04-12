# Global Variables ----------------------------------------------------------------------------------------------------------------

is_debug = True

# def data_graph_devives(graphDevices):
#     #define nodes
#     graphDevices.add_node("control_center1", mode = "off", network_role = "consumer")
#     graphDevices.add_node("uav1", mode = "off", network_role = "router")
#     graphDevices.add_node("uav2", mode = "off", network_role = "router")
#     graphDevices.add_node("soldier1", mode = "off", network_role = "consumer")
#     graphDevices.add_node("tank1", mode = "off", network_role = "router")
#     graphDevices.add_node("soldier2", mode = "off", network_role = "consumer")
#     graphDevices.add_node("uav3", mode = "off", network_role = "producer")
#     #graphDevices.add_node("N8", name = "uav4")

#     # define links
#     graphDevices.add_edge("N1", "N2", link_delay=6)
#     graphDevices.add_edge("N2", "N3", link_delay=3)
#     graphDevices.add_edge("N2", "N4", link_delay=3)
#     graphDevices.add_edge("N4", "N5", link_delay=3)
#     graphDevices.add_edge("N3", "N4", link_delay=3)
#     graphDevices.add_edge("N5", "N6", link_delay=2)
#     graphDevices.add_edge("N5", "N7", link_delay=3)

# -------uncomment--------

# def data_graph_devives(graphDevices):
#     #define nodes
#     graphDevices.add_node("uav1", mode = "off", network_role = "router")
#     graphDevices.add_node("uav2", mode = "off", network_role = "router")
#     graphDevices.add_node("tank1", mode = "off", network_role = "router")
#     graphDevices.add_node("soldier1", mode = "off", network_role = ["router","consumer"])
#     # define links
#     graphDevices.add_edge("uav1", "uav2", link_delay=3)
#     graphDevices.add_edge("uav1", "soldier1", link_delay=3)
#     graphDevices.add_edge("uav2", "soldier1", link_delay=3)
#     graphDevices.add_edge("soldier1", "tank1", link_delay=3)

# dynamic_graph_devives = {
#     "uav4": {"edge": ("N5", "N8"), "link_delay":3}
# }

# -------uncomment--------

def data_graph_devives(graphDevices):
    #define nodes
    #graphDevices.add_node("otaviopc-to-be-filled-by-o-e-m", mode = "off", network_role = "router")
    graphDevices.add_node("uav1", mode = "on", network_role = "router")
    graphDevices.add_node("uav2", mode = "on", network_role = "router")
    #graphDevices.add_node("client2", mode = "off", network_role = "router")
    #graphDevices.add_node("server1", mode = "off", network_role = "router")
    graphDevices.add_node("tank1", mode = "on", network_role = "router")
    
    # define links
    #graphDevices.add_edge("otaviopc-to-be-filled-by-o-e-m", "uav1", link_delay=3)

    graphDevices.add_edge("uav1", "uav2", link_delay=3)
    #graphDevices.add_edge("uav1", "client2", link_delay=3)
    #graphDevices.add_edge("uav2", "client2", link_delay=3)
    graphDevices.add_edge("uav2", "tank1", link_delay=3)
    #graphDevices.add_edge("tank1", "server1", link_delay=3)

dynamic_graph_devives = {
    "uav2": {"edge": ("uav2", "tank1"), "link_delay":3, "attrs": [("mode", "off"), ("network_role", "router")]}
    #None
}

max_attempt = 2

max_attempt_udp = 2

graph_counters_devices = {"uav": 2, "soldier": 2, "controller": 2, "tank": 2, "node": 8}
graph_counters = {"cs": 1, "br": 1, "nr": 1, "sr": 1, "sv": 1, "pd": 1, "la": 1, "fw": 1}

node_default_stats = {
    "cpu_stats": {
        "cpu_percent": 0.0,
        "cpu_total": 0,
        "last_update": 0.0,
    },
    "memory_stats": {
        "memory_percent": 0.0,
        "memory_total": 0,
        "memory_update": 0.0,
    }
}

specific_node_default_attrs = {
    "cs": {
        "type": "CS",
        #"size": 100000, #quantidade absoluta de conteudos que é possivel salvar (não é em Mb)
        "lastScaled": 0.0
    },
    "br": {
        "type": "BR",
        #"size": 250,
        "lastScaled": 0.0
    },
    "nr": {
        "type": "NR",
        "static_routes": {}, #a set fot each face. Producer indiretamente ligados
        "dynamic_routes": {}, #producer diretamente ligados
        "lastScaled": 0.0
    },
    "sr": {
        "type": "SR",
        "strategy": "multicast",
        "lastScaled": 0.0
    }
}

default_metrics = {
    "cs": {},
    "br": {},
    "nr": {},
    "sr": {},
    "pd": {},
    }


pod_default_attrs = {
    "cs": {
    "container_name": "microservice-content-store",
    "container_image": "otaviocruz/ndn_microservice-content_store:8.0",
    "template_labels": {"app": "microservice-content-store"},
    #"limits":{"cpu": "100m", "memory": "100M"} # 500m -> 0.5 (50%) of 1 core CPU. 300M -> 300 megabytes
    "requests": {"cpu": "175m", "memory": "300M"}
    },
    "nr": {
    "container_name": "microservice-name-router",
    "container_image": "otaviocruz/ndn_microservice-name_router:6.0",
    "template_labels": {"app": "microservice-name-router"},
    #"limits":{"cpu": "100m", "memory": "100M"} # 500m -> 0.5 (50%) of 1 core CPU. 300M -> 300 megabytes
    "requests": {"cpu": "150m", "memory": "100M"}
    },
    "br": {
    "container_name": "microservice-backward-router",
    "container_image": "otaviocruz/ndn_microservice-backward_router:3.0",
    "template_labels": {"app": "microservice-backward-router"},
    #"limits":{"cpu": "25m", "memory": "35M"} # 500m -> 0.5 (50%) of 1 core CPU. 300M -> 300 megabytes
    "requests": {"cpu": "175m", "memory": "100M"}
    },
    "sr": {
    "container_name": "microservice-strategy-forwarder",
    "container_image": "otaviocruz/ndn_microservice-strategy_forwarder:2.0",
    "template_labels": {"app": "microservice-strategy-forwarder"},
    #"limits":{"cpu": "100m", "memory": "20M"} # 500m -> 0.5 (50%) of 1 core CPU. 300M -> 300 megabytes
    "requests": {"cpu": "100m", "memory": "20M"}
    }
}

command_default = {
    "cs": "/CS",
    "nr": "/NR",
    "br": "/BR",
    "sr": "/SR"
}

arg_default = {
    "cs": {"size": "100000", "local_port": "6363", "command_port": "10000"},
    "nr": {"consumer_port": "6362", "producer_port": "6363","command_port": "10000"},
    "br": {"size":"250", "local_port": "6363", "command_port": "10000"},
    "sr": {"local_port": "6363", "command_port": "10000"}
}

def set_args(pod_type, pod_name, container_arg, add_arg = "") -> str:
    if pod_type == "cs":
        return " -n " + pod_name + " -s " + container_arg["size"] + " -p " + container_arg["local_port"] + " -C " + container_arg["command_port"] + add_arg
    elif pod_type == "br":
        return " -n " + pod_name + " -s " + container_arg["size"] + " -p " + container_arg["local_port"] + " -C " + container_arg["command_port"] + add_arg
    elif pod_type == "nr":
        return " -n " + pod_name + " -c " + container_arg["consumer_port"] + " -p " + container_arg["producer_port"] + " -C " + container_arg["command_port"] + add_arg
    elif pod_type == "sr":
        return " -n " + pod_name + " -p " + container_arg["local_port"] + " -C " + container_arg["command_port"] + add_arg
    else:
        return False
