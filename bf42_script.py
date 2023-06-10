import os
import re
import math
import pickle
import json
import sys
import traceback
from pathlib import PurePosixPath as BFPath
from inspect import signature, Parameter

class BFMethodError(Exception): pass


class KeyedList:
    def __init__(self, valueToKeyFunc):
        self._list = list()
        self._dict = dict()
        self._valueToKeyFunc = valueToKeyFunc
    
    def append(self, value):
        self._list.append(value)
        self._dict[self._valueToKeyFunc(value)] = value
    
    def get(self, key, default=None):
        return self._dict.get(key, default)
    
    def index(self, value):
        return self._list.index(value)

    def __iter__(self):
        return self._list.__iter__()
    
    def __getitem__(self, x):
        if isinstance(x, int):
            return self._list[x]
        return self._dict[x]

class BFMethodMapper:
    def __init__(self, methods):
        self.methodInfos = {}
        for methodName, method in methods.items():
            methodInfo = {
                'method': method,
                'minparams': sum((1 if param.default == Parameter.empty else 0) for param in signature(method).parameters.values())-1,
                'maxparams': len(signature(method).parameters)-1,
            }
            self.methodInfos[methodName] = methodInfo
            self.methodInfos['set'+methodName] = methodInfo
    
    def callMethod(self, obj, name, arguments):
        methodInfo = self.methodInfos.get(name.lower())
        if not methodInfo: return False
        #argumentCount = len(arguments)
        #if argumentCount < methodInfo['minparams'] or methodInfo['maxparams'] < argumentCount:
            # raise AttributeError(f'Invalid number of parameters, {methodInfo["minparams"]} expected, got {argumentCount}')
            #return False
        try:
            return methodInfo['method'](obj, *arguments)
        except (TypeError, ValueError) as e:
            raise BFMethodError(str(e))

    @staticmethod
    def execMethod(obj, method, arguments):
        return obj.methodMapper.callMethod(obj, method, arguments)

def scriptclass(cls):
    methodMappingDict = {
        func.lower(): getattr(cls, func)
            for func in dir(cls)
                if callable(getattr(cls, func)) and not func.startswith('__')
    }
    cls.methodMapper = BFMethodMapper(methodMappingDict)
    return cls


# method to store objects as strings:
def dumps(objectToDump):
    return(json.dumps(objectToDump))
    # return(pickle.dumps(objectToDump).hex())
def loads(stringToLoad):
    return(json.loads(stringToLoad))
    # return(pickle.loads(bytes.fromhex(stringToLoad)))

class BF42_vec3:
    x = 0
    y = 0
    z = 0
    def __init__(self, vertex):
        if type(vertex) is str:
            v_str = vertex.split('/')
            v = []
            for vert_str in v_str:
                try:
                    v.append(float(vert_str))
                except ValueError:
                    pass
            if len(v) == 1 and len(v_str) == 1:
                self.x = v[0]
                self.y = v[0]
                self.z = v[0]
            elif len(v) == 2 and len(v_str) == 2:
                self.x = v[0]
                self.y = v[1]
            elif len(v) == 3 and len(v_str) == 3:
                self.x = v[0]
                self.y = v[1]
                self.z = v[2]
        else:
            self.x = vertex[0]
            self.y = vertex[1]
            self.z = vertex[2]
    def __eq__(self, other):
        if not isinstance(other, BF42_vec3):
            return False
        return self.x == other.x and self.y == other.y and self.z == other.z
    def str(self, numberOfSignif=6):
        strings = []
        for v in self.lst():
            if v == 0:
                v = 0 # prevent negative 0 (cosmetic)
            nrOfDigitsBeforeDot = int(math.log10(abs(v)))+1 if v != 0 else 0
            significance = max(6,4+nrOfDigitsBeforeDot)
            strings.append("%.*g" % (significance, v))
        return(strings[0]+"/"+strings[1]+"/"+strings[2])
    def str_floor(self, numberOfSignif=6): #for lightmap
        strings = []
        for v in self.lst():
            if v == 0:
                v = 0 # prevent negative 0 (cosmetic)
            nrOfDigitsBeforeDot = int(math.log10(abs(v)))+1 if v != 0 else 0
            significance = max(6,4+nrOfDigitsBeforeDot)
            string = "%.*g" % (significance, v)
            if "e" in string:
                strings.append("0")
            else:
                strings.append(string.split(".")[0])
        return(strings[0]+"-"+strings[1]+"-"+strings[2])
    def lst(self): # return new vector
        return([self.x, self.y, self.z])
    def toBlend(self,sceneScale = 1):
        return([self.x*sceneScale, self.z*sceneScale, self.y*sceneScale])
    def rotate(self, vec): # rotate vector yaw/pitch/roll
        ref = self.copy()
        self.x = ref.x*math.cos(math.radians(vec.x)) + ref.z*math.sin(math.radians(vec.x))
        self.z = -ref.x*math.sin(math.radians(vec.x)) + ref.z*math.cos(math.radians(vec.x))
        ref = self.copy()
        self.y = ref.y*math.cos(math.radians(vec.y)) - ref.z*math.sin(math.radians(vec.y))
        self.z = ref.y*math.sin(math.radians(vec.y)) + ref.z*math.cos(math.radians(vec.y))
        ref = self.copy()
        self.x = ref.x*math.cos(math.radians(vec.z)) - ref.y*math.sin(math.radians(vec.z))
        self.y = ref.x*math.sin(math.radians(vec.z)) + ref.y*math.cos(math.radians(vec.z))
        return(self)
    def add(self, vec): # return new vector
        self.x += vec.x
        self.y += vec.y
        self.z += vec.z
        return(self)
    def copy(self): # return new vector
        return(BF42_vec3((self.x,self.y,self.z)))

