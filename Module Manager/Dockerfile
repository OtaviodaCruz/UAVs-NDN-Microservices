FROM ubuntu:bionic

COPY manager-app1/ manager

RUN apt-get update && apt-get -y install python3 python3-pip nano git && pip3 install kubernetes networkx Twisted klein simplejson

#acho que não precisa
EXPOSE 8080 

# networkx-2.5.1
# Twisted-22.4.0
# klein-21.8.0
# python 3.6.9

