# Domoticz-BBox
Plugin pour Domoticz et le routeur de Bouygue telecom

# Description
- Donne la liste des appareils connectés ou pas sur votre reseau (avec une qualitée affichée pour le wifi) en créant un switch pour chacun, permettant de gerer les presences.   
- Permet d'allumer une machine a distance avec le WOL.   
- Permet d'arreter une machine avec l'appli "Switchoff".   
- En cas de problemes de compatiblitées, essayez de passer la variable NO_DOMOTICZ_LIB a True/False.   

# Installation.
- With command line, go to your plugins directory (domoticz/plugins).   
- Run:   
```git clone https://github.com/Smanar/Domoticz-BBox.git```
- (If needed) Make the plugin.py file executable:   
```chmod +x Domoticz-BBox/plugin.py```
- Restart Domoticz.   
- Enable the plugin in hardware page (hardware page, select deconz plugin, click "update").   

You can later update the plugin
- With command line, go to the plugin directory (domoticz/plugin/Domoticz-deCONZ).   
- Run:   
```git pull```
- Restart Domoticz.    

# Support
https://easydomoticz.com/forum/viewtopic.php?f=10&t=8806