def bf42_vec3_Add(v1,v2):
    v = BF42_vec3((v1.x,v1.y,v1.z))
    return(v.add(v2))

class BF42_command:
    def __init__(self, cmd_str):
        self.className = None; self.method = None; self.arguments = []; self.targetVariable = None
        # regex = "^([\t\f ]*)([^\t^\f^ ^\.^\n]*)(?:(\.)([^\t^\f^ ^\n]*)){0,1}([\t\f ]*)([^\n]*)" # this is the regex to parse a whole file
        regex = "^[\t\f ]*([^\t^\f^ ^\.]*)(?:\.([^\t^\f^ ^\n]*)){0,1}[\t\f ]*(.*)"
        regexResult = re.findall(regex, cmd_str, flags = re.ASCII|re.IGNORECASE|re.MULTILINE)
        if len(regexResult) == 1:
            splitted = regexResult[0]
            if splitted[0] != "": self.className = splitted[0]
            if splitted[1] != "": self.method = splitted[1]
            if splitted[2] != "": 
                arguments_str = splitted[2]
                regex = r'(?:"(?:(?:.*?")|(?:.*)))|(?:[^\t^\f^ ]+)'
                self.arguments = [argument.replace('"', '') for argument in re.findall(regex, arguments_str, flags = re.ASCII)]
                if len(self.arguments) > 1 and self.arguments[-2] == "->" and self.arguments[-1].lower().startswith("v_"):
                    self.targetVariable = self.arguments[-1]
                    self.arguments = self.arguments[:-2]
    
    def __eq__(self, commandString): #commandString has className.method as format where either part can be empty
        parts = commandString.split('.', 1)
        className = True if parts[0] in ['', '*'] else parts[0]
        method = True if len(parts) == 1 or parts[1] in ['', '*'] else parts[1]
        if className != True:
            className = self.className.lower() == className.lower()
        if method != True:
            method = isMethod(self.method, method)
        return className == True and method == True

def isMethod(method, methodReference):
    return(method.lower() == methodReference.lower() or method.lower() == "set"+methodReference.lower())

def bf42_is_linked(template):
    return(type(template) != str or type(template) == int)

