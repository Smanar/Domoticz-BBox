# BBox plugin
#
# Author: Smanar
#
"""
<plugin key="BBox" name="BBox plugin" author="Smanar" version="1.0.3" wikilink="https://github.com/Smanar/Domoticz-BBox">
    <description>
        <br/><br/>
        <h2>Plugin pour le routeur de Bouygues telecom</h2><br/>
        Pour le moment sert juste a lister les peripheriques, WOL, afficher la qualite du Wifi.
        <br/><br/>
        <h3>Remarque</h3>
        <ul style="list-style-type:square">
            <li>Le mot de passe n'est utile que pour les actions demandant des droits d'acces, vous pouvez laisser le champs vide.</li>
        </ul>
        <h3>Configuration</h3>
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

import json
import requests

requests.packages.urllib3.disable_warnings()
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += 'HIGH:!DH:!aNULL'
try:
    requests.packages.urllib3.contrib.pyopenssl.DEFAULT_SSL_CIPHER_LIST += 'HIGH:!DH:!aNULL'
except AttributeError:
    # no pyopenssl support used / needed / available
    pass

URL = "mabbox.bytel.fr"
NO_DOMOTICZ_LIB = True
ADSL_QUALITY = False

class BasePlugin:

    def __init__(self):
        self.httpConn = None
        self.url = None
        self.data = None
        self.listdevice = {}
        self.tempo = 0
        self.counter = 0
        self.UpdateSucced = False

        self.down = 0
        self.up = 0

        self.password = None
        self.cookie = None
        return

    def onStart(self):
        Domoticz.Debug("onSart")

        if Parameters["Mode3"] != "0":
            Domoticz.Debugging(int(Parameters["Mode3"]))

        self.tempo = int(Parameters["Mode1"]) / 10

        #Retreive cookies for authentification
        self.Login()

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

        self.ManageAnswer(Data)

    def ManageAnswer(self,Data):

        self.UpdateSucced = True

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

                elif 'wan' in _json:
                    _json = _json['wan']['xdsl']
                    self.up = _json['up']['power'] - _json['up']['noise']
                    self.down = _json['down']['power'] - _json['down']['noise']

                else:
                    Domoticz.Log('Not managed Json')

        elif (Status == 307) or (Status == 401):
            Domoticz.Error("Router returned a status: " + str(Status) + " Operation requires authentication")
            self.Login()

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
                if self.password:
                    self.cookie = GetCookie(self.password)
                else:
                    Domoticz.Error("And no password set.")

                return
            #Make request
            url = '/api/v1/hosts/' + str(id) + '?btoken=' + token
            data = "action=wakeup"
            self.Request(url,data)

        if Command == "Off":
            #Get device id
            mac = Devices[Unit].DeviceID
            #Domoticz.Log(str(self.listdevice[mac]))
            ip = self.listdevice[mac]['ipaddress']
            #Make request
            url = 'http://' + ip + ':8000/?action=System.Sleep'
            self.Request(url)

        #Recuperation de l'etat 30s apres, ca peut prendre du temps
        self.ForceUpdate(30)

    def onDisconnect(self, Connection):
        Domoticz.Debug("onDisconnect called for connection to: "+Connection.Address+":"+Connection.Port)
        if self.UpdateSucced == False:
            Domoticz.Error("Request not answer")
        self.httpConn = None
        self.url = None

    def onHeartbeat(self):
        self.counter += 1
        if self.counter > self.tempo:
            self.counter = 0
            Domoticz.Log("MAJ BBox")
            self.Request('/api/v1/hosts')

        if ADSL_QUALITY and (self.counter == self.tempo - 1):
            Domoticz.Log("MAJ ADSL quality")
            self.Request('/api/v1/wan/xdsl')


        Domoticz.Debug("HeartBeat")

#---------------------------------------------------------------------------------------------------------

    def ForceUpdate(self,time):
        self.counter = int(self.tempo - int(time) / 10)

    def Login(self):
        if Parameters["Mode2"] != "":
            self.password = Parameters["Mode2"]
            self.cookie = GetCookie(self.password)   

    def Request(self,url,data=None):
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

        if NO_DOMOTICZ_LIB:

            Domoticz.Debug("Making request " + _proto.lower() + "://" + _address + url)

            h = {
                'User-Agent':'Domoticz',\
                'Accept':'*/*' ,\
                'Host':URL,\
                'Connection':'keep-alive'\
                 }

            if self.cookie:
                h['Cookie'] = self.cookie

            try:
                if data:
                     result = requests.post( _proto.lower() + "://" + _address + url , headers=h, data = data, timeout = 5, verify=False)
                else:
                     result = requests.get( _proto.lower() + "://" + _address + url , headers=h, timeout = 5, verify=False)

                data2 = {}
                data2["Status"] = result.status_code
                data2["Data"] = result.content

                self.ManageAnswer(data2)

            except:
                Domoticz.Error("Connection error : Box non joignable")

        else:
            if not self.httpConn:
                self.UpdateSucced = False

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

            Dev_name = self.listdevice[i]['hostname']
            if Dev_name == "":
                Dev_name = self.listdevice[i]['ipaddress']

            #Create device if not exist
            if not unit:
                unit = FreeUnit()
                Domoticz.Status("DeviceCreation : " + Dev_name )
                Domoticz.Device(Name=Dev_name, Unit=unit, DeviceID=mac , Type=244, Subtype=73, Switchtype=0, Image=17, ).Create()

            active = Devices[unit].nValue

            if self.listdevice[i]['active'] != Devices[unit].nValue:
                kwarg = {}
                Domoticz.Log("Device Update : " + Dev_name )

                kwarg['SignalLevel'] = self.listdevice[i]['rssi']

                kwarg['nValue'] = self.listdevice[i]['active']
                if kwarg['nValue'] == 1:
                    kwarg['sValue'] = "On"
                else:
                    kwarg['sValue'] = "Off"

                Devices[unit].Update(**kwarg)

        if ADSL_QUALITY:
            unit = GetDevice("ADSL_QUALITY")
            if not unit:
                unit = FreeUnit()
                Domoticz.Device(Name="ADSL_QUALITY", Unit=unit, DeviceID="ADSL_QUALITY" , Type=243, Subtype=19 ).Create()
            kwarg = {}
            kwarg['nValue'] = 0
            kwarg['sValue'] = "Up: " + str(self.up) + " Down : " + str(self.down)
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
        result = requests.get('https://' + URL + '/api/v1/device/token' , headers=headers, timeout = 5, verify=False)
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
        result = requests.post('https://' + URL + '/api/v1/login' , headers=headers, data = data, timeout = 5, verify=False)
        cookie = 'BBOX_ID=' + result.cookies['BBOX_ID']
        Domoticz.Status("Cookie recupéré, mode admin possible !")
        return cookie
    except:
        Domoticz.Error("Pas de cookie recupéré, les fonctions demandant une autorisation ne marcheront pas")
        try:
            Domoticz.Error(str(result.json()))
        except:
            Domoticz.Error("No connexion usable")

    return None
