from twisted.internet import defer
import networkx as nx

import log
    
@defer.inlineCallbacks
def propagateNewRoutes(graphPods, modules_socket, name, prefixes):
    NR_names = [name2 for name2, attrs in graphPods.nodes(data=True) if attrs["type"] == "NR" and name2 != name]
    for name2 in NR_names:
        for path in nx.all_simple_paths(graphPods, name2, name):
            #print("[", str(datetime.datetime.now()), "]", path)
            face_id = graphPods.edges[name2, path[1]]["face_id"]
            resp = yield modules_socket.newRoute(name2, face_id, prefixes)
            if resp and resp == "success":
                propagated_routes = graphPods.nodes[name2].get("propagated_routes", {})
                routes = propagated_routes.get(face_id, set())
                routes |= prefixes
                propagated_routes[face_id] = routes
                graphPods.nodes[name2]["propagated_routes"] = propagated_routes
            else:
                log.printWithColor(name2, " -> error while propagate routes")


@defer.inlineCallbacks
def propagateDelRoutes(graphPods, modules_socket, name: str, prefixes: list):
    log.printWithColor("[ propagateDelRoutes ] Start", type="WARNING")
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
                log.printWithColor("[ propagateDelRoutes ]" + name2 + " -> remove dynamic routes" + prefixes_to_remove + " to " + path[1], type="WARNING")
                face_id2 = graphPods.edges[name2, path[1]]["face_id"]
                resp = yield modules_socket.delRoutes(name2, face_id2, prefixes_to_remove)
                if resp and resp == "success":
                    graphPods.nodes[name2]["dynamic_routes"].pop(face_id2, None)
                else:
                    log.printWithColor("[ propagateDelRoutes ] " + name2 + " -> error while removing routes")
            else:
                log.printWithColor("[ propagateDelRoutes ] " + name2 + " -> routes are up to date ", type="WARNING")
    log.printWithColor("[ propagateDelRoutes ] End", type="WARNING")


@defer.inlineCallbacks
def appendExistingRoutes(graphPods, modules_socket, source, target):
    face_id = graphPods.edges[source, target]["face_id"]
    NR_names = [name for name, attrs in graphPods.nodes(data=True) if attrs["type"] == "NR" and name != source]
    prefixes = set()
    for name in NR_names:
        if nx.has_path(graphPods, target, name):
            for value in graphPods.nodes[name].get("routes", {}).values():
                prefixes |= value
    if prefixes:
        resp = yield modules_socket.newRoute(source, face_id, prefixes)
        if resp and resp == "success":
            propagated_routes = {face_id: prefixes}
            graphPods.nodes[source]["propagated_routes"] = propagated_routes
            propagateNewRoutes(source, prefixes)