class BF42_data:
    def __init__(self):
        self.objectTemplates = KeyedList(lambda template: template.name.lower())
        self.networkableInfos = []
        self.geometryTemplates = KeyedList(lambda template: template.name.lower())
        self.objects = []
        self.staticObjects = [] # subCatergory of objects
        self.active_ObjectTemplate = None
        self.active_NetworkableInfo = None
        self.active_GeometryTemplate = None
        self.active_Object = None
        self.textureManager_alternativePaths = []
        self.console_worldSize = None
        self.game = BF42_Game()
        self.variables = {}
        self.constants = {}
        self.lastObjectTemplateID = -1
        self.lastObjectID = -1
        
        with open('constants.txt') as file:
            for line in file:
                parts = line.strip().split()
                self.constants[parts[0]] = parts[1]
    
    def getNextObjectTemplateID(self):
        self.lastObjectTemplateID += 1
        return(self.lastObjectTemplateID)
    
    def getNextObjectID(self):
        self.lastObjectID += 1
        return(self.lastObjectID)
    
    def getObject(self, name):
        for object in self.objects:
            if object.name.lower() == name.lower():
                return(objectTemplate)
        return(None)
    
    def getObjectTemplate(self, name):
        return self.objectTemplates.get(name.lower(), None)
    
    def getNetworkableInfo(self, name):
        for networkableInfo in self.networkableInfos:
            if networkableInfo.name.lower() == name.lower():
                return(networkableInfo)
        return(None)
    
    def getGeometryTemplate(self, name):
        return self.geometryTemplates.get(name)
        
    def creatLinks(self):
        for object in self.objects:
            if not bf42_is_linked(object.template):
                template = self.getObjectTemplate(object.template)
                if template != None:
                    object.template = template
        for objectTemplate in self.objectTemplates:
            for child in objectTemplate.childeren:
                if not bf42_is_linked(child.template):
                    template = self.getObjectTemplate(child.template)
                    if template != None:
                        child.template = template
                        template.parents.append(objectTemplate)
            if objectTemplate._networkableInfo:
                if not bf42_is_linked(objectTemplate._networkableInfo):
                    objectTemplate._networkableInfo = self.getNetworkableInfo(objectTemplate._networkableInfo)
            geometry = self.getGeometryTemplate(objectTemplate._geometry)
            if geometry != None:
                objectTemplate._geometry = geometry
        
    def dumps(self):
        list_dump = [[],[],[],[]]
        for objectTemplate in self.objectTemplates:
            geometry = self.geometryTemplates.index(objectTemplate.geometry) if bf42_is_linked(objectTemplate._geometry) else objectTemplate._geometry
            childeren = []
            for child in objectTemplate.childeren:
                template = self.objectTemplates.index(child.template) if bf42_is_linked(child.template) else child.template
                childeren.append([template, child.setPosition.lst(), child.setRotation.lst()])
            linePoints = [linePoint.lst() for linePoint in objectTemplate.linePoints]
            list_dump[0].append([objectTemplate.type, objectTemplate.name, geometry, objectTemplate.triggerRadius, linePoints, childeren])
        for geometryTemplate in self.geometryTemplates:
            list_dump[1].append([geometryTemplate.type, geometryTemplate.name, geometryTemplate.scale.lst(), geometryTemplate.file, geometryTemplate.materialSize, geometryTemplate.worldSize, geometryTemplate.yScale, geometryTemplate.waterLevel])
        for object in self.objects:
            template = self.objectTemplates.index(object.template) if bf42_is_linked(object.template) else object.template
            list_dump[2].append([template, object.absolutePosition.lst(), object.rotation.lst(), object.geometry_scale.lst()])
        for staticObject in self.staticObjects:
            list_dump[3].append(self.objects.index(staticObject))
        return(dumps(list_dump))
        
    def loads(self, dataDump):
        list_dump = loads(dataDump)
        # load objectTemplates
        for (type, name, geometry, triggerRadius, linePoints, childeren) in list_dump[0]:
            objectTemplate = BF42_ObjectTemplate(type, name)
            objectTemplate._geometry = geometry
            objectTemplate.triggerRadius = triggerRadius
            objectTemplate.linePoints = [BF42_vec3(linePoint) for linePoint in linePoints]
            for (template, setPosition, setRotation) in childeren:
                objectTemplateChild = BF42_ObjectTemplateChild(template)
                objectTemplateChild.setPosition = BF42_vec3(setPosition)
                objectTemplateChild.setRotation = BF42_vec3(setRotation)
                objectTemplate.childeren.append(objectTemplateChild)
            self.objectTemplates.append(objectTemplate)
        # load geometryTemplates
        for (type, name, scale, file, materialSize, worldSize, yScale, waterLevel) in list_dump[1]:
            geometryTemplate = BF42_GeometryTemplate(type, name)
            geometryTemplate.scale = BF42_vec3(scale)
            geometryTemplate.file = file
            geometryTemplate.materialSize = materialSize
            geometryTemplate.worldSize = worldSize
            geometryTemplate.yScale = yScale
            geometryTemplate.waterLevel = waterLevel
            self.geometryTemplates.append(geometryTemplate)
        # link objectTemplates
        for objectTemplate in self.objectTemplates:
            for child in objectTemplate.childeren:
                if bf42_is_linked(child.template):
                    child.template = self.objectTemplates[child.template]
            if bf42_is_linked(objectTemplate._geometry):
                objectTemplate._geometry = self.geometryTemplates[objectTemplate._geometry]
        # load and link objects
        for (template, absolutePosition, rotation, geometry_scale) in list_dump[2]:
            object = BF42_Object("")
            object.template = self.objectTemplates[template] if bf42_is_linked(template) else template
            object.absolutePosition = BF42_vec3(absolutePosition)
            object.rotation = BF42_vec3(rotation)
            object.geometry_scale = BF42_vec3(geometry_scale)
            self.objects.append(object)
        # load and link staticObjects
        for i in list_dump[3]:
            self.staticObjects.append(self.objects[i])
        return(self)

