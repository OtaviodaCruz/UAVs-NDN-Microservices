import matplotlib.pyplot as plt 
import numpy as np 

dataset = open("client-i-10-comcs.txt", 'r')

rttList = []
for line in dataset:
    line = line.strip()
    rtts, empty = line.split(';')
    rttList.append(float(rtts))

dataset.close()

count = 1
sumrtt = 0
rttFinal = []
quantidade = 20
for value in rttList:
    sumrtt = sumrtt + value
    if count == quantidade:
        rttFinal.append(sumrtt/quantidade)
        count = 1
        sumrtt = 0
    else:
        count = count + 1

# create 
x = list(range(len(rttFinal)))
#plt.plot(x, rttFinal)  

plt.rc('pdf',fonttype = 42)
plt.bar(x, rttFinal)

#plt.xticks(np.arange(min(x), max(x)+1, 1.0))  # Set label locations.
plt.xlabel('Communications occurred')
plt.ylabel('RTT (ms)')
#plt.legend()

plt.show() 
