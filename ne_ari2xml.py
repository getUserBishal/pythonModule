# this module already parsed(already written) the components of ariadne schematics 
#!/usr/bin/env python3
# -*- coding: iso-8859-1 -*-
DEF_LIB_ARI_VER = "0.9" # application version
"""
 <')))>< ne_ari2xml.py fst:19.01.22 lst: 07.03.s22
 ariadne converter
 - convert ariadne schematic files *.sca to eagle *.sch xml files
  - eagle.sch can be imported with kicad V6 (Import eagle function)


"""

#from token import TYPE_COMMENT
from asyncio.log import logger
from typing import KeysView
#import pcbnew
#import configparser
import logging
import math
import locale
from xml.dom.pulldom import parseString
#import svgwrite

#import argparse
#import sys
#import os


#DEF_F2LOAD_SCA="../../test/R_2_ariad/A3-Rahmen.sca"
#DEF_FINI = './ne_ari2xml.ini' # ini file name 


# init environment

"""
logger = logging.getLogger()
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)
"""

# NE Part status
class CNePartStatus:
    def __init__(self):
        self.stat = CNePartStatus.eACTIVE

    def pp(self):
        if self.stat == CNePartStatus.eACTIVE:
            return "ACTIVE"
        elif self.stat == CNePartStatus.ePROTO:      
            return "PROTO"
        elif self.stat == CNePartStatus.eDISCONT:      
            return "PROTO"
        elif self.stat == CNePartStatus.eREPLACE:      
            return "PROTO"
        elif self.stat == CNePartStatus.eREMOVED:      
            return "PROTO"
        else:
            return "UNKNOWN"

    eUNKNOWN    = 0 # not defined in fp(footprint)
    eACTIVE     = 1 # normal status
    ePROTO      = 2 # prototype
    eDISCONT    = 3 # Discontinued
    eREPLACE    = 4 # replacement / borker
    eREMOVED    = 5 # removed 

# Ariadne object sections will be swicthed on with *SECNAME* in the ariadne files
class CAridSec:
    def __init__(self):
        self.type = CAridSec.eSEC_NONE

    """
        return >0 for an object type, parsed from any ariadne file 
    """
    @staticmethod
    def check_sec_type(line):
        sec_idx, sec_arg = CAridSec.get_sec_idx_and_arg(line)
        return sec_idx

    """ somtimes the *SECTION* has an argument after the last '*' e.g. *SIGNAL* D0
        @return *sec-index, argument
    """
    @staticmethod
    def get_sec_idx_and_arg(line):
        idx = CAridSec.eSEC_NONE
        sec_arg = None
        if line.find('*') >=0:
            for i, sec in enumerate(CAridSec.lst_sec):
                if line.find(sec) == 0:
                    idx = i
                    sec_arg = line[len(sec):]
                    if len(sec_arg) == 0:
                        sec_arg = None
                    else:
                        sec_arg = sec_arg.strip(' ')
                    break    

        return (idx,sec_arg)


    """ section in sca files that will ne ignored
        ATENTION: positin in list is important !!!!
    """
    lst_sec = [
        '*ARIADNE*', # index 0
        '*SCM*',
        '__DIS__*VERSION*',
        '__DIS__*UNIT*',
        '__DIS__*ACTIVE*',
        '__DIS__*COLOR*',
        '*LINES*',      # 6
        '*SHEETFORM*',  # 7 
        '*SHEET*',      # 8 
        '*SYMBOL*',     # 9
        '*TEXT*',       # 10 text
        '*COMPONENT*',  # 11 
        '*PARTTYPE*',   # 12
        '*SYMREF*',     # 13
        '*DRAWING*',    # 14 nop
        '*SIGNAL*',     # 15 with argument e.g. VCC
        '*DEFAULT*',    # 16  
        '*END*'
    ]

    @staticmethod
    def get_sec_index(line):
        try :
            return CAridSec.lst_sec.index(line)
        except IndexError:
            pass
        except ValueError:
            return -1

    eSEC_NONE       = -1
    eSEC_SHEET_LINES= 6 # sheet lines  
    eSEC_SHEETFORM  = 7 # sheet, descriptions, frames and logo
    eSEC_SHEET      = 8 # sheet, number and base position og the whole sheet
    eSEC_SYMBOL     = 9 # symbol from *.sca schematic e.g. R,C,L and others
    eSEC_SHEET_TEXT = 10 # sheet text 
    eSEC_COMPONENT  = 11 # oneliner e.g  @R1       10R:MINIMELF
    eSEC_PARTTYPE   = 12 # parttype from *.sca schematic
    eSEC_SYMREF     = 13 # witch symbol on pos x,y, sheet for the component e.g. @WID S1  300 265 90 N 1 R204
    eSEC_DRAWING    = 14 # Drawing net drawings,line and symbols 
    eSEC_SIGNAL     = 15 # Signal section with argument e.g. VCC, GND, $S6 
    eSEC_DEFAULT    = 16 # disabled
    eSEC_DB_ART     = 100 # Not a real section, force this one to load db art numers
    eSEC_IGNORE     = 998 # ignore this sections
    eSEC_END        = 999 # Object END-MARKER *END*


class CAridObjBase:

    range_def = [+999999,-999999]
    x_range = range_def[:]  # min,max over all Objects
    y_range = range_def[:]  # min,max over all Objects
    
    def __init__(self):  #  Object name
        self.name = None # unknown name
        self.type = -1 # @audit-ok Arid Object type
        self.is_valid = False # object was created and validated
        self.lines = [] # all lines of this object

        self.x = None
        self.y = None

        self.x_range = CAridObjBase.range_def[:]  # min,max this object
        self.y_range = CAridObjBase.range_def[:]  # min,max this object

    @staticmethod
    def xy_reset():
        CAridObjBase.x_range = CAridObjBase.range_def[:]  # min,max
        CAridObjBase.y_range = CAridObjBase.range_def[:]  # min,max  
    
    @staticmethod
    def xy_pp_range(x_range,y_range):
        range = 'range:('    + str(int(x_range[0])) + ' < x < ' +  str(int(x_range[1]))
        range += '),('      + str(int(y_range[0])) + ' < y < ' +  str(int(y_range[1]))
        range += ')'
        return range 

    @staticmethod
    def xy_pp():
        return CAridObjBase.xy_pp_range(CAridObjBase.x_range,CAridObjBase.y_range)

    def xy_self_pp(self):
        return CAridObjBase.xy_pp_range(self.x_range,self.y_range)

    def xy_set(self,x,y):
        self.x = float(x)
        if CAridObjBase.x_range[1] < self.x:
            CAridObjBase.x_range[1] = self.x
        if CAridObjBase.x_range[0] > self.x:
            CAridObjBase.x_range[0] = self.x    
        self.y = float(y)
        if CAridObjBase.y_range[1] < self.y:
            CAridObjBase.y_range[1] = self.y
        if CAridObjBase.y_range[0] > self.y:
            CAridObjBase.y_range[0] = self.y

        if self.x_range[1] < self.x:
            self.x_range[1] = self.x
        if self.x_range[0] > self.x:
            self.x_range[0] = self.x    
        if self.y_range[1] < self.y:
            self.y_range[1] = self.y
        if self.y_range[0] > self.y:
            self.y_range[0] = self.y

    @staticmethod
    def xy_append_range(x_range,y_range):

        if x_range[1] < CAridObjBase.x_range[1]:
            x_range[1] = CAridObjBase.x_range[1]
        if x_range[0] > CAridObjBase.x_range[0]:
            x_range[0] = CAridObjBase.x_range[0]    
        if y_range[1] < CAridObjBase.y_range[1]:
            y_range[1] = CAridObjBase.y_range[1]
        if y_range[0] > CAridObjBase.y_range[0]:
            y_range[0] = CAridObjBase.y_range[0]


    # store collected Range to range object
    def xy_store(range_obj): 
        range_obj.xy_set(CAridObjBase.x_range[0],CAridObjBase.y_range[0])
        range_obj.xy_set(CAridObjBase.x_range[1],CAridObjBase.y_range[1])

    def pp(self):
        sout = 'Name:' + self.name + ' OK:' + str(self.is_valid)
        return sout

    # the default parser will eat the lines in lines list
    # return None for an exception, else the object
    def parse(self):
        return None

