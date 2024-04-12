import copy
import datetime
from klein import Klein

import simplejson as json

from twisted.web.static import File
from twisted.web.server import Site, Request
from twisted.internet import reactor, defer, threads, endpoints

import networkx as nx

import static.config as config
import operations
import log
import microservice_graph
import pod
import NR

import traceback


def jsonSerial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, set):
        return list(obj)
    raise TypeError("Type %s not serializable" % type(obj))


app = Klein()
endpoints.serverFromString(reactor, "tcp:8080").listen(Site(app.resource()))  # eq to app.run(...)

serverGraph = None
serverSocket = None

# API static files -----------------------------------------------------------------------------------------------------
@app.route("/", branch=True)
def indexFile(request):
    return File("./http")

@app.route("/<name>", branch=True)
def staticFile(request: Request, name):
    return File("./http/" + name)

# API graph ------------------------------------------------------------------------------------------------------------
@app.route("/api/graph")
def sendGraph(request: Request):
    request.setHeader(b"Content-Type", b"application/json")
    
###############temporary solution###############
# take off key function. It's not serializable (return raise jsonSerial())
    b = copy.deepcopy(nx.node_link_data(serverGraph))

    for node in b["nodes"]:
        for k, v in node["metrics"].items():
            v.pop('function')
            node["metrics"][k] = v
###############temporary solution###############
    print
    return json.dumps(b, default=jsonSerial)

# API nodes ------------------------------------------------------------------------------------------------------------
@app.route("/api/nodes", methods=["POST"])
def createNode(request: Request):
    j = json.loads(request.content.read().decode())
    if all(field in j for field in ["type"]) and j["type"] in config.graph_counters:
        name = j["type"] + str(config.graph_counters[j["type"]])
        config.graph_counters[j["type"]] += 1
        if operations.createPodAndNode(name, j["type"], serverGraph, serverSocket, namespace="ndn"):
            return name
        else:
            request.setResponseCode(500)
            return "Error when try create node"
    else:
        request.setResponseCode(400)
        return "Bad Request"

@app.route("/api/nodes", methods=["GET"])
def sendNodesList(request: Request):
    request.setHeader(b"Content-Type", b"application/json")
    return json.dumps(list(serverGraph.nodes), default=jsonSerial)


@app.route("/api/nodes/<name>", methods=["GET"])
def sendNodeInfo(request: Request, name):
    if serverGraph.has_node(name):
        request.setHeader(b"Content-Type", b"application/json")
        strInfo = str(serverGraph.nodes[name])
        return json.dumps(strInfo, default=jsonSerial)
    else:
        request.setResponseCode(404)
        return

@app.route("/api/nodes/<name>", methods=["DELETE"])
@defer.inlineCallbacks
def removeNode(request: Request, name):
    if serverGraph.has_node(name):
        try:
            attrs = serverGraph.nodes[name]
            if attrs["editable"] and name not in graph.locked_nodes:
                graph.locked_nodes.add(name)
                log.printWithColor("[ removeNode ] unscale " + name, type="WARNING")  
                    
                # while attrs.get("scaled", False):
                #     yield scaleDown(name, attrs)
                operations.detachNode(name, serverGraph, serverSocket)
                resp = yield threads.deferToThread(pod.deletePod, name, namespace="ndn")
                if resp:
                    log.printWithColor("[ removeNode ] " + name + " removed", type="WARNING")
                    serverGraph.remove_node(name)
                graph.locked_nodes.remove(name)
            else:
                request.setResponseCode(503)
                return name + " is not editable or locked"
        except Exception as e:
            log.printWithColor("When try remove node. Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
        return "1"
    else:
        request.setResponseCode(404)
        return "0"

@app.route("/api/nodes/<name>", methods=["PATCH"])
@defer.inlineCallbacks
def nodeReport(request: Request, name):
    j = json.loads(request.content.read().decode())
    if serverGraph.has_node(name):
        d = {}
        if j.get("manager_address", None):
            d["manager_address"] = j["manager_address"]
        if j.get("manager_port", None):
            d["manager_port"] = int(j["manager_port"])
        if j.get("report_each", None):
            d["report_each"] = int(j["report_each"])
        if j.get("strategy", None):
            d["strategy"] = j["strategy"]
        resp = yield serverSocket.editConfig(name, d)
        if resp:
            if d["report_each"] > 0:

                dataDict = {"status": "on", "timeStep": d["report_each"]}
                #serverGraph.nodes[name]["metrics"]["lastTime"] = datetime.now()
                #graph.changeMetricPerName(serverGraph, name, "hit_count", dataDict)

                dataDict = {"status": "on", "timeStep": d["report_each"]}
                #serverGraph.nodes[name]["metrics"]["lastTime"] = datetime.now()
                #graph.changeMetricPerName(serverGraph, name, "miss_count", dataDict)

            request.setHeader(b"Content-Type", b"application/json")
            return json.dumps(resp, default=jsonSerial)
        else:
            request.setResponseCode(204)
            return
    else:
        request.setResponseCode(404)
        return
    
# API links ------------------------------------------------------------------------------------------------------------
@app.route("/api/links", methods=["POST"])
@defer.inlineCallbacks
def createLink(request: Request):
    j = json.loads(request.content.read().decode())
    if (all(field in j for field in ["source", "target"]) and serverGraph.has_node(j["source"]) and serverGraph.has_node(j["target"])
            and not serverGraph.has_edge(j["source"], j["target"])):
        resp = yield serverSocket.newFace(j["source"], j["target"])#, j.get("producer", False) if graph.nodes[j["target"]]["type"] == "NR" else False)
        if resp and resp > 0:
            serverGraph.add_edge(j["source"], j["target"], face_id=resp)
            NR.appendExistingRoutes(serverGraph, serverSocket, j["source"], j["target"])
            log.printWithColor("Link between " + j["source"] + " and " + j["target"] + "created", type="INFO")
            return "1"
        else:
            log.printWithColor("When try create Link between " + j["source"] + " and " + j["target"], type="CRITICAL")
            log.writeDataLogFile("When try create Link between " + j["source"] + " and " + j["target"], type="CRITICAL")
            return "0"
    else:
        log.printWithColor("When try create Link between " + j["source"] + " and " + j["target"] + ". One node don't exist.", type="CRITICAL")
        log.writeDataLogFile("When try create Link between " + j["source"] + " and " + j["target"] + ". One node don't exist.", type="CRITICAL")
        return "0"

@app.route("/api/links", methods=["GET"])
def sendLinks(request: Request):
    request.responseHeaders.addRawHeader(b"content-type", b"application/json")
    return json.dumps(list(serverGraph.edges), default=jsonSerial)

@app.route("/api/links/<source>/<target>", methods=["GET"])
def getLinkInfo(request: Request, source, target):
    if serverGraph.has_edge(source, target):
        request.setHeader(b"Content-Type", b"application/json")
        return json.dumps(serverGraph.edges[source, target], default=jsonSerial)
    else:
        request.setResponseCode(404)
        return

@app.route("/api/links/<source>/<target>", methods=["DELETE"])
@defer.inlineCallbacks
def removeLink(request: Request, source, target):
    if serverGraph.has_edge(source, target):
        resp = yield serverSocket.delFace(source, target)
        if resp and resp == 1:
            serverGraph.remove_edge(source, target)
            return "1"
        else:
            return "0"
    else:
        return "0" 
