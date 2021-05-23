# -*- coding: utf-8 -*-
"""
Created on Sat May 22 13:23:34 2021

@author: plinio silva
"""

import socket
import time
import sys


TCP_IP = '127.0.0.1'
TCP_PORT = 8002
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


f = open(r"Anemômetro_Young.txt")
buff = f.readlines()
f.close()

i=0
while True:
    i += 1  
    if i >= len(buff):
        i = 0
    temp = buff[i]
    print(temp)
    temp = temp.encode('ascii')        
    s.send(temp)  # echo
    time.sleep(1)