""" Arid Part bind a decal(footprint to the symbol)
    Ariadne Doc:12-44
    @BC238B ANA NPN 2 1 1  <- Header   (2xTextLine 1 Decal 1 Function)
    # Class: TRAN          <- TextLine 1
    # Date: 20.11.92       <  Text Line 2
    :TO92                  <- One Decal
    G 1 3 :NPN             <- Function
    1,1,B,U,                   ""
    2,2,E,U,                   ""
    3,3,C,U,                   ""
    
    Header:
    @74244[XX] TTL BUFFER  3 4 11
    2) Name[Suffix] =  74244[XX]
    4) Tech = TTL 
    5) Familiy = BUFFER  0 fÃ¼r keine Familie, only a search hashtag ?
    6/7) Call!Extension = search criteria !!! Nicht im Beispiel 
    8) TextLines= 3 Text-Lines After this header line  
    9) Decalls(min 1) =4  Number of used decals
    10 Functions=11 Number of Functions (Not Lines) (Kopfzeilen)
    
    Decal:
    DIP20:SO20L-R:[NEXT-DECAL]   min 1 decal
    
    Function-Lines:
    Kopfzeilen:
    FUNC SwapGrp CONN SubGates [:Symbol]
      1)   2)      3)   4)        5)
    1) FUNC:
    M: MainGates Hauptgatter (Chip-Select?)
    G: Gatter, fÃ¼hrendes Main Gate Symbol entfÃ¤llt    
    P: Pin-Info Stecker
    S: Specail Gatter
    H: Bohr/ Befestigung
    2) SwapGrp 0: Kann nicht mit anderen Gattern Getauscht werden >0 In Gruppe tauschbar
    3) CONN Anzahl der AnschlÃ¼sse
    4)  SUB-Gates Wirksam bei MainGate: Anzahl der untergeod. Gatter
    5) Symbol
    
    M 1 1 4:BUF4
    :
    G 1 2
    :
    S 0 2
   
    Pinbschreibung:
    SymbPin, DecalPin, PinName, SwapGrp, PinType, SigName, TrackWidth
        1)      2)        3)       4)        5)      6)        7
    1) PinNumber 0:  No Pin in Symbol
    3) Pin-Name : z.B. Transistor C B E,  Logik-Pin: A2, A2
    5) PinType: I(nput),O(utput),U(ndef), B(idirect), G(nd) , P(ower
    6  Signal Name (As Option)
    7) Track Width 58 (mil), oder 1.46mm
    
"""
class CAridPartType(CAridObjBase):

    db = {} # store all the PartTypes here key is the name e.g BC238B 

    class CPinFunction:

        db = {} # store all pin function objects key is the symbol-key name eg CM4-1  

        def __init__(self,parent,func_type,line):
            self.func_type = func_type
            self.swap_grp_id = 0 # 0 don't swap >0: group-id, can swap with the same id 
            self.num_conn = 0 # number of connectors
            self.num_sub_gates = 0  # number of sub gates
            self.symbols = [] # symbols
            self.lst_pin = [] # pin objects
            self.parent = parent
    
  
        @staticmethod
        def parse_type(line):
            type =  CAridPartType.CPinFunction.ePF_UNKNOWN
            p2idx = ['M','G','P','S','H']
            for i,func in enumerate(p2idx):
                if line.find(func) == 0:
                    type = i
                    break
            return type


        # symbol is ':' seperated e.g.   ':IC9543A'  or ':IC-CM4-1'  or a list :R-SPULE-GEP-A:R-SPULE-GEP-B:R-SPULE-GEP-C:R-SPULE-GEP-D
        def set_symbol_list(self,s_symbol):
            tok = CAridParserObj.tokenize(s_symbol,':')
            for symbol in tok:
                self.symbols.append(symbol)
                CAridPartType.CPinFunction.db[symbol] = self


        # e.g.  G 0 100   :IC-CM4-1
        def parse_line(self, lst_tok):
            #self.func_type <-> lst_tok[0] is the already parsed type
            self.swap_grp_id = int(lst_tok[1])
            self.num_conn = int(lst_tok[2])
          
            if len(lst_tok) > 3:
                if self.func_type == CAridPartType.CPinFunction.ePF_MAIN_GATE:
                    self.num_sub_gates = int(lst_tok[3])
                    self.set_symbol_list(lst_tok[4]) # symbols are column seperated
                else:
                    self.set_symbol_list(lst_tok[3]) # symbols are column seperated
            
            #print(str(lst_tok))
            return True

        ePF_UNKNOWN    = -1 # unknown
        ePF_MAIN_GATE  = 0 # M(ain-Gate)
        ePF_GATE       = 1 # G(ate)
        ePF_PIN        = 2 # P(in) info 
        ePF_SPECIAL    = 3 # S(ecial)
        ePF_DRILL      = 4 # H(ole) / Drill

    class CPin:
        def __init__(self):
            self.pin_sym = 0 # symbol pin
            self.pin_dec = 0 # decal pin
            self.name = "" # name of the pin
            self.swap_group_id = 0 # all in a group can swap, 0: dont swap
            self.pin_type = CAridPartType.CPin.ePT_UNKNOWN # PinType: I(nput),O(utput),U(ndef), B(idirect), G(nd) , P(ower)
            self.opt_sig_name = "" # option signal-name
            self.tack_with = -1 # 58 (mil), oder 1.46mm
        
        def parse_line(self, lst_tok):
            self.pin_sym =  int(lst_tok[0])
            self.pin_dec =  int(lst_tok[1])
            self.name = lst_tok[2]
            self.swap_grp_id = int(lst_tok[3])
            self.pin_type = CAridPartType.CPin.parse_pin_type(lst_tok[4])
            return True

        @staticmethod
        def parse_pin_type(tok):
            type =  CAridPartType.CPin.ePT_UNKNOWN
            p2idx = ['I','O','U','B','G','P']
            for i,type in enumerate(p2idx):
                if tok.find(type) == 0:
                    type = i
                    break
            return type

        ePT_UNKNOWN    = -1 # Unknwon
        ePT_IN         = 0 # I(nput)
        ePT_OUT        = 1 # O(utput)
        ePT_UNDEV      = 2 # U(ndef)
        ePT_BIDIR      = 3 # B(idirect)
        ePT_GND        = 4 # G(nd)
        ePT_POW        = 5 # P(ower)  

    # init of CAridPartType
    def __init__(self,parent_obj):
        super().__init__()
        self.tech = None  # ic-technology e.g. TTL
        self.familie = None # e.g. BUFFER # only a hash for searching
        self.num_text_lines = 0
        self.num_decals = 1 # min:one decal
        self.num_func = 0 # number of function min: func
        self.text = [] # text lines, part after header
        self.decals = [] # decals 
        self.func_main_gate = None  # M: MainGates Hauptgatter (Chip-Select?)
        self.func_gates = []        # G: Gatter, fÃ¼hrendes Main Gate Symbol entfÃ¤llt possible to have more than one   
        self.func_pin_con = None    # P: Pin-Info Stecker
        self.func_special = None    # S: Special Gatter
        self.func_drill = None      # H: Bohr/ Befestigung


    def pp(self):
        sout = 'Part-Type: ' + self.name + ' Text:' + str(self.text[0])
        return sout
    
    @staticmethod
    def pp_db():
        for obj in CAridPartType.db.values():
            print(obj.pp())
    
    def parse(self):
        try:
            tok,_line = CAridParserObj.tokenize_pop(self.lines)
            if  tok[0].find('@') != 0:
                CAridParserMain.logger.error('line is not a part header:' + str(tok))
                return None
            else:
                self.name = tok[0].replace('@','')
                self.tech = tok[1]
                self.familie = tok[2]
                self.num_text_lines = int(tok[3])
                self.num_decals = int(tok[4])
                self.num_func = int(tok[5])
            
            #body: text lines
            for i in range(0,self.num_text_lines):
                self.text.append(self.lines.pop(0))
            #decals
            self.decals,_line = CAridParserObj.tokenize_pop(self.lines,':')
                
            #pins and function
            self.parse_func_and_pin()
        except Exception as e:
            logging.error(e, exc_info=True)
            return None

        #print('p-part:' + str(tok))
        CAridPartType.db[self.name] = self
        #print (self.pp())
        return self
        
    def parse_func_and_pin(self):
        """
        if self.name=='CM4':
            print('DbgBrkCM41')
        """

        while (1):
            lst_tok,_line = CAridParserObj.tokenize_pop(self.lines)
            if lst_tok is None:
                break
            fst = lst_tok[0]
            type = CAridPartType.CPinFunction.parse_type(fst)
            if type != CAridPartType.CPinFunction.ePF_UNKNOWN:
                pf = CAridPartType.CPinFunction(self, type,_line)
                if type == CAridPartType.CPinFunction.ePF_GATE:
                    self.func_gates.append(pf) # can be more than one e.g. IC-CM4 !!!
                elif type == CAridPartType.CPinFunction.ePF_PIN:
                    self.func_pin_con = pf
                elif type == CAridPartType.CPinFunction.ePF_DRILL:
                    pass
                else:
                     raise Exception('Invalid PinFunction:' + str(type))  
                pf.parse_line(lst_tok)
                for i in range(0,pf.num_conn):
                    lst_tok,_line = CAridParserObj.tokenize_pop(self.lines,',')
                    pin = CAridPartType.CPin()
                    pin.parse_line(lst_tok)
                    pf.lst_pin.append(pin)
                
