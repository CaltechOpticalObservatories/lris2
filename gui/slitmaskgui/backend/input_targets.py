'''
the file format is a starlist: https://www2.keck.hawaii.edu/observing/starlist.html

'''

import re
import json

# need to update the input targets to have a different header
# I want the header to match that of magma #,Target name, priority,magnitude,Ra,Dec,Center distance
#The program should be able to output an array that has this information and if the information is not provided
#then it should put N/A 
keywords = (
    "pmra",
    "pmdec",
    "dra",
    "ddec",
    "vmag",
    "rotmode",
    "rotdest",
    "wrap",
    "raoffset",
    "decoffset"
    )

'''will have to get priority from starlist as well as if the star is a must have'''

class TargetList:

    def __init__(self,file_path):

        self.file_path = file_path
        self.target_list = []
        self.objects = []
        self._parse_file()
        
    def _parse_file(self):
        with open(self.file_path) as file:
            untitled_count = 0
            for line in file:
                line = line.strip() #Just in case
                if not line.startswith("#") and line.split():
                    match = re.match(r"(?P<star>\S+)\s+(?P<Ra>\d{2} \d{2} \d{2}\.\d{2}) (?P<Dec>[\+|\-]\d{2} \d{2} \d{2}(?:\.\d+)?)\s+(?P<equinox>[^\s]+)\s",line)
                    if match:
                        name, ra, dec, equinox = match.group("star"), match.group("Ra"), match.group("Dec"), match.group("equinox")
                    else:
                        name, ra, dec, equinox = f"UntitledStar{untitled_count}", "Not Provided", "Not Provided", "Not Provided"
                        untitled_count += 1
                    
                    search = re.search(r"vmag=(?P<vmag>.+\.\S+)",line)
                    priority_search = re.search(r"priority=(?P<priority>\S+)",line)

                    vmag = search.group("vmag") if search != None else "N/A"
                    priority = priority_search.group("priority") if priority_search != None else "0"

                    obj = {
                        "name": name,
                        "ra": ra,
                        "dec": dec,
                        "equinox": equinox,
                        "vmag": vmag,
                        "priority": priority
                    }
                    self.objects.append(obj)

    def send_json(self):
        self.objects = json.dumps(self.objects)
        return self.objects
        
