import socket
import time, datetime, pytz
from influxdb import InfluxDBClient
import sys
import bluetooth
import json

from config import config
from targets import targets


interval = config['info']['interval']
averaging = 7
discovery_file = 'discovery.json'


def db_write(client, data):
    try:
        client.write_points(data)
    except Exception as e:
        if str(e.code) == '404':
            print("       /!\ Unable to find the database")
        elif str(e.code) == '400':
            print("       /!\ Unable to save the value")
        else:
            print("       /!\ Error with DB, ", e)
            print("       /!\ Data, ", data)


if __name__ == '__main__':

    # Initialize the tools
    client = InfluxDBClient(
        config['influxdb']['server'], 
        config['influxdb']['port'], 
        config['influxdb']['user'],
        config['influxdb']['password'], 
        config['influxdb']['dbname']
    )
    a = 0

    # Initialize all presence to none
    presence = {}
    for t in targets:
        presence[t] = []

    discovery = {}
    try:
        with open(discovery_file) as discovery_f:
            discovery = json.load(discovery_f)
    except:
        pass

    # Main loop
    while 1:

        print("Iteration %s" % a)
        a += 1

        for mac in targets:
            if len(presence[mac]) >= averaging:
                presence[mac].pop(0)
            presence[mac].append(False)

        # Performing an ARP query to discover network clients (to be saved)
        devices = bluetooth.discover_devices(lookup_names=True)

        # Parsing the BT scan answer
        for mac, name in devices:

            # Parsing the ping answer
            if mac in targets:
                if targets[mac]['name'] == '':
                    targets[mac]['name'] = name
                presence[mac][-1] = True
                # print("     (o) %s - %s " % (mac, name))
            else:
                if mac not in discovery:
                    discovery[mac] = name
                    print("     (?) %s - %s " % (mac, name))

        # Generating a current unique timesamp
        ctime = datetime.datetime.fromtimestamp(time.time(), pytz.UTC)

        # Processing all updated targets
        for mac in targets:

            # Moving average on the presence (to avoid flickering)
            p = False
            for i in presence[mac]:
                p += i

            # Display the result
            print("         %s - %s" % ("(o)" if p else "   ", targets[mac]['label']))
            val = 1 if p else 0

            # Post the status to the DB
            data = [
                {
                    "measurement": config['info']['name'],
                    "tags": {
                        "name": targets[mac]['label'],
                        "group": targets[mac]['group']
                    },
                    "time": ctime,
                    "fields": {
                        "value": val,
                        "mac": mac,
                    },
                }
            ]
            db_write(client, data)


        with open(discovery_file, 'w') as f:
            f.seek(0)
            f.write(json.dumps(discovery))
            f.truncate()

        # Waiting before repeating
        time.sleep(config['info']['interval'])