"""
  Parse a single sub-object like an text grafic-element, line, circel, text 
"""
class CAridParserObj:
    def __init__(self,parent_obj):  #  Parent-Object
        self.is_valid = False # object is valid, parser-validattion ok
        self.parser_state =  CAridParserObj.PARSER_STATE_INIT 
        self.lines = [] # config lines for this object

    
    """ @return TRUE if the string is an <OPTION> e.g. <S> <NOPIN>
    """
    @staticmethod
    def is_option(opt):
        if  len(opt) >=3:
            if opt[0] == '<' and opt[-1] == '>':
                return True
        return False

    # return a list with all argument of an object-head
    @staticmethod
    def tokenize_head(line_head):
        lst_tok=[]
        if line_head.find('@') == 0 and len(line_head) > 1:
            lst = line_head[1:].split(' ')
            for item in lst:
                if len(item)  > 0:
                    lst_tok.append(item)
        return lst_tok

    # return a tokenized list of strings > 0
    @staticmethod
    def tokenize(line,sep=' '):
        lst_tok=[]
        if len(line) > 0:
            lst = line.split(sep)
            for item in lst:
                if len(item)  > 0:
                    lst_tok.append(item)
        return lst_tok

    """
        @return a tokenized list of the first line in given lines
         - seperator is a space
         - skip empty elements, skip element with space
         - skip empty lines
         - pop the first line from lines list
         - return None if the line end reached
    """
    @staticmethod
    def tokenize_pop(lines,sep=' '):
        if len(lines) ==0:
            return (None, None)
        line = lines.pop(0)
        if len(line) == 0:
            return CAridParserObj.tokenize_pop(lines)

        lst_tok=[]
        lst = line.split(sep)
        for item in lst:
            if len(item) > 0:
                lst_tok.append(item)
        if len(lst_tok)==0:
            return CAridParserObj.tokenize_pop(lines)
        return (lst_tok,line)
    


    PARSER_STATE_INIT   = 0 # no valid stuff, try to find HEADER
    PARSER_STATE_HEADER = 1 # found valid header
    PARSER_STATE_BODY   = 2 # parse body stuff until END-MARK
    PARSER_STATE_FIN    = 3 # finished after this, check is_valid flag

""" Symbol Name e.g. NAME X Y ROT MIRROR TXT-HIGH TXT-WIDTH   NN 2 -2 0 N 2.5 0.25
    ariadne doc page 12-18
    NN: Part-Name e.g R210
    NT: Part-Type e.g. IC210
    N[1..3] Attribute
    TS: TextSizeDescription
    NP: Pin Number
"""
class CAridDrawName(CAridParserObj):
    
    def __init__(self, lst_tok):
        super().__init__(self)  #  Parent-Object    
        self.name = "" # NN:Part-Name (Prefix); NT: Part Type; N[1..3]:Attribute; TS:Text-Size Description; NP: PinNumber 
        self.x = None # position x [mm]
        self.y = None # position y [mm]
        self.rot = None # rotate deg e.g. 90
        self.mirror = False # N or M for Mirror
        self.high = None # Text-High [mm] option
        self.width = None # Line thickness [mm] option           
        self.parse_hdr(lst_tok)

    def parse_hdr(self,lst_tok):
        self.parser_state = CAridParserObj.PARSER_STATE_FIN
        try:
            self.name = lst_tok[0]
            self.x = float(lst_tok[1])
            self.y = float(lst_tok[2])
            if self.name == 'TS': # TextgrÃ¶Ãenbeschreibung in symbols
                self.high = float(lst_tok[1])
                self.width = float(lst_tok[2])
                self.is_valid = True
                return self
            self.rot = float(lst_tok[3])
            if lst_tok[4][0] == 'M':
                self.mirror = True
            if len(lst_tok) >= 6:
                self.high = float(lst_tok[5])
                if len(lst_tok) >= 7:
                    self.width = float(lst_tok[6])
        except Exception as e:
            logging.error(e, exc_info=True)
            return None
        self.is_valid = True
        return self
        

""" Symbol Text e.g. TXT X Y ROT MIRROR TXT-HIGH TXT-WIDTH :Text   TXT 2 -2 0 N 2.5 0.25 :FooText
    ariadne doc page 12-18  
"""
class CAridDrawText(CAridObjBase):
    def __init__(self, line):
        super().__init__()  #  Parent-Object    
        self.text = "" # text content
        self.rot = None # rotate deg e.g. 90
        self.mirror = False # N or M for Mirror
        self.high = None # Text-High [mm] option
        self.width = None # Line thickness [mm] option           

        if line is not None:
            self.parse_hdr(line)
            
    def set_text(self, txt):
        self.text = txt

    def list_to_string(self,org_list, seperator=' '):
        return seperator.join(org_list)

    def parse_hdr(self,line):
        #self.parser_state = CAridParserObj.PARSER_STATE_FIN
        try:
            lst_tok = CAridParserObj.tokenize(line)
            # lst_tok[0] is always 0
            if lst_tok[0] != 'TXT': 
                 raise Exception('is not TXT' + str(lst_tok[0]))    
            self.xy_set(lst_tok[1],lst_tok[2])
            self.rot = float(lst_tok[3])
            if lst_tok[4][0] == 'M':
                self.mirror = True
            self.high = float(lst_tok[5])
            self.width = float(lst_tok[6])
            if len(lst_tok) >7:
                tmp_tok=CAridParserObj.tokenize(line,':')
                self.set_text(tmp_tok[1])
                self.is_valid = True
            else:
                self.is_valid = False # txt is the next line
                # text is in the next line

        except Exception as e:
            logging.error(e, exc_info=True)
            return None
        
        return self

    def parse_second_line(self,lst_lines):
        lst_tok,line = CAridParserObj.tokenize_pop(lst_lines,':')
        self.set_text(lst_tok[0])
        self.is_valid = True
        return self

    def transform(self, x, y ,rot):
        self.x += x
        self.y += y   
        self.rot += rot
    
    def transform_mirrow(self):
        self.x = self.x * (-1)
        

