# -*- coding: utf-8 -*-
"""
Created on Sat May 22 11:48:33 2021

@author: plinio silva
"""


import socket
import time
import serial
import pynmea2
import re
import sys
import gc
import datetime
# from metpy import calc
from metpy.calc import wind_speed,wind_direction,wind_components
from metpy.units import units
import numpy as np

gc.collect()

import json

try:
    with open('sailing-anemometerLogger-config.txt') as f:
        temp = f.read()
        config = json.loads(temp)
except Exception as e:
    print(e)
    print("Nao foi possivel abrir arquivo de configuração. Criando modelo novo.")
    config = dict(
                legSER = "comport e baudrate se referem a porta serial do anemometro",
                comport = "COM30",
                baudrate = 19200,
                legTCP = "TCP_IP e TCP_PORT se referem ao endereco de IP do PC da navegacao e a porta aberta no Hypack Shared Memory",
                TCP_IP = "127.0.0.1",
                TCP_PORT = 8001,
                )
    temp = json.dumps(config,indent = 4)
    with open('sailing-anemometerLogger-config.txt','w') as f:
        f.write(temp)
        f.close()


comport = config["comport"]
baudrate = config["baudrate"]
TCP_IP = config["TCP_IP"]
TCP_PORT = config["TCP_PORT"]

if "ser" in globals() or "ser" in locals():
    print("fechando a porta serial aberta previamente")
    ser.close()

#configuracao de portas
# comport = "COM30" #porta serial de recepcao da string do anemometro-emet, entre "aspas"
# baudrate = 19200 #baudrate do anemometro / emet
# se o log for feito na mesma maquina da navegacao, o tcpIP pode ser 127.0.0.1
# TCP_IP = "127.0.0.1" #numero do IP da maquina da navegacao. entre "aspas"
# TCP_PORT = 8001 #numero da porta aberta no shared memory do hypack

#Exemplo da configuracao:
#comport = "COM30" #porta serial de recepcao da string do anemometro-emet, entre "aspas"
#baudrat = 19200 #baudrate do anemometro / emet
# se o log for feito na mesma maquina da navegacao, o tcpIP pode ser 127.0.0.1
#TCP_IP = "127.0.0.1" #numero do IP da maquina da navegacao. entre "aspas"
#TCP_PORT = 8001 #numero da porta aberta no shared memory do hypack

temp = """
Esse programa ira gravar em um arquivo os dados medidos anemometro ja com a correcao 
da velocidade.  
Para tal funcionar, ele precisa de uma string GPRMC que pode ser feita pelo
MemoryShare do Hypack.
A unidade de entrada da velocidade e direcao de vento nesse programa deve estar em
NOS e GRAUS.
O arquivo gravado terah no nome a data da primeira string de GPS recebida.
Na parte de cima do arquivo sera gravado um header
O arquivo sera atualizado com todas as strings que chegarem a cada 60 segundos
A string da estacao meteorologica deve ser desse formato, uma linha por vez:
03.1 219 
02.9 219 
03.2 224 
velocidade direcao separados por um espaço.
------
O header do arquivo formatado é:
wspdT,wdirT,wspd,wdir,boatspd,boatdir,lat,lon,gpstime 

wspdT = velocidade corrigida 
wdirT = direcao corrigida com relacao ao norte verdadeiro (de onde vem)
wspd = velocidade medida
wdir = direcao medida sem correcao de heading (de onde vem)
boatspd = velocidade do navio calculada pelo Hypack ou equivalente
boatdir = heading do navio norte verdadeiro (para onde vai)
lat = latitude no ponto de aquisicao
lon = longitude no ponto de aquisicao
gpstime = horario retirado da string de GPS GPRMC 
"""

print(temp)
time.sleep(3)

header = "wspdT,wdirT,wspd,wdir,boatspd,boatdir,lat,lon,gpstime\n"
#%%
def spdir2uv(spd, ang, deg=False):
    """
    Computes u, v components from speed and direction.
    Parameters
    ----------
    spd : array_like
          speed [m s :sup:`-1`]
    ang : array_like
          direction [deg]
    deg : bool
          option, True if data is in degrees. Default is False
    Returns
    -------
    u : array_like
        zonal wind velocity [m s :sup:`-1`]
    v : array_like
        meridional wind velocity [m s :sup:`-1`]
    """

    if deg:
        ang = np.deg2rad(ang)

    # Calculate U (E-W) and V (N-S) components
    u = spd * np.sin(ang)
    v = spd * np.cos(ang)
    return u, v


# In[4]:


def uv2spdir(u, v, mag=0, rot=0):
    """
    Computes speed and direction from u, v components.
    Converts rectangular to polar coordinate, geographic convention
    Allows for rotation and magnetic declination correction.
 
    Parameters
    ----------
    u : array_like
        zonal wind velocity [m s :sup:`-1`]
    v : array_like
        meridional wind velocity [m s :sup:`-1`]
    mag : float, array_like, optional
          Magnetic correction [deg]
    rot : float, array_like
          Angle for rotation [deg]
 
    Returns
    -------
    ang : array_like
          direction [deg]
    spd : array_like
          speed [m s :sup:`-1`]
 
    Notes
    -----
    Zero degrees is north.
 
    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> from oceans.ocfis import uv2spdir
    >>> u = [+0, -0.5, -0.50, +0.90]
    >>> v = [+1, +0.5, -0.45, -0.85]
    >>> wd, ws = uv2spdir(u,v)
    >>> fig, ax = plt.subplots(subplot_kw=dict(polar=True))
    >>> kw = dict(arrowstyle="->")
    >>> wd = np.deg2rad(wd)
    >>> lines = [ax.annotate("", xy=(d, s), xytext=(0, 0), arrowprops=kw)
    ...  for d, s in zip(wd, ws)]
    >>> _ = ax.set_ylim(0, np.max(ws))
 
    """
 
    u, v, mag, rot = list(map(np.asarray, (u, v, mag, rot)))
 
    vec = u + 1j * v
    spd = np.abs(vec)
    ang = np.angle(vec, deg=True)
    ang = ang - mag + rot
    ang = np.mod(90. - ang, 360.)  # Zero is North.
 
    return ang, spd