predictionModeEnum = ['PMNone', 'PMLinear', 'PMCubic', 'PMUsePhysics']

@scriptclass
class BF42_Game:
    def __init__(self):
        self._mapId = None
        self._activeCombatArea = None
        self._customGameName = None
        self._customGameVersion = None
        self._multiplayerBriefingObjectives = None
        self._objectiveBriefing = None
        self._modPaths = []
    
    def setMapId(self, value): self._mapId = value
    def setActiveCombatArea(self, a,b,c,d): self._activeCombatArea = (int(a), int(b), int(c), int(d))
    def customGameName(self, value = None):
        if value != None: self._customGameName = value
        return(self._customGameName)
    def customGameVersion(self, value = None):
        if value != None: self._customGameVersion = value
        return(self._customGameVersion)
    def addModPath(self, value): self._modPaths.append(value)
    def setMultiplayerBriefingObjectives(self, value): self._multiplayerBriefingObjectives = value
    def setObjectiveBriefing(self, value): self._objectiveBriefing = value


@scriptclass
class BF42_ObjectTemplate:
    def __init__(self, type, name, ID):
        self.ID = ID
        self.type = type
        self.name = name
        self._networkableInfo = None
        self._geometry = "" # string will be replaced by a reference after linking
        self._maxHitPoints = 10
        self._minRotation = BF42_vec3((0,0,0))
        self._maxRotation = BF42_vec3((0,0,0))
        self._maxSpeed = BF42_vec3((1,1,1))
        self._acceleration = BF42_vec3((0.1,0.1,0.1))
        self._inputToYaw = 55
        self._inputToPitch = 55
        self._inputToRoll = 55
        self._automaticReset = False
        self._magSize = 30
        self._numOfMag = 3
        self._numberOfGears = None
        self._gearUp = 0.7
        self._gearDown = 0.3
        self._triggerRadius = 0
        self._linePoints = []
        self._controlPointName = ""
        self._team = None
        self._unableToChangeTeam = None
        
        self._MinSpawnDelay = None
        self._MaxSpawnDelay = None
        self._SpawnDelayAtStart = None
        self._TimeToLive = None
        self._Distance = None
        self._DamageWhenLost = None
        self._maxNrOfObjectSpawned = None
        self._teamOnVehicle = None
        self._objectTemplates = {} # for objectSpawners
        
        self.childeren = []
        self.active_child = None
        self.parents = [] # not used inside module
    
    def networkableInfo(self, value):
        if value != None: self._networkableInfo = value
        return(self._networkableInfo)
    def geometry(self, value):
        if value != None: self._geometry = value
        return(self._geometry)
    def maxHitPoints(self, value = None):
        if value != None: self._maxHitPoints = float(value)
        return(self._maxHitPoints)
    def minRotation(self, value = None):
        if value != None: self._minRotation = BF42_vec3(value)
        return(self._minRotation)
    def maxRotation(self, value = None):
        if value != None: self._maxRotation = BF42_vec3(value)
        return(self._maxRotation)
    def maxSpeed(self, value = None):
        if value != None: self._maxSpeed = BF42_vec3(value)
        return(self._maxSpeed)
    def acceleration(self, value = None):
        if value != None: self._acceleration = BF42_vec3(value)
        return(self._acceleration)
    def inputToPitch(self, value = None):
        if value != None: self._inputToPitch = int(value)
        return(self._inputToPitch)
    def inputToYaw(self, value = None):
        if value != None: self._inputToYaw = int(value)
        return(self._inputToYaw)
    def inputToRoll(self, value = None):
        if value != None: self._inputToRoll = int(value)
        return(self._inputToRoll)
    def automaticReset(self, value = None):
        if value != None: self._automaticReset = bool(int(value))
        return(self._automaticReset)
    def magSize(self, value = None):
        if value != None: self._magSize = int(value)
        return(self._magSize)
    def numOfMag(self, value = None):
        if value != None: self._numOfMag = int(value)
        return(self._numOfMag)
    def numberOfGears(self, value = None):
        if value != None: self._numberOfGears  = int(value)
        return(self._numberOfGears)
    def gearUp(self, value = None):
        if value != None: self._gearUp  = float(value)
        return(self._gearUp )
    def gearDown(self, value = None):
        if value != None: self._gearDown  = float(value)
        return(self._gearDown)
    def triggerRadius(self, value): self._triggerRadius = int(value)
    def addLinePoint(self, value): self._linePoints.append(BF42_vec3(value))
    def controlPointName(self, value): self._controlPointName = value
    def team(self, value): self._team = value
    def unableToChangeTeam(self, value): self._unableToChangeTeam = value
    
    def MinSpawnDelay(self, value): self._MinSpawnDelay = value
    def MaxSpawnDelay(self, value): self._MaxSpawnDelay = value
    def SpawnDelayAtStart(self, value): self._SpawnDelayAtStart = value
    def TimeToLive(self, value): self._TimeToLive = value
    def Distance(self, value): self._Distance = value
    def DamageWhenLost(self, value): self._DamageWhenLost = value
    def maxNrOfObjectSpawned(self, value): self._maxNrOfObjectSpawned = value
    def teamOnVehicle(self, value): self._teamOnVehicle = value
    def setObjectTemplate(self, key, value): self._objectTemplates[int(key)] = value
    
    def addTemplate(self, value):
        self.active_child = BF42_ObjectTemplateChild(value)
        self.childeren.append(self.active_child)
    def setActiveTemplate(self, value):
        if len(self.childeren) > int(value):
            self.active_child = self.childeren[int(value)]
    def removeTemplate(self, value):
        if len(self.childeren) > int(value):
            self.childeren.pop(int(value))
    def setPosition(self, value):
        if self.active_child != None:
            self.active_child.setPosition = BF42_vec3(value)
    def setRotation(self, value):
        if self.active_child != None:
            self.active_child.setRotation = BF42_vec3(value)