""" Terminal/Pin description object
    ariadne doc page 12-19
    TNUM X Y X-TERM Y-TERM ROTATE Mirror   e.g.: T1  0 0 -1 1 0 N
"""
class CAridDrawTermDesc(CAridParserObj):
    def __init__(self, lst_tok):
        super().__init__(self)  #  Parent-Object    
        self.num = 0 # Terminal number, first valid 1
        self.x = None # position x [mm]
        self.y = None # position y [mm]
        self.x_ntxt = None # position of the terminal name-text [mm]
        self.y_ntxt = None # position of the terminal name-text [mm]
        self.rot = None # rotate deg e.g. 90
        self.mirror = False # N or M for Mirror
        self.high = None # Text-High [mm] option
        self.width = None # Line thickness [mm] option           
        self.parse_hdr(lst_tok)

    def parse_hdr(self,lst_tok):
        self.parser_state = CAridParserObj.PARSER_STATE_FIN
        try:
            lst_tok[0] = lst_tok[0].replace('T','')
            self.num = int(lst_tok[0])
            if self.num <=0:                   
                return None
            self.x = float(lst_tok[1])
            self.y = float(lst_tok[2])
            
            self.x_ntxt = float(lst_tok[3])
            self.y_ntxt = float(lst_tok[4])
            self.rot = float(lst_tok[5])
            if lst_tok[6][0] == 'M':
                self.mirror = True
        except Exception as e:
            logging.error(e, exc_info=True)    
            return None
        self.is_valid = True
        return self


""" outline symbol outline graph
ariadne doc page 12-20
FORM {LineArt} Art LineWidth  e.g.: T1  0 0 -1 1 0 N
e.g. CLOSED LINE 0.35 ....
    - FORM: OPEN|CLOSED|CIRCLE (CLOSED: means closed construction (first point is the same as the last point))
    - LineArt <DOT>|<DASH>|<DASHDOT> (!!!default is FULL!!!) , attention one element less in the line if LineArt is FULL
    - Art: LINE|FULL Line construction, full will be filled
    - LineWidth [mm]
    @todo arc
"""
class CAridDrawOutLine(CAridParserObj):
   
    class CAridDrawOutLineItem(CAridObjBase):
        def __init__(self, x ,y):      
            super().__init__()
            self.xy_set(x,y)
            self.r = None # exists if it is a circle or arc
            self.is_arc = False
            
        def CAridDrawOutLineItemfCircle(CAridDrawOutLineItem):
            def __init__(self,x_mid,y_mid,x_r,y_r):
                self.mid = CAridDrawOutLineItem(x_mid,y_mid)
                self.rad = CAridDrawOutLineItem(x_r,y_r)
                
        def CAridDrawOutLineItemArc(CAridDrawOutLineItem):
            def __init__(self,x_mid,y_mid,x_begin,y_begin,x_end,y_end):
                self.mid = CAridDrawOutLineItem(x_mid,y_mid)
                self.begin = CAridDrawOutLineItem(x_begin,y_begin)
                self.end = CAridDrawOutLineItem(x_end,y_end)
                    

    def __init__(self, lst_tok):       
        super().__init__(self)  #  Parent-Object    
        self.width = None # line width in [mm]
        self.form = CAridDrawOutLine.eFORM_INVALID
        self.line_art = CAridDrawOutLine.eART_LINE_FULL
        self.is_filled = False
        self.lst_item = [] # CAridDrawOutLine
        if lst_tok is not None:
            self.parse_hdr(lst_tok)

    def parse_hdr(self,lst_tok):
        try:
            if lst_tok[0] == 'CLOSED':
                self.form = CAridDrawOutLine.eFORM_CLOSED
            elif lst_tok[0] == 'OPEN':
                self.form = CAridDrawOutLine.eFORM_OPEN
            elif lst_tok[0] == 'CIRCLE':
                self.form = CAridDrawOutLine.eFORM_CIRCLE    
            else:
                raise Exception('unknown form' + str(lst_tok[0]))

            if CAridParserObj.is_option(lst_tok[1]) is True:
                str_line = lst_tok[2]
                str_width = lst_tok[3]
                if lst_tok[1] == '<DOT>':
                    self.line_art = CAridDrawOutLine.eART_LINE_DOT
                elif lst_tok[1] == '<DASH>':
                    self.line_art= CAridDrawOutLine.eART_LINE_DASH
                elif lst_tok[1] == '<DASHDOT>':
                    self.line_art = CAridDrawOutLine.eART_LINE_DASHDOT      
            else:
                str_line = lst_tok[1]
                str_width = lst_tok[2]
    
            if str_line == 'FULL':
                self.is_filled = True
            
            self.width = float(str_width)

        except Exception as e:
            logging.error(e, exc_info=True)
            self.parser_state = CAridParserObj.PARSER_STATE_FIN
            return None
        self.parser_state = CAridParserObj.PARSER_STATE_BODY
        return self

    def parser_body(self,lst_tok):
        #print('body:' + str(lst_tok)) 
        try:
            if lst_tok[0]=='END':
                self.parser_state = CAridParserObj.PARSER_STATE_FIN
                self.is_valid = True
                if self.form == 99:
                    print('error')
                return self
            it = CAridDrawOutLine.CAridDrawOutLineItem(lst_tok[0] ,lst_tok[1])
            self.lst_item.append(it)
            if len(self.lst_item) ==1 and self.form == CAridDrawOutLine.eFORM_CIRCLE:
                pass
            elif len(self.lst_item) ==2 and self.form == CAridDrawOutLine.eFORM_CIRCLE:
                #it.is_center = True
                x1=self.lst_item[0].x
                x2=it.x
                y1=self.lst_item[0].y
                y2=it.y
                it.r = math.sqrt((x1-x2) * (x1-x2) + (y1-y2) * (y1-y2)) / 2  
                it.x = x2-it.r
                it.y = y2
                self.lst_item.pop(0) 
                # circle with no END 
                self.is_valid = True 
                self.parser_state = CAridParserObj.PARSER_STATE_FIN 
            #elif len(lst_tok) > 2:  # @fixme
            #    pass
            elif lst_tok[-1] == 'ARC': # @todo:arc
                #logging.warning('todo arc')
                pass
            elif lst_tok[-1] == 'END':
                self.parser_state = CAridParserObj.PARSER_STATE_FIN
                self.is_valid = True
        except Exception as e:
            logging.error(e, exc_info=True)
            self.parser_state = CAridParserObj.PARSER_STATE_FIN
            return None

        return self

    def transform(self, x, y ,rot):
        for it in self.lst_item:
            it.x += x
            it.y += y
            it.rot = rot

    def transfrom_mirrow(self):
         for it in self.lst_item:
            it.x = it.x * (-1)

    eFORM_OPEN      =0  # open construction
    eFORM_CLOSED    =1  # closed construction first item == last item
    eFORM_CIRCLE    =2  # closed circle
    eFORM_INVALID   =99

    eART_LINE_FULL      =0 # default dot art ______
    eART_LINE_DOT       =1 # .....
    eART_LINE_DASH      =2 # ------
    eART_LINE_DASHDOT   =3 # .-..-.

"""
Ariadne DB Export Artikelnummer 

@0R0:MBB
REF:
LAGERNUMMER:93913290017
END

"""
class CAridDBArtNr(CAridObjBase):
    db = {} # store all tge artikel numbers key is part e.g 0R0:MBB

    def __init__(self,parent_obj):
        super().__init__()
        self.name = "" # part number
        self.ne_art_nr = "" # ~N~ artikel nummer

    def pp(self):
        sout = 'Part:' + self.name + ' = ' + str(self.ne_art_nr)
        return sout
    
    @staticmethod
    def pp_db():
        for obj in CAridDBArtNr.db.values():
            print(obj.pp())

    def parse(self):
        try:
            # parse head
            line = self.lines.pop(0)
            lst_tok= CAridParserObj.tokenize_head(line)
            if len(lst_tok) ==0:
                logging.error("CAridDBArtNr no valid header:" + line)
                return None
            name = str(lst_tok[0]) # elect. part is the only token in header
            # parse body
            while (1):
                lst_tok,_line = CAridParserObj.tokenize_pop(self.lines,':')
                if lst_tok is None:
                    break 
                
                fst = lst_tok[0]
                if fst == "LAGERNUMMER":
                    CAridDBArtNr.db[name] = lst_tok[1]
                elif fst == 'END':
                    break

        except IndexError:
            logging.warning("CAridDBArtNr header failed:" + line)
            pass   


