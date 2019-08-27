# BBox plugin
#
# Author: Smanar
#
"""
<plugin key="BBox" name="BBox plugin" author="Smanar" version="1.0.0" wikilink="https://github.com/Smanar/Domoticz-BBox">
    <description>
        <br/><br/>
        <h2>Plugin pour le routeur de Bouygues telecom</h2><br/>
        Pour le moment sert juste a lister les peripheriques, WOL.
        <br/><br/>
        <h3>Remark</h3>
        <ul style="list-style-type:square">
            <li>Le mot de passe n'est utile que pour les actions demandant des droits d'acces, vous pouvez laisser le champs vide.</li>
        </ul>
        <h3>Configuration</h3>
        Gateway configuration
    </description>
    <params>
        <param field="Mode1" label="Delai en secondes" width="75px" required="true" default="300" />
        <param field="Mode2" label="Password (si besoin)" width="100px" required="false" default="" />
        <param field="Mode3" label="Debug" width="150px">
            <options>
                <option label="None" value="0"  default="true" />
                <option label="Debug info Only" value="2"/>
                <option label="Basic Debugging" value="62"/>
                <option label="Basic+Messages" value="126"/>
                <option label="Connections Only" value="16"/>
                <option label="Connections+Python" value="18"/>
                <option label="Connections+Queue" value="144"/>
                <option label="All" value="-1"/>
            </options>
        </param>
    </params>
</plugin>
"""

# https://api.bbox.fr/doc/#Getting%20started
# API complete : https://api.bbox.fr/doc/apirouter/index.html


# All imports
import Domoticz

import json, requests

URL = "mabbox.bytel.fr"

class BasePlugin:

    def __init__(self):
        self.httpConn = None
        self.url = None
        self.data = None
        self.listdevice = {}
        self.tempo = 0
        self.counter = 0

        self.password = None
        self.cookie = None
        return

    def onStart(self):
        Domoticz.Debug("onSart")

        if Parameters["Mode3"] != "0":
            Domoticz.Debugging(int(Parameters["Mode3"]))

        self.tempo = int(Parameters["Mode1"]) / 10

        #Retreive cookies
        if Parameters["Mode2"] != "":
            self.password = Parameters["Mode2"]
            self.cookie = GetCookie(self.password)

        #To force an update
        self.ForceUpdate(10)

        Domoticz.Status("BBox plugin running !")

    def onStop(self):
        Domoticz.Log("onStop - Plugin is stopping.")

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("Connect")
        if (Status == 0):
            Domoticz.Debug("connected successfully.")

            h = {
                'User-Agent':'Domoticz',\
                'Accept':'*/*' ,\
                'Host':URL,\
                'Connection':'keep-alive'\
                 }

            if self.cookie:
                h['Cookie'] = self.cookie

            sendData = {}
            if self.data:
                sendData['Verb'] = 'POST'
                sendData['Data'] = self.data
            else:
                sendData['Verb'] = 'GET'
            sendData['URL'] = self.url
            sendData['Headers'] = h

            self.url = None
            self.data = None

            Connection.Send(sendData)
        else:
            Domoticz.Log("Failed to connect ("+str(Status)+") with error: "+Description)

    def onMessage(self, Connection, Data):
        #Domoticz.Log("****************** "  + str(Data) )
        Domoticz.Debug("OnMessage")

        Status = int(Data["Status"])
        Response = ''

        try:
            if "Data" in Data:
                strData = Data["Data"].decode("utf-8", "ignore")
                try:
                    Response = json.loads(strData)
                except:
                    Response = str(strData)
        except:
            Domoticz.Error("On message error "  + str(Data) )

        if (Status == 200):
            #Ok bien recu data, deconnexion si besoin.
            if self.httpConn.Connected():
                self.httpConn.Disconnect()

            if len(Response) == 0:
                Domoticz.Status("Requete effectuée")
                return

            #Traitement
            if type(Response) is str:
                # Html code
                if 'Computer will begin to sleep' in Response:
                    Domoticz.Status("Command send succesfull at Switchoff")
                else:
                    Domoticz.Error("Unknow responde : " + str(Response))

            else:
                # Json code
                _json = Response[0]

                if 'hosts' in _json:
                    _json = _json['hosts']['list']

                    for i in _json:
                        macaddress = i['macaddress']
                        if macaddress not in self.listdevice:
                            self.listdevice[macaddress] = {}

                        self.listdevice[macaddress]['id'] = i['id']
                        self.listdevice[macaddress]['hostname'] = i['hostname']
                        self.listdevice[macaddress]['ipaddress'] = i['ipaddress']
                        self.listdevice[macaddress]['active'] = i['active']

                        link = i['link']
                        rssi = 12
                        if link.startswith('Wifi'):
                            _rssi = i['wireless']['rssi0']
                            _rssi = - int ( _rssi)
                            if _rssi < 60:
                                rssi = 11
                            elif _rssi > 75:
                                rssi = 4
                            else:
                                rssi = 8

                        self.listdevice[macaddress]['rssi'] = rssi

                    #for i in self.listdevice:
                    #    Domoticz.Log('Device: ' + self.listdevice[i]['hostname'] + ' active : ' + str(self.listdevice[i]['active']))

                    self.UpdateDevice()

                else:
                    Domoticz.Log('Not managed Json')

        elif (Status == 307):
            Domoticz.Error("Router returned a status: " + str(Status) + " Operation requires authentication")

        else:
            Domoticz.Error("Router returned a status: " + str(Status))

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

        if len(self.listdevice) == 0:
            Domoticz.Log("Plugin not ready")
            return

        if Command == "On":
            #Get device id
            mac = Devices[Unit].DeviceID
            #Domoticz.Log(str(self.listdevice[mac]))
            id = self.listdevice[mac]['id']
            #Get token
            token = GetToken(self.cookie)
            if not token:
                return
            #Make request
            url = '/api/v1/hosts/' + str(id) + '?btoken=' + token
            data = "action=wakeup"
            self.Request(url,data)

        if Command == "Off":
            #Get device id
            mac = Devices[Unit].DeviceID
            Domoticz.Log(str(self.listdevice[mac]))
            ip = self.listdevice[mac]['ipaddress']
            #Make request
            url = 'http://' + ip + ':8000/?action=System.Sleep'
            self.Request(url)

        #Recuperation de l'etat 30s apres, ca peut prendre du temps
        self.ForceUpdate(30)

    def onDisconnect(self, Connection):
        Domoticz.Debug("onDisconnect called for connection to: "+Connection.Address+":"+Connection.Port)
        self.httpConn = None

    def onHeartbeat(self):
        self.counter += 1
        if self.counter > self.tempo:
            self.counter = 0
            Domoticz.Log("MAJ BBox")
            self.Request('/api/v1/hosts')

        Domoticz.Debug("HeartBeat")