class BF42_ObjectTemplateChild:
    def __init__(self, template):
        self.template = template
        self.setPosition = BF42_vec3((0,0,0))
        self.setRotation = BF42_vec3((0,0,0))

@scriptclass
class BF42_NetworkableInfo:
    def __init__(self, name):
        self.name = name
        self._isUnique = False
        self._basePriority = 1.0
        self._predictionMode = 0 # PMNone
        self._predictionMode = 0 # PMNone
        self._forceNetworkableId = False
    
    def setBasePriority(self, value): self._basePriority = float(value)
    def setIsUnique(self, value): self._isUnique = bool(int(value))
    def setPredictionMode(self, value): self._predictionMode = predictionModeEnum.index(value)


@scriptclass
class BF42_GeometryTemplate:
    def __init__(self, type, name):
        self.type = type
        self.name = name
        self._scale = BF42_vec3((1,1,1))
        self._file = None
        self._materialSize = 256
        self._worldSize = 1024
        self._yScale = 1
        self._waterLevel = 0
    
    def scale(self, value): self._scale = BF42_vec3(value)
    def file(self, value): self._file = value.replace("\\","/")
    def materialsize(self, value): self._materialsize = int(value)
    def worldsize(self, value): self._worldsize = int(value)
    def yscale(self, value): self._yscale = float(value)
    def waterlevel(self, value): self._waterlevel = float(value)


