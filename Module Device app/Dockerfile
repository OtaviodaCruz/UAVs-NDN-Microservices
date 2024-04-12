FROM ubuntu:bionic
COPY device_app /device

RUN apt-get update && apt-get -y install python3 python3-pip nano git && pip3 install Twisted klein simplejson