"""
Sheet
*SHEET*
@S1 DINA2 6.416 -1.373036 -444.816065 -226.5 -605  # forget the tokens after DINAX, this are the last view/zoom of ariadne

*LINES*
@$NONAME  S1  60 165 0 N
OPEN LINE 0.35
 0 0
 100 0 END
END
...

*TEXT*
@$NONAME  S1  507.5 24.5 0 N
TXT  31 1.5 0 N 2.5 0.25 :8 Tasten
END
...

"""
class CAridSheet(CAridObjBase):
    
    db = {} # store all the sheet here,key is sheet number
    x_range_sheet = CAridObjBase.range_def[:]
    y_range_sheet = CAridObjBase.range_def[:]

    def __init__(self,parent_obj,sec):
        super().__init__()
        #CAridObjBase.xy_reset()
        self.sec_idx = sec
        self.form_din = "" # e.g. DINA2
        #self.null_point = (0,0) # null point X e.g. in [mm]
        self.name = ""
        self.num_sheet =0
        #self.rot =0
        self.mirrow = False
        self.lst_text = [] # CAridDwawText
        self.lst_outline = [] # CAridDrawLines


    def pp(self):
        sout = 'Sheet' + self.prefix + ':' +  self.name + ' OK:' + str(self.is_valid)
        return sout
    
    @staticmethod
    def pp_db():
        for obj in CAridSheet.db.values():
            print(obj.pp())


    def get_sheet(self,num_sheet):
        return CAridSheet.db.get(num_sheet)


    def parse_outline(self):
        try:
            # parse head
            line = self.lines.pop(0)
            lst_tok= CAridParserObj.tokenize_head(line)
            if len(lst_tok) ==0:
                logging.error("CAridSheet no valid header:" + line)
                return None

            noname = lst_tok[0] # looks like $noname
            self.num_sheet = int(lst_tok[1].replace('S',''))
            sheet = self.get_sheet(self.num_sheet)
            #txt = CAridDrawOutLine(None) # don't parse in __init__
            base_x = float(lst_tok[2])
            base_y = float(lst_tok[3])
            sheet.xy_set(lst_tok[2],lst_tok[3])
            base_rot = float(lst_tok[4])
            if (lst_tok[5]=='M'):
                base_mirror = True
            else:
                base_mirror = False
            while(1): 
                lst_tok, line = CAridParserObj.tokenize_pop(self.lines)
                if lst_tok is None:
                    break
                elif lst_tok[0] == "TXT":
                    obj_txt = CAridDrawText(line)
                    if obj_txt.is_valid is False:
                        obj_txt.parse_second_line(self.lines)
                    self.lst_text.append(obj_txt)
                elif lst_tok[0] == "END":
                    break
                else: 
                    obj_new = CAridDrawOutLine(lst_tok)
                    while len(self.lines) and obj_new.parser_state != CAridParserObj.PARSER_STATE_FIN:
                        lst_tok,_line = CAridParserObj.tokenize_pop(self.lines)
                        #print(str(lst_tok))
                        if lst_tok is None:
                            break
                        obj_new.parser_body(lst_tok)
                        if obj_new.is_valid:
                            if base_mirror is True:
                                obj_new.transform_mirrow()
                            obj_new.transform(base_x,base_y,base_rot)
                            sheet.lst_outline.append(obj_new)
            
            CAridObjBase.xy_append_range(CAridSheet.x_range_sheet,CAridSheet.y_range_sheet)
            #logging.warning("Sheet:" + str(sheet.num_sheet) + ' Range:' + CAridObjBase.xy_pp())
        except IndexError:
            logging.warning("CAridSheet header failed:" + line)
            pass   

    def parse_text(self):
        try:
            # parse head
            if len(self.lines)==0:
                return None
            line = self.lines.pop(0)
            lst_tok= CAridParserObj.tokenize_head(line)
            if len(lst_tok) ==0:
                logging.error("CAridSheet no valid header:" + line)
                return None

            noname = lst_tok[0] # looks like $noname
            self.num_sheet = int(lst_tok[1].replace('S',''))
            sheet = self.get_sheet(self.num_sheet)
            txt = CAridDrawText(None) # don't parse in __init__
            txt.xy_set(lst_tok[2],lst_tok[3])
            txt.rot = float(lst_tok[4])
            if (lst_tok[5]=='M'):
                txt.mirror = True
            while(1): 
                lst_tok,line = CAridParserObj.tokenize_pop(self.lines)
                if lst_tok is None:
                    break
                elif lst_tok[0] == "END":
                    break
                elif lst_tok[0] == "TXT":
                    #print('sheetline:' + line)
                    txt.x = txt.x + float(lst_tok[1])
                    txt.y = txt.y + float(lst_tok[2])
                    txt.rot = txt.rot + float(lst_tok[3])
                    if (lst_tok[5]=='M'):
                        txt.mirror = True
                    self.high = float(lst_tok[5])
                    txt.width = float(lst_tok[6])
                    if len(lst_tok) >7:
                        lst_tok = CAridParserObj.tokenize(line,':')
                        txt.text = lst_tok[1]  
                        txt.is_valid = True
                    else:
                        txt.parse_second_line(self.lines) 
                    if txt is None:
                        print('foo')
                    sheet.lst_text.append(txt)
                else:
                    raise Exception('more than one line ?' + str(line))
        
            CAridObjBase.xy_append_range(CAridSheet.x_range_sheet,CAridSheet.y_range_sheet)
 

        except Exception as e:
            logging.error(e, exc_info=True)
        except IndexError:
            logging.warning("CAridSheet header failed:" + line)
            pass   

    def parse(self):
        if self.sec_idx == CAridSec.eSEC_SHEET_TEXT:
            self.parse_text()
            return self
        elif self.sec_idx == CAridSec.eSEC_SHEET_LINES:
            self.parse_outline()
            return self
        try:
            # parse head
            line = self.lines.pop(0)
            lst_tok= CAridParserObj.tokenize_head(line)
            if len(lst_tok) ==0:
                logging.error("CAridSheet no valid header:" + line)
                return None

            self.num_sheet = int(lst_tok[0].replace('S',''))
            self.form_din = lst_tok[1]
            #self.x = float(lst_tok[2])
            #self.y = float(lst_tok[3])
            #self.form_offset_x = float(lst_tok[3]) # negative value
            #self.form_offset_y = float(lst_tok[4]) # negative value
            CAridSheet.db[self.num_sheet] = self
            #self.form_din = lst_tok[1] # e.g. dina2
        
        except IndexError:
            logging.warning("CAridSheet header failed:" + line)
            pass   