class BF42_Object:
    def __init__(self, template, ID):
        self.ID = ID
        self.template = template
        self.name = "" # toDo: find out the object ID/name logic/generation
        self.absolutePosition = BF42_vec3((0,0,0))
        self.rotation = BF42_vec3((0,0,0))
        self.geometry_scale = BF42_vec3((1,1,1))
        self.OSId = None
        self.team = None
    
    def setProperty(self, name, arguments):
        if len(arguments) == 1: # all used commands thus far require 1 argument
            value = arguments[0]
            if isMethod(name, "absoluteposition"): self.absolutePosition = BF42_vec3(value)
            elif isMethod(name, "rotation"): self.rotation = BF42_vec3(value)
            elif isMethod(name, "geometry.scale"): self.geometry_scale = BF42_vec3(value)
            elif isMethod(name, "osid"): self.OSId = value
            elif isMethod(name, "team"): self.team = value
            elif isMethod(name, "name"): self.name = value

def bf42_evaluate(value1, operator, value2):
    if operator == "==":
        return(value1.lower() == value2.lower())
    return(False)

class BF42_script:
    def __init__(self, data = None, rfaGroup = None):
        if data == None: data = BF42_data()
        self.REM = False
        self.IFs = [] # 0 = False, 1 = True, 2 = has already been True
        self.rfaGroup = rfaGroup
        self.data = data
        
    def read(self, path, staticObjects = False, forceExternalPath = False, v_args = None):
        data = self.data
        if v_args != None:
            for i, v_arg in enumerate(v_args):
                data.variables["v_arg"+str(i+1)] = v_arg
        lines = []
        try:
            if self.rfaGroup == None or forceExternalPath:
                fp = open(path, 'r', errors='replace')
                lines = fp.readlines()
            else:
                fileString = self.rfaGroup.extractFile(str(path), asString = True)
                if fileString == False:
                    raise Exception(f"Can't find path in RFA: {path}")
                lines = iter(fileString.splitlines())
        except:
            print("Could not find file: "+path, file = sys.stderr)
        for lineNumber0, line_raw in enumerate(lines):
            try:
                line = line_raw.strip()
                command = BF42_command(line)
                if command.className != None:
                    numArgs = len(command.arguments)
                    if command not in ["var", "const"]:
                        for i in range(numArgs):
                            if command.arguments[i].lower().startswith('v_'):
                                command.arguments[i] = data.variables[command.arguments[i]] if command.arguments[i] in data.variables else command.arguments[i]
                            elif command.arguments[i].lower().startswith('c_'):
                                command.arguments[i] = data.constants[command.arguments[i]] if command.arguments[i] in data.constants else command.arguments[i]
                    if command == "beginrem":
                        self.REM = True
                    elif command == "endrem":
                        self.REM = False
                    elif not command == "rem" and not self.REM:
                        if command == "if" and numArgs == 3:
                            if bf42_evaluate(*command.arguments):
                                self.IFs.append(1)
                            else:
                                self.IFs.append(0)
                        elif command == "elseif" and numArgs == 3:
                            if len(self.IFs) > 0:
                                if self.IFs[-1] == 0:
                                    if bf42_evaluate(*command.arguments):
                                        self.IFs[-1] = 1
                                elif self.IFs[-1] == 1:
                                    self.IFs[-1] = 2
                            else:
                                pass # elseif without if
                        elif command == "else" and numArgs == 0:
                            if len(self.IFs) > 0:
                                if self.IFs[-1] == 0:
                                    self.IFs[-1] = 1
                                elif self.IFs[-1] == 1:
                                    self.IFs[-1] = 2
                            else:
                                pass # else without if
                        elif command == "endif" and numArgs == 0:
                            if len(self.IFs) > 0:
                                self.IFs.pop()
                            else:
                                pass # endif without if
                        elif not any(x in self.IFs for x in [0, 2]):
                            if command.method != None:
                                if command == "objectTemplate":
                                    if command == ".create":
                                        if numArgs == 2:
                                            if data.getObjectTemplate(command.arguments[1]) == None:
                                                data.active_ObjectTemplate = BF42_ObjectTemplate(command.arguments[0], command.arguments[1], data.getNextObjectTemplateID())
                                                data.objectTemplates.append(data.active_ObjectTemplate)
                                    elif command == ".active":
                                        if numArgs == 1:
                                            refered_ObjectTemplate = data.getObjectTemplate(command.arguments[0])
                                            if refered_ObjectTemplate != None:
                                                data.active_ObjectTemplate = refered_ObjectTemplate
                                    else:
                                        if data.active_ObjectTemplate != None:
                                            BFMethodMapper.execMethod(data.active_ObjectTemplate, command.method, command.arguments)
                                elif command == "networkableInfo":
                                    if command == ".createNewInfo":
                                        if numArgs == 1:
                                            if data.getNetworkableInfo(command.arguments[0]) == None:
                                                data.active_NetworkableInfo = BF42_NetworkableInfo(command.arguments[0])
                                                data.networkableInfos.append(data.active_NetworkableInfo)
                                    else:
                                        if data.active_NetworkableInfo != None:
                                            BFMethodMapper.execMethod(data.active_NetworkableInfo, command.method, command.arguments)
                                elif command == "geometryTemplate":
                                    if command == ".create":
                                        if numArgs == 2:
                                            if data.getGeometryTemplate(command.arguments[1]) == None:
                                                data.active_GeometryTemplate = BF42_GeometryTemplate(command.arguments[0], command.arguments[1])
                                                data.geometryTemplates.append(data.active_GeometryTemplate)
                                    elif command == ".active":
                                        if numArgs == 1:
                                            refered_GeometryTemplate = data.getGeometryTemplate(command.arguments[0])
                                            if refered_GeometryTemplate != None:
                                                data.active_GeometryTemplate = refered_GeometryTemplate
                                    else:
                                        if data.active_GeometryTemplate != None:
                                            BFMethodMapper.execMethod(data.active_GeometryTemplate, command.method, command.arguments)
                                
                                elif command == "object":
                                    if command == ".create":
                                        if numArgs == 1:
                                            data.active_Object = BF42_Object(command.arguments[0], data.getNextObjectID())
                                            data.objects.append(data.active_Object)
                                            if staticObjects:
                                                data.staticObjects.append(data.active_Object)
                                    elif command == ".active":
                                        if numArgs == 1:
                                            refered_Object = data.getObject(command.arguments[0])
                                            if refered_Object != None:
                                                data.active_Object = refered_Object
                                    else:
                                        if data.active_Object != None:
                                            data.active_Object.setProperty(command.method, command.arguments)
                                
                                elif command == "texturemanager":
                                    if command == ".alternativepath":
                                        if numArgs == 1:
                                            data.textureManager_alternativePaths.append(command.arguments[0])
                                
                                elif command == "game":
                                    returnValue = BFMethodMapper.execMethod(data.game, command.method, command.arguments)
                                    if command.targetVariable != None and returnValue != False and command.targetVariable in data.variables:
                                        data.variables[command.targetVariable] = returnValue
                                
                                elif command == "console":
                                    if command == ".worldsize":
                                        if numArgs == 1:
                                            data.console_worldSize = int(command.arguments[0])
                            else:
                                if command == "include":
                                    if numArgs == 1:
                                        path_include = os.path.relpath(str(BFPath(path).parent / command.arguments[0]))
                                        self.read(path_include, data)
                                elif command == "run":
                                    if numArgs >= 1:
                                        path_run = BFPath(command.arguments[0])
                                        if path_run.suffix == "":
                                            path_run = path_run.with_suffix(".con")
                                        path_run = os.path.relpath(str(BFPath(path).parent / path_run))
                                        v_args_run = command.arguments[1:] if len(command.arguments) > 1 else []
                                        BF42_script(data = data, rfaGroup = self.rfaGroup).read(path_run, v_args = v_args_run)
                                elif command == "var":
                                    if numArgs == 3:
                                        data.variables[command.arguments[0]] = command.arguments[2]
                                    elif numArgs == 1:
                                        if command.arguments[0] not in data.variables:
                                            data.variables[command.arguments[0]] = "" # or should it be set to None?
                                elif command == "const":
                                    if numArgs == 3:
                                        data.constants[command.arguments[0]] = command.arguments[2]
                                    elif numArgs == 1:
                                        if command.arguments[0] not in data.constants:
                                            data.constants[command.arguments[0]] = "" # or should it be set to None?
                                elif command.className.lower().startswith('v_'):
                                    if numArgs == 2:
                                        if command.className in data.variables:
                                            data.variables[command.className] = command.arguments[1]
                                elif command.className.lower().startswith('c_'):
                                    if numArgs == 2:
                                        if command.className in data.constants:
                                            data.constants[command.className] = command.arguments[1]
            except BFMethodError:
                #traceback.print_exc(file = sys.stderr)
                print(f'Exception in BF42_script.read(): {path} ({lineNumber0+1}): {line}', file = sys.stderr)
                
        return(self.data)


