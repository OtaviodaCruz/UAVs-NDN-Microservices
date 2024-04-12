FROM ndn_microservice/base:latest
COPY NR_ST /NR_ST
RUN cd /NR_ST && cmake . && make -j2 && mv bin/NR / && cd /