""" DIN Form
*SHEETFORM*
@DINA2  42.5 -598.5
OPEN LINE 0.25
 35.5 -1.5
 35.5 3.5 END
OPEN LINE 0.25
"""
class CAridSheetForm(CAridObjBase):
#class CAridSheetForm(CAridObjBase): don't use it because of xxy min/max calculation 
    db = {} # store all the forms here

    def __init__(self,main_parser):
        super().__init__()
        self.lines=[]
        self.lst_outline = [] # outline objects
        self.lst_text = [] # values: CSymbolTxt
        self.din_a_size = 2 # e.g. DINA2
        #self.null_point = (0,0) # null point X e.g. in [mm]
        self.format_x = None # din format +x [mm] (looks like cm)
        self.format_y = None # din format -y [mm] (negativ)
        self.name = "SheetForm"
        self.mparser = main_parser 

    def pp(self):
        sout = 'SheetForm:' + self.prefix + ':' +  self.name + ' OK:' + str(self.is_valid)
        return sout
    
    @staticmethod
    def pp_db():
        for obj in CAridSheetForm.db.values():
            print(obj.pp())

    def parse(self):
        try:
            # parse head
            line = self.lines.pop(0)
            lst_tok= CAridParserObj.tokenize_head(line)
            if len(lst_tok) ==0:
                logging.error("CAridSheetForm no valid header:" + line)
                return None

            self.din_a_size = lst_tok[0][-1] # e.g. dina2 is 2
            self.name = lst_tok[0] # dina2
            #self.null_point = (float(lst_tok[1]),float(lst_tok[2]))
            self.format_x = float(lst_tok[1])
            self.format_y = float(lst_tok[2])

            self.parse_body()
        except IndexError:
            logging.warning("CAridSheetForm header failed:" + line)
            pass   

    def parse_body(self):
        lst_tok = None
        while (1):
            lst_tok,line = CAridParserObj.tokenize_pop(self.lines)
            if lst_tok is None:
                break

            fst = lst_tok[0]
            if  fst == "TXT":
                obj_new = CAridDrawText(line)
                if obj_new.is_valid is True:
                    self.lst_text.append(obj_new)
                    #obj_new.transform(270,0,0)
                else:
                    self.lst_text.append(obj_new.parse_second_line(self.lines))
                    #obj_new.transform(270,0,0)

            elif (fst == 'OPEN' or fst == 'CLOSED' or fst == 'CIRCLE'):
                obj_new = CAridDrawOutLine(lst_tok)
                while len(self.lines) and obj_new.parser_state != CAridParserObj.PARSER_STATE_FIN:
                    lst_tok,_line = CAridParserObj.tokenize_pop(self.lines)
                    #print(str(lst_tok))
                    if lst_tok is None:
                        break
                    obj_new.parser_body(lst_tok)
                    if obj_new.is_valid:
                        self.lst_outline.append(obj_new)
                        #obj_new.transform(270,0,0)
            elif fst == "END": # end of symbol object 
                self.is_valid = True
                logger.info('Formsheet Range:' + CAridObjBase.xy_pp())
                #self.mparser.x_range_form = CAridObjBase.x_range[:]
                #self.mparser.y_range_form = CAridObjBase.y_range[:]
                CAridObjBase.xy_append_range(self.x_range,self.y_range)
                #print (self.pp())
            else:
                CAridParserMain.logger.warning('CAridSheedForm unhandled tokens:' + str(lst_tok))
        
        CAridSheetForm.db[self.name] = self
        return self


""" parse ariadne symbol ariadne doc page 12-15
    - started with line @NAME TERMS PREFIX <NOPINS> expample: @WID 2 R <NOPINS>
    - ended with line END
    - <NOPINS>: no pin numbers
"""
class CAridSymbol(CAridObjBase):

    db = {} # store all the symbols here key is the name A:TAS-LED-KATO

    def __init__(self,parent_obj):  #  headline to parse e.g  @WID 2 R <NOPINS>
        super().__init__()
        self.term_num = 0 # numbe of terminals(pins,connectors)
        self.prefix = "" # e.g. R is option for e.g. symbol
        self.opt = set() # e.g. <S> <HIDENAME> <NOPINS>
        self.dic_sym_name = {} # Keys :"NN","NT","N1","N2","N3","TS","NP" values: CSymbolNames
        self.lst_text = [] # values: CSymbolTxt
        self.dic_term_desc = {} # Keys :terminal/pin index (>0) value:CSymbolTermDes 
        self.lst_outline = [] # outline objects

    def pp(self):
        sout = 'Symbol Name:' + self.prefix + ':' +  self.name + ' OK:' + str(self.is_valid)
        return sout
    
    @staticmethod
    def pp_db():
        for obj in CAridSymbol.db.values():
            print(obj.pp())

    def parse(self):
        try:
            # parse head
            line = self.lines.pop(0)
            lst_tok= CAridParserObj.tokenize_head(line)
            if len(lst_tok) ==0:
                logging.error("CAridObjSymbol no valid header:" + line)
                return None

            self.name = lst_tok[0] # name
            self.term_num = int(lst_tok[1]) # terminal pins
            idx_opt=2 
            if CAridParserObj.is_option(lst_tok[2]) is False:
                self.prefix = lst_tok[2] # prefix e.g. 'R'
                idx_opt=3
            else:
                self.prefix = '<S>' # symbol only
            for i in range(idx_opt,len(lst_tok)):
                self.opt.add(lst_tok[i])

            # parse body
            self.parse_body()
        except IndexError:
            logging.warning("CAridObjSymbol failed:" + line)
            pass   
    
    def parse_body(self):
        lst_tok = None
        while (1):
            lst_tok,line = CAridParserObj.tokenize_pop(self.lines)
            if lst_tok is None:
                break

            fst = lst_tok[0]
            if fst == "NN" or fst == "NT" or fst == "N1" or fst == "N2" or fst == "N3" or fst == "TS" or fst == "NP":
                obj_new = CAridDrawName(lst_tok)
                if obj_new.is_valid:
                    self.dic_sym_name[fst] = obj_new
            elif  fst == "TXT":
                obj_new = CAridDrawText(line)
                if obj_new.is_valid is True:
                    self.lst_text.append(obj_new)
                else:
                    self.lst_text.append(obj_new.parse_second_line(self.lines))

            elif fst.find('T')==0:
                obj_new = CAridDrawTermDesc(lst_tok)
                if obj_new.is_valid:
                    self.dic_term_desc[obj_new.num] = obj_new  
            elif (fst == 'OPEN' or fst == 'CLOSED' or fst == 'CIRCLE'):
                obj_new = CAridDrawOutLine(lst_tok)
                while len(self.lines) and obj_new.parser_state != CAridParserObj.PARSER_STATE_FIN:
                    lst_tok,_line = CAridParserObj.tokenize_pop(self.lines)
                    #print(str(lst_tok))
                    if lst_tok is None:
                        break
                    obj_new.parser_body(lst_tok)
                    if obj_new.is_valid:
                        self.lst_outline.append(obj_new)
            elif fst == "END": # end of symbol object 
                self.is_valid = True
                CAridSymbol.db[self.name] = self
                #print (self.pp())
            else:
                CAridParserMain.logger.warning('unhandled tokens:' + str(lst_tok))
                
        return self

""" Signal item
"""
class CAridDrawSignalItem(CAridObjBase):
    def __init__(self,lst_item, x, y, symbol=None):      
        super().__init__()
        self.xy_set(x,y)
        self.symbol = symbol # can be also <TAG> or $Pfeil
        self.is_begin = False # is symobol at start of signal
        self.is_end = False  # is symbol at end of signal
        if symbol is not None:
            if len(lst_item):
                self.is_end = True

            elif len(lst_item) ==0:
                self.is_begin = True
        lst_item.append(self)    

""" Only on <TAG> per Signal 
    e.g. TAG <> 280.55 138.75 0 N 2.5 0.25
"""
class CAridDrawSignalItemTag:
    def __init__(self,x,y,rot,mirror,txt_size,txt_width):      
        self.x = float(x)
        self.y = float(y)
        self.rot = float(rot)
        self.mirror = False
        if mirror == 'M':
            self.mirrow = True
        self.txt_size = txt_size
        self.txt_width = txt_width