def bf42_readAllScripts(bf42_data, base_path, level = None):
    for path, subdirs, files in os.walk(BFPath(base_path) / "Objects"):
        for name in files:
            filePath = BFPath(path, name)
            if filePath.suffix.lower() == ".con":
                BF42_script(bf42_data).read(filePath)
    if level != None:
        BF42_script(bf42_data).read(BFPath(base_path) / "Bf1942/Levels" / level / "Init.con", v_args = ["host"])
        BF42_script(bf42_data).read(BFPath(base_path) / "Bf1942/Levels" / level / "Conquest.con", v_args = ["host"])
        BF42_script(bf42_data).read(BFPath(base_path) / "Bf1942/Levels" / level / "StaticObjects.con", staticObjects = True, v_args = ["host"])

def bf42_writeStaticCon(path, objects, data):
    data.objects = objects
    data.creatLinks()
    with open(path, 'w') as f:
        for object in objects:
            templateName = object.template.name if bf42_is_linked(object.template) else object.template
            f.write("object.create "+templateName+"\n")
            f.write("object.absolutePosition "+object.absolutePosition.str()+"\n")
            f.write("object.rotation "+object.rotation.str()+"\n")
            if bf42_is_linked(object.template):
                meshes = bf42_listAllGeometries(object.template)
                for mesh in meshes[0]:
                    if mesh[1].lower() == "treemesh":
                        f.write("object.geometry.scale 1\n")
                        break
            f.write("\n")
    return objects