#%%#Abrindo a porta TCP para captura de string nmea
TCP_IP = TCP_IP
TCP_PORT = TCP_PORT
BUFFER_SIZE = 1024
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect((TCP_IP, TCP_PORT))
except Exception as e:
    print(e)
    print("Nao foi possivel conectar a porta TCP em %s na porta %d"%(TCP_IP,TCP_PORT))
    print("Verifique e tente novamente")
    s.close()
    sys.exit(10)

#%%Abrindo a porta Serial para captura da string da estacao meteorologica / anemometro

try:
    ser = serial.Serial(comport, baudrate, timeout=2)
except Exception as e:
    print(e)
    print("A porta serial nao pode ser aberta. Tentando novamente")
    sys.exit(11)
    

#%%
rect = time.time()
buff = ""
buff2 = ""
ti = time.time()
emet_filename = ""
while True:
    ###Le a string da porta TCP / GPS
    try:
        gpsdata = s.recv(BUFFER_SIZE).decode()
        
        if gpsdata:
            # print("gpsdata",gpsdata)
            pass
    except Exception as e:
        print("Sem dados de GPS",e)
    
    ####Le a string da porta Serial / EMET
    emetdata = ""
    t1 = time.time() + 5 #5 segundos antes de avisar que nao esta chegando emetdata
    while emetdata == '':
        emetdata = ser.read_all().decode().split('\n')   # read a '\n' terminated line
        emetdata = ''.join(emetdata)
        if emetdata == "":
            time.sleep(.5)
            if time.time() > t1:
                temp = time.time() - ti
                print("esperando por emetdata... %s %.0f"%(emetdata,temp))
                
    try:
        wspd,wdir = re.findall('([0-9.]+) ([0-9.]+)',emetdata)[-1]
        wspd = float(wspd)
        wdir = float(wdir)
    except:
        pass
    
    #lendo a string nmea e extraindo informacoes de velocidade e direcao
    if gpsdata:
        rmc = ''
        gga = ''
        hdt = ''
        try:
            rmc = re.findall("GPRMC.*",gpsdata)[-1]
            rmc = pynmea2.parse(rmc)
            gpstime = datetime.datetime.combine(rmc.datestamp,rmc.timestamp)
            boatspd = rmc.spd_over_grnd #em knots
            boathdt = rmc.true_course #norte verdadeiro
        except:
            print("nao foi encontrada string GPRMC")
            print("...calculando velocidade e heading com string GGA")
            pass
        #se nao foi possivel achar a rmc, tentar calcular boatspeed e boatheading com GGA e HDT
        if not rmc:
            try:
                gga = re.findall("GPGGA.*",gpsdata)[-1]
                gga = pynmea2.parse(gga)
            except:
                print('nao foi encontrada string GGA')
                sys.exit(12)
                pass
            try:
                hdt = re.findall("GPHDT.*",gpsdata)[-1]
                hdt = pynmea2.parse(gga)
            except:
                print('nao foi encontrada string HDT')
                sys.exit(13)
                pass
            pass
    
        #calculando a resultante        
        wu,wv = wind_components(wspd * units('knots'), wdir * units.degree)
        
        #o vetor do barco e do vento tem direcoes contrarias, por causa da convecao de onde o vento vem,
        #mas o vetor do barco nao precisa ser girado pois essa funcao ja calcula o vetor invertido.
        boatu,boatv = wind_components(boatspd * units('knots'), boathdt * units.degree)
        
        #velocidade medida = velocidade barco + velocidade real
        #velocidade real = velocidade medida - velocidade barco.
        wTu = wu - boatu
        wTv = wv - boatv
        
        wspdT = float(wind_speed(wTu,wTv).magnitude)
        wdirT = float(wind_direction(wTu,wTv).magnitude)
        
        lat = rmc.lat + ' ' + rmc.lat_dir
        lon = rmc.lon + ' ' + rmc.lon_dir        
        
        buff2 = "wspdT=%.2f wdirT=%.2f"%(wspdT,wdirT) 
        buff2 += " wspd=%.2f wdir=%.2f"%(wspd,wdir)
        buff2 += " boatspd=%.2f boatdir=%.2f"%(boatspd,boathdt)
        buff2 += " lat=%s lon=%s"%(lat,lon)
        buff2 += " gpstime=%s \n"%(gpstime)
        print(buff2)
        
        buff += "%.2f,%.2f,"%(wspdT,wdirT) 
        buff += "%.2f,%.2f,"%(wspd,wdir)
        buff += "%.2f,%.2f,"%(boatspd,boathdt)
        buff += "%s,%s,"%(lat,lon)
        buff += "%s\n"%(gpstime)
        
        
        t = time.time()
        if t > rect:
            rect = time.time() + 60
            if emet_filename == "":
                emet_filename = gpstime.strftime("%Y-%m-%dT%H%M%S")
                emet_filename = "young %s.txt"%emet_filename
            
            with open(emet_filename,'a') as f:
                if header:
                    f.write(header)
                    header = ""
                f.write(buff)
            buff = ""

#%%