"""  Component, 
    e.g. combination between PartType and affected decal
    - looks line an one-liner
    @R1       10R:MINIMELF
    100R[5%]:SMD-0805,Wert_noch_unklar
    @X12      LOETSTIFT:LOETST-SMD,*
"""
class CAridComponent(CAridObjBase):

    db = {} # store all the components here key is the name e.g. R1,C1,IC1

    def __init__(self,parent_obj):  #  headline to parse e.g  @WID 2 R <NOPINS>
        super().__init__()
        self.part_type = None # CAridPartType object
        self.name_decal = ""
        self.name_decal_remark = "" # e.g. Wert_noch_unklar, or marker for '*'
        self.name_part_type = ""  # e.g.  100N[SMD] seperator '[' 
        self.name_part = ""  # e.g. 100N seperated from [SMD]  
        self.name_type = ""  # e.g. [SMD] or [5%]


    # component name eg D201, R210
    # but also A1-1 and A1-2 for e.g. CM4 Modul with two symbols, but with the same component A1
    @staticmethod
    def get_comp(comp_name): 
        comp_idx = 0
        tok = CAridParserObj.tokenize(comp_name,'-')
        comp = CAridComponent.db.get(tok[0], None)
        if len(tok) >1:
            comp_idx = int(tok[1])-1
        return (comp,comp_idx)

    # component name eg D201, R210
    # but also A1-1 and A1-2 for e.g. CM4 Modul with two symbols, but with the same component A1
    @staticmethod
    def get_terminal_name(comp_name, term_num):
        comp,comp_idx = CAridComponent.get_comp(comp_name)
        if comp is None:
            return None
        part_type = comp.part_type

        pin_func_num = comp_idx
        """
        if len(tok) > 1:
            pin_func_num = int(tok[1])-1  # .e.g A1-1 or A1-2  as comp-name for CM4
        """

        try:       
            pin_obj = part_type.func_gates[pin_func_num].lst_pin[term_num-1]
        except Exception as e:
            logging.error(e, exc_info=True)
            return None
        
        return pin_obj.name
    

    @staticmethod
    def get_ne_art_nr(comp_name):
        comp,comp_idx = CAridComponent.get_comp(comp_name)
        if comp is None:
            return None
        key =  comp.name_part_type + ':' + comp.name_decal
        ne_art_nr = CAridDBArtNr.db.get(key,None)
        return ne_art_nr

    # return the value of the component e.g 10k for resistor
    @staticmethod
    def get_value(comp_name,with_type=False):
        comp,comp_idx = CAridComponent.get_comp(comp_name)
        if comp is None:
            return None
        #print("NeArtNr:" + str(CAridComponent.get_ne_art_nr(comp_name)))    
        if with_type is True:
            return comp.name_part_type
        else:
            return comp.name_part

    def parse(self):
        try:
            lst_tok = None
            while (1):
                if len(self.lines) == 0:
                    return None 
                lst_tok = CAridParserObj.tokenize_head(self.lines.pop(0))
                if lst_tok is None:
                    break
                self.name = lst_tok[0]
                tok_tmp = CAridParserObj.tokenize(lst_tok[1],':')
                self.name_part_type = tok_tmp[0]
                self.part_type = CAridPartType.db[self.name_part_type]
                self.name_decal = tok_tmp[1]
                tok_tmp = CAridParserObj.tokenize(self.name_part_type,'[')
                self.name_part = tok_tmp[0]
                if len(tok_tmp) >1:
                    self.name_type = tok_tmp[1]    
                
                tok_decal = CAridParserObj.tokenize(self.name_decal,',') #   100R[5%]:SMD-0805,Wert_noch_unklar
                self.name_decal = tok_decal[0]
                if len(tok_decal) >1:
                    self.name_decal_remark = tok_decal[1]
                
                
                CAridComponent.db[self.name] = self
                self.is_valid = True
        except Exception as e:
            logging.error(e, exc_info=True)
            return None
        
        return self

    def pp(self):
        sout = 'Comp Name:' + self.name
        return sout
    
    @staticmethod
    def pp_db():
        for obj in CAridComponent.db.values():
            print(obj.pp())



"""  SymRef 
- Position ans symbol of the component on the sheet
@WID      S1  300 265 90 N 1 R204
  1)       2)  3)  4) 5) 6) 7) 8)
1) Symbol
2) Sheet-Number
3) x-Pos Sheet
4) y-Pos Sheet
5) Rotation
6) M(irro) or (N)ot 
7) ?
8) Name of the Component
Option:
NN 6 2 90 N 2.5 0.25   (Part-Name) CAridDrawName
NT 2 2 90 N 2.5 0.25   (Part-Type) CAridDrawName
N1 ... 
"""
class CAridSymRef(CAridObjBase):

    db = {} # store all the components here key is the name e.g. R1,C1,IC1

    def __init__(self,parent_obj):  #  headline to parse e.g  @WID 2 R <NOPINS>
        super().__init__()
        self.name = None # CAridComponent Name / Key e.g R10
        self.symbol_name = ""
        self.symbol_obj = None 
        self.num_sheet = 1 # default one
        #self.x = None
        #self.y = None
        self.rot = 0
        self.mirror = False
        self.draw_name = None
        self.draw_type = None


    def parse(self):
        try:
            lst_tok = None
            #print('len': + str(self.lines.len())) 
            while (1):
                #if len(self.lines) == 0:
                #    return None 
                lst_len = len(self.lines) 
                if lst_len == 0:
                    return None
                
                line = self.lines.pop(0)
                lst_tok = CAridParserObj.tokenize_head(line)
                if len(lst_tok) == 0:
                    lst_tok = CAridParserObj.tokenize(line)
                    if lst_tok[0] == "NN":
                        self.draw_name = CAridDrawName(lst_tok)
                    elif lst_tok[0] == "NT":
                        self.draw_type = CAridDrawName(lst_tok)
                    elif lst_tok[0] == "N1":
                        self.draw_type = CAridDrawName(lst_tok)
                    else:
                        raise Exception('CAridSymRef : Unknown Draw:' + str(lst_tok[0]))
                    continue
                        
                self.symbol_name = lst_tok[0]
                self.symbol_obj = CAridSymbol.db[self.symbol_name]
                self.num_sheet = int(lst_tok[1].replace('S','')) # e.g. S1
                self.xy_set(lst_tok[2],lst_tok[3])
                self.rot = float(lst_tok[4])
                if lst_tok[5]=='M':
                    self.mirror = True
                # lst_tok[6] ?
                self.name = lst_tok[7]
                CAridSymRef.db[self.name] = self
                self.is_valid = True
        except Exception as e:
            logging.error('Section SymRef')
            logging.error(e, exc_info=True)
            return None
        
        CAridSheet.xy_append_range(self.x_range,self.y_range)
        return self

    def pp(self):
        sout = 'Sym Name:' + self.name
        return sout
    
    @staticmethod
    def pp_db():
        for obj in CAridSymRef.db.values():
            print(obj.pp())