def bf42_readAllConFiles(base_path, level):
    bf42_data = BF42_data()
    bf42_readAllScripts(bf42_data, base_path, level) 
    bf42_data.creatLinks()
    return(bf42_data)



# These two functions are for processing in Blender:
def bf42_listAllGeometries(objectTemplate, pos = None, rot = None, isFarLod = False):
    # ToDo:
    # child templates are first moved and then rotated (relative to the parent origin)
    if pos == None:
        pos = BF42_vec3((0,0,0))
    if rot == None:
        rot = BF42_vec3((0,0,0))
    list = [[],[]] # [[close LOD] , [far LOD]]
    if bf42_is_linked(objectTemplate.geometry):
        geometryTemplate = objectTemplate.geometry
        if geometryTemplate.file != "":
            list[1 if isFarLod else 0].append((geometryTemplate.file, geometryTemplate.type, pos, rot))
    for i, child in enumerate(objectTemplate.childeren):
        if objectTemplate.type.lower() == "lodobject":
            if not len(objectTemplate.childeren) in [2,3]:
                print("Error: "+objectTemplate.name+" has wrong number of children for LodObject!!")
            if i == 1:
                isFarLod = True
            if i == 2: # dont add destroyed LOD
                break
        if bf42_is_linked(child.template):
            subList = bf42_listAllGeometries(child.template, bf42_vec3_Add(pos, child.setPosition.copy().rotate(rot)), bf42_vec3_Add(rot, child.setRotation), isFarLod) # can I add rotation vectors?
            list[0] += subList[0]
            list[1] += subList[1]
    return(list)

def bf42_listAllGeometries_new(objectTemplate, pos = None, rot = None, isFarLod = False):
    # ToDo:
    # child templates are first moved and then rotated (relative to the parent origin)
    if pos == None:
        pos = BF42_vec3((0,0,0))
    if rot == None:
        rot = BF42_vec3((0,0,0))
    list = [[],[]] # [[close LOD] , [far LOD]]
    if bf42_is_linked(objectTemplate.geometry):
        if objectTemplate.geometry.file != "":
            list[1 if isFarLod else 0].append((objectTemplate.geometry, pos, rot))
    for i, child in enumerate(objectTemplate.childeren):
        if objectTemplate.type.lower() == "lodobject":
            if not len(objectTemplate.childeren) in [2,3]:
                print("Error: "+objectTemplate.name+" has wrong number of childeren for LodObject!!")
            if i == 1:
                isFarLod = True
            if i == 2: # dont add destroyed LOD
                break
        if bf42_is_linked(child.template):
            subList = bf42_listAllGeometries_new(child.template, bf42_vec3_Add(pos, child.setPosition.copy().rotate(rot)), bf42_vec3_Add(rot, child.setRotation), isFarLod) # can I add rotation vectors?
            list[0] += subList[0]
            list[1] += subList[1]
    return(list)
