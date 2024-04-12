from twisted.internet import defer
import networkx as nx
import datetime
import itertools

import log

"""
Adiciona os prefixos a NRs conectados ao microsserviço "name"
""" 
@defer.inlineCallbacks
def propagateNewRoutes(graphPods, modules_socket, name: str, prefixes: list):
    print("[", str(datetime.datetime.now()), "] [ propagateNewRoutes ] start")
    NR_names = [name2 for name2, attrs in graphPods.nodes(data=True) if attrs["type"] == "NR" and name2 != name]
    for name2 in NR_names:
        for path in nx.all_simple_paths(graphPods, name2, name):
            print("[", str(datetime.datetime.now()), "] [ propagateNewRoutes ]", name2, "-> add dynamic routes", prefixes, "to", path[1])
            face_id = graphPods.edges[name2, path[1]]["face_id"]
            resp = yield modules_socket.newRoute(name2, face_id, prefixes)
            if resp and resp == "success":
                routes = graphPods.nodes[name2]["dynamic_routes"].get(face_id, set())
                routes.update(prefixes)
                graphPods.nodes[name2]["dynamic_routes"][face_id] = routes
            else:
                print("[", str(datetime.datetime.now()), "] [ propagateNewRoutes ]", name2, "-> error while adding routes")
        print("[", str(datetime.datetime.now()), "] [ propagateNewRoutes ] end")

@defer.inlineCallbacks
def propagateDelRoutes(graphPods, modules_socket, name: str, prefixes: list):
    print("[", str(datetime.datetime.now()), "] [ propagateDelRoutes ] start")
    nodes_with_dynamic_routes = [(name, attr) for name, attr in graphPods.nodes(data="dynamic_routes") if attr]
    nodes_with_static_routes = [(name, attr) for name, attr in graphPods.nodes(data="static_routes") if attr]
    for name2, attr in nodes_with_dynamic_routes:
        for path in nx.all_simple_paths(graphPods, name2, name):
            accessible_static_prefixes = set()
            for name3, attr in nodes_with_static_routes:
                if nx.has_path(graphPods, path[1], name3):
                    accessible_static_prefixes.update(itertools.chain.from_iterable(attr.values()))
            prefixes_to_remove = list(set(prefixes) - accessible_static_prefixes)
            if prefixes_to_remove:
                print("[", str(datetime.datetime.now()), "] [ propagateDelRoutes ]", name2, "-> remove dynamic routes", prefixes_to_remove, "to", path[1])
                face_id2 = graphPods.edges[name2, path[1]]["face_id"]
                resp = yield modules_socket.delRoute(name2, face_id2, prefixes_to_remove)
                if resp and resp == "success":
                    graphPods.nodes[name2]["dynamic_routes"].pop(face_id2, None)
                else:
                    print("[", str(datetime.datetime.now()), "] [ propagateDelRoutes ]", name2, "-> error while removing routes")
            else:
                print("[", str(datetime.datetime.now()), "] [ propagateDelRoutes ]", name2, "-> routes are up to date")
    print("[", str(datetime.datetime.now()), "] [ propagateDelRoutes ] end")

# when a new node connect to the network
"""
Exemplo 1:
Considere a seguinte cadeia:
NR2 ---> BR1 ---> NR1

Considere que está sendo adicionada a face entre NR2 e BR1. Nesse caso appendExistingRoutes é utilizada para criar rotas de prefixos de NR1
Adiciona os prefixos atingiveis a "source"

Exemplo 2:
Considere a seguinte cadeia:
CS1 ---> BR1 ---> NR1

Considere que está sendo adicionada a face entre CS1 e BR1. Nesse caso appendExistingRoutes é utilizada para 
"""
@defer.inlineCallbacks
def appendExistingRoutes(graphPods, modules_socket, source, target):
    print("[", str(datetime.datetime.now()), "] [ appendExistingRoutes ] start")
    nodes_with_static_routes  = [(name, attr) for name, attr in graphPods.nodes(data="static_routes") if attr]
    accessible_static_prefixes  = set()
    for name, attr in nodes_with_static_routes:
        if nx.has_path(graphPods, target, name):
            accessible_static_prefixes.update(itertools.chain.from_iterable(attr.values())) 
    if accessible_static_prefixes:
        if graphPods.nodes[source]["type"] == "NR":
            print("[", str(datetime.datetime.now()), "] [ appendExistingRoutes ]", source, "-> add dynamic routes", accessible_static_prefixes, "to", target)
            face_id = graphPods.edges[source, target]["face_id"]
            resp = yield modules_socket.newRoute(source, face_id, accessible_static_prefixes)
            if resp and resp == "success":
                graphPods.nodes[source]["dynamic_routes"][face_id] = accessible_static_prefixes
            else:
                print("[", str(datetime.datetime.now()), "] [ appendExistingRoutes ]", source, "-> error while adding routes")
        else:
            print("[", str(datetime.datetime.now()), "] [ appendExistingRoutes ]", source, "-> skip, not a NR node")
        propagateNewRoutes(source, list(accessible_static_prefixes)) 
    print("[", str(datetime.datetime.now()), "] [ appendExistingRoutes ] end")