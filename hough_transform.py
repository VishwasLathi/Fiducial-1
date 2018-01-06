#!/usr/bin/env python2

from scipy.ndimage.filters import gaussian_filter1d, gaussian_filter
import numpy as np
import cv2
from matplotlib import pyplot as plt

path=''
img=cv2.imread(path)
img = gaussian_filter(img,2)
#cimg = cv2.cvtColor(img,cv2.COLOR_GRAY2BGR)

circles = cv2.HoughCircles(img,cv2.HOUGH_GRADIENT,1,5,
                            param1=50,param2=25,minRadius=0,maxRadius=80)

circles = np.uint16(np.around(circles))
#(i[0],i[1]) is the center of the circle and i[2] is the radius of the circle
print circles
for i in circles[0,:]:
    # draw the outer circle
       cv2.circle(img,(i[0],i[1]),i[2],(0,255,0),2)
     #draw the center of the circle
       cv2.circle(img,(i[0],i[1]),2,(0,0,255),2)

cv2.imshow('detected circles',img)
cv2.waitKey(0)
cv2.destroyAllWindows()