#---------------------------------------------------------------------------------------------------------

    def ForceUpdate(self,time):
        self.counter = int(self.tempo - int(time) / 10)

    def Request(self,url,data=None):
        if not self.httpConn and not self.url:
            _port = '443'
            _proto = 'HTTPS'
            _address = URL

            #if it's not a request to the box
            if url.startswith('http'):
                if not url.startswith('https'):
                    _port = '80'
                    _proto = 'HTTP'
                t = url.split('/')
                _address = t[2]
                url = '/' + '/'.join(t[3:])

                if ':' in _address:
                    t = _address.split(':')
                    _address = t[0]
                    _port = t[1]

            Domoticz.Debug("Making request " + _proto.lower() + "://" + _address + url)
            self.url = url
            self.data = data
            self.httpConn = Domoticz.Connection(Name="BBox", Transport="TCP/IP", Protocol=_proto, Address=_address, Port=_port)
            self.httpConn.Connect()
        else:
            Domoticz.Debug("Connection already active")


    def UpdateDevice(self):

        for i in self.listdevice:
            mac = i
            unit = GetDevice(mac)

            #Create device if not exist
            if not unit:
                unit = FreeUnit()
                Domoticz.Status("DeviceCreation : " + self.listdevice[i]['hostname'] )
                Domoticz.Device(Name=self.listdevice[i]['hostname'], Unit=unit, DeviceID=mac , Type=244, Subtype=73, Switchtype=0, Image=17, ).Create()

            active = Devices[unit].nValue

            if self.listdevice[i]['active'] != Devices[unit].nValue:
                kwarg = {}
                Domoticz.Log("Device Update : " + self.listdevice[i]['hostname'] )

                kwarg['SignalLevel'] = self.listdevice[i]['rssi']

                kwarg['nValue'] = self.listdevice[i]['active']
                if kwarg['nValue'] == 1:
                    kwarg['sValue'] = "On"
                else:
                    kwarg['sValue'] = "Off"

                Devices[unit].Update(**kwarg)



global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()


#-----------------------------------------------------------------

def GetDevice(mac):
    for x in Devices:
        if Devices[x].DeviceID == str(mac) :
            return x
    return False

def FreeUnit() :
    FreeUnit = ""
    for x in range(1,256):
        if x not in Devices :
            FreeUnit=x
            return FreeUnit
    if FreeUnit == "" :
        FreeUnit=len(Devices)+1
    return FreeUnit

def GetToken(cookie):
    if not cookie:
        Domoticz.Error("Cookie manquants")

    try:
        headers={'Accept':'*/*','host':URL,"Cookie":cookie}
        result = requests.get('https://' + URL + '/api/v1/device/token' , headers=headers, timeout = 5)
        _json = result.json()

        if 'exception' in _json:
            Domoticz.Error("Token Error : " + str(_json['exception']))
            if _json['exception']['code'] == '401':
                Domoticz.Error("Token Error : Not Authorized")
            return False

        _json = _json[0]['device']['token']
        Domoticz.Log("Token ok")
        return _json
    except:
        Domoticz.Error("Token non recupéré")
    return False

def GetCookie(password):
    try:
        data = {'password': password,'remember':'1'}
        headers={'Accept':'*/*','host':URL}
        result = requests.post('https://' + URL + '/api/v1/login' , headers=headers, data = data, timeout = 5)
        cookie = 'BBOX_ID=' + result.cookies['BBOX_ID']
        Domoticz.Status("Cookie recupéré, mode admin possible !")
        return cookie
    except:
        Domoticz.Error("Pas de cookie recupéré")
    return None
