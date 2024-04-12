import json
#from pprint import pprint

class Device():
    def __init__(self):
        with open('config_file.json') as json_data:
            d = json.load(json_data)
            json_data.close()
            #pprint(d)

        self.position_in_formation = d["position_in_formation"]
        self.resources = d["resources"]
        self.device_type = d["device_type"]
        self.network_role = d["network_role"]
        self.name = "temporaryName"
        self.state = "off"