"""  SymSignal 

*SIGNAL* $3
@S1
150 265 R201.1
150 240 A201.K2

@S1
425 200 <JP>
475 200
475 226 A208.S2

@S1
350 47.5 <JP>
355 47.5 <S> $PFEIL   <-- This are 4 tok

*SIGNAL* T1_IN
@S1
267 140 D210.4
280 140 <TAG>
TAG <> 280.55 138.75 0 N 2.5 0.25

@S1
125 200 <JP>
175 200 <JP>

"""
class CAridSignal(CAridObjBase):

    db = {} # store all the components here key is the name of the section e.g. VCC, $3

    def __init__(self,parent_obj,sec_arg):  #  headline to parse e.g  @S1 it' only the Sheet No.
        super().__init__()
        self.name = None # Section argument of *SIGNAL*
        self.num_sheet = 1 # default one
        self.signal_name = sec_arg
        self.lst_sig_item = [] # CAridDrawSignalItem(CAridParserObj):
        self.x_dir_neg = None # for TAGing  TAG---> x_dir_neg = False ;   TAG<--- x_dir_neg = True
        self.y_dir_neg = None # same as x_dir_neg
        self.tag = None # e.g TAG <> 280.55 138.75 0 N 2.5 0.25
        self.signals = [] # list of CArdidSignal all signals in a list e.g. VCC got many signal on many sheets 
        self.lst_sheets = [] # list of all used sheeets for this signal


    def set_sheet(self,tok):
        self.num_sheet = int(tok.replace('S',''))

    def get_sheet_list(self,exclude_number=0):
        str_sort=""
        lst_set = set(self.lst_sheets)
        unique_list = sorted(list(lst_set))
        for s in unique_list:
            if int(s) != exclude_number: 
                str_sort += str(s) + ','
        
        if len(str_sort) >0 and str_sort[-1] == ',':
            str_sort=str_sort[0:-1]
        return str_sort

    def parse(self):
        try:
            lst_tok = None
            #print('len': + str(self.lines.len())) 
            while (1):
                #if len(self.lines) == 0:
                #    return None 
                lst_len = len(self.lines) 
                root_signal = CAridSignal.db.get(self.signal_name,None)
                if lst_len == 0:
                    self.is_valid = True
                   
                    if root_signal is None:
                        CAridSignal.db[self.signal_name] = self
                        root_signal = self     
                    root_signal.signals.append(self)
                    
                    """
                    if self.signal_name == "LX7":
                        print('Signal:' + self.signal_name + ' sheet:'+ str(self.num_sheet))
                    """
                    #print(root_signal.get_sheet_list())
                 
                    if len(self.lst_sig_item) >0:
                        if (self.lst_sig_item[-2].y == self.lst_sig_item[-1].y):
                            if (self.lst_sig_item[-2].x > self.lst_sig_item[-1].x):
                                self.x_dir_neg = True
                            else:
                                self.x_dir_neg = False
                        if (self.lst_sig_item[-2].x == self.lst_sig_item[-1].x):
                            if (self.lst_sig_item[-2].y > self.lst_sig_item[-1].y):
                                self.y_dir_neg = True
                            else:
                                self.y_dir_neg = False

                    CAridObjBase.xy_append_range(CAridSheet.x_range_sheet,CAridSheet.y_range_sheet)
                    return self


                line = self.lines.pop(0)
                lst_tok = CAridParserObj.tokenize_head(line)
                if len(lst_tok) != 0:
                    self.set_sheet(lst_tok[0])
                    continue
                else:
                    lst_tok = CAridParserObj.tokenize(line)
                    if lst_tok[0] == "TAG":
                        self.tag = CAridDrawSignalItemTag(lst_tok[2],lst_tok[3],lst_tok[4],lst_tok[5],lst_tok[6],lst_tok[7])
                        continue
                    self.xy_set(lst_tok[0],lst_tok[1])
                    if len(lst_tok) == 4 and lst_tok[2]=='<S>': # looks like <S> $Pfeil
                        item = CAridDrawSignalItem(self.lst_sig_item,lst_tok[0],lst_tok[1],lst_tok[3])
                    elif len(lst_tok) == 3:
                        item = CAridDrawSignalItem(self.lst_sig_item,lst_tok[0],lst_tok[1],lst_tok[2])
                        # @todo check pin-symbol in DB
                    elif len(lst_tok) == 2:
                        item = CAridDrawSignalItem(self.lst_sig_item,lst_tok[0],lst_tok[1])
                    #self.lst_sig_item.append(item)

        except Exception as e:
            logging.error('Section Signal line' + str(lst_tok))
            logging.error(e, exc_info=True)
            return None

        return self

    def pp(self):
        sout = 'Signal Name:' + self.signal_name
        return sout
    
    @staticmethod
    def pp_db():
        for obj in CAridSignal.db.values():
            print(obj.pp())

    @staticmethod
    def sheetlist_create():
        for sig_root in CAridSignal.db.values():
            for sig in sig_root.signals:
                sig_root.lst_sheets.append(sig.num_sheet)
            




"""
  Parse a whole ariadne file
   - Parse each section , started with *SECTIONNAME* in ariadne file
"""
class CAridParserMain:
    
    logger = None
    
    def __init__(self,logger):
        self.fname = None  # fule name to parse 
        CAridParserMain.logger = logger
        self.lines = [] # striped(\n) lines
        #self.x_range_form = None
        #self.y_range_form = None

    """ load a additional exported ariadne db-file.
        file-ending: *.asc
    """
    def load_ari_file(self, fname):
        self.lines.clear()
        logging.info("Try to load file:" + fname)
        try: # latin1 
            with open(fname, 'r',encoding="iso-8859-1") as fin:
                for line in fin:
                    line = line.strip('\n')
                    #print(line)
                    self.lines.append(line)
        except Exception as e:
            logging.error(e, exc_info=True)
            exit(1)


    """ valid file-names:
      - *.sca Ariadne schematic file
    """
    def parse(self,sec_start):
        lines = self.lines
        sec_actual = sec_start
        if sec_actual is None:
            sec_actual = CAridSec.eSEC_NONE

        line_num = 0
       
        def try_obj_parse(obj):
            if obj is not None:
                lst_len = len(obj.lines)
                if lst_len > 0:
                    obj.parse()
                    obj.lines.clear()
                #last_obj = None # not working

        #self.load_ari_file(fname)
        
        # parse all lines
        
        sec_arg = None # e.g. *SIGNAL* VCC
        last_obj = None
        for line in self.lines:
            if len(line) == 0:
                line_num +=1
                continue
            
            check_new_sec, new_sec_arg = CAridSec.get_sec_idx_and_arg(line)
            check_new_sec = CAridSec.check_sec_type(line)
            if check_new_sec is not CAridSec.eSEC_NONE:
                if (sec_actual is not check_new_sec) or (new_sec_arg is not sec_arg):
                    sec_actual = check_new_sec
                    sec_arg = new_sec_arg

                    if last_obj is not None: 
                        try_obj_parse(last_obj)
                        last_obj = None # not working
                    if sec_actual == CAridSec.eSEC_SHEETFORM:
                        CAridObjBase.xy_reset()
                    if sec_actual == CAridSec.eSEC_SHEET:
                        CAridObjBase.xy_reset()
                    if sec_actual == CAridSec.eSEC_DRAWING:
                        CAridObjBase.xy_reset()    
                    continue

            if line.find('@') == 0:
                if (last_obj is not None) and (len(last_obj.lines) > 0):
                    try_obj_parse(last_obj)
                    last_obj = None
                if sec_actual == CAridSec.eSEC_SYMBOL:
                    last_obj = CAridSymbol(self)
                elif sec_actual == CAridSec.eSEC_COMPONENT:
                    last_obj = CAridComponent(self)
                elif sec_actual == CAridSec.eSEC_PARTTYPE:
                    last_obj = CAridPartType(self)
                elif sec_actual == CAridSec.eSEC_SYMREF:
                    last_obj = CAridSymRef(self)    
                elif sec_actual == CAridSec.eSEC_SIGNAL:
                    last_obj = CAridSignal(self,sec_arg)
                elif sec_actual == CAridSec.eSEC_SHEETFORM:
                    last_obj = CAridSheetForm(self)
                elif sec_actual == CAridSec.eSEC_SHEET:
                    last_obj = CAridSheet(self,sec_actual)
                elif sec_actual == CAridSec.eSEC_SHEET_LINES:
                    last_obj = CAridSheet(self,sec_actual)
                elif sec_actual == CAridSec.eSEC_SHEET_TEXT:
                    last_obj = CAridSheet(self,sec_actual)    
                elif sec_actual == CAridSec.eSEC_DB_ART:
                    last_obj = CAridDBArtNr(self) 
                else:
                    #logger.info('skip obj:' + line)
                    #last_obj = None
                    continue
                last_obj.lines.append(line)                   
            
            elif last_obj is not None:
                last_obj.lines.append(line)
                 
        #CAridSymbol.pp_db()
        #CAridPartType.pp_db()
        #CAridComponent.pp_db()
        #CAridSymRef.pp_db()
        #CAridSignal.pp_db()
        logging.info('parsed lines:' + str(line_num))
        return line_num
#EOF
