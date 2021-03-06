from __future__ import print_function
from scipy.ndimage.filters import gaussian_filter1d, gaussian_filter
import numpy as np
import cv2
from matplotlib import pyplot as plt
import argparse
from sklearn.cluster import KMeans
from random import randint
import dicom

# Import DICOM file as numpy array
def import_dicom(path, max_threshold=255, image_threshold=0.1,
                 scale_grays=125):
    if scale_grays > 255 or scale_grays < 0:
        raise ValueError("scale_grays must be between 0 and 255")

    raw_image = dicom.read_file(path).pixel_array
    raw_image = np.where(raw_image < 0, np.zeros(raw_image.shape), raw_image)

    if raw_image.max() > max_threshold:
        threshold = image_threshold * raw_image.max()
        if threshold > 255:
            scaled = np.where(raw_image >= 255, np.ones(raw_image.shape) * 255,
                              (raw_image / threshold) * scale_grays)
        elif threshold > scale_grays:
            scaled = np.where(raw_image >= threshold,
                              np.ones(raw_image.shape) * 255,
                              (raw_image / threshold) * scale_grays)
        else:
            scaled = np.where(raw_image >= threshold,
                              np.ones(raw_image.shape) * 255, raw_image)
    else:
        scaled = np.zeros(raw_image.shape)
    return scaled.astype(np.uint8)

# Display grayscale image
def display(image, title=None):
    plt.figure()
    if title is not None:
        plt.title(title)
    plt.imshow(image, cmap='gray', vmin=0, vmax=255)
    plt.show(block=False)

# Contrast Limited Adaptive Histogram Equalization
def clahe_img(image, clipLimit=2.0, tileGridSize=(8, 8), verbose=False):
    improved = cv2.createCLAHE(clipLimit=clipLimit,
                               tileGridSize=tileGridSize).apply(image)
    if verbose:
        display(improved, 'After CLAHE')
    return improved.astype(np.uint8)

# Smoothened Image Histogram
def img_hist(image, hist_filter_sigma=2):
    hist = cv2.calcHist([image], [0], None, [256], [0, 256])
    hist = np.reshape(hist, (len(hist)))
    return gaussian_filter1d(hist, hist_filter_sigma)

# Returns "1st" local minima of a function
def func_minima(func):
    for i in range(len(func)):
        if i > 0 and i < (len(func) -1) and func[i] <= func[i - 1] and\
        func[i] <= func[i + 1]:
            return i

# Second-derivative of Ratio Curve of Image Histogram: Normalized Rate Curve
def norm_rate_curve(hist, filter_sigma=2, verbose=False):
    summation = hist * range(1, 1 + len(hist))
    ratio = [np.sum(summation[:i]) / np.sum(summation[(i + 1):]) for i in\
            range(len(summation) - 1)]
    x = np.arange(len(ratio))
    if verbose:
        plt.title('Ratio Curve')
        plt.plot(x, ratio)
        plt.show()

    y_first = np.diff(ratio) / np.diff(x)
    x_first = 0.5 * (x[:-1] + x[1:])
    y_second = np.diff(y_first) / np.diff(x_first)
    second_der = gaussian_filter1d(y_second, filter_sigma)
    if verbose:
        x_second = 0.5 * (x_first[:-1] + x_first[1:])
        plt.title('Normalized Rate Curve')
        plt.plot(x_second, second_der)
        plt.show()
    return second_der

# Thresholding of image from 1st minima of histogram
# NOTE: This only works if background is noticeably darker than the brain
def thresh_hist(image, thresh_filter_sigma=2.7, clahe=True, verbose=False,
                **kwargs):
    if clahe:
        image = clahe_img(image, verbose=verbose)
    hist = img_hist(image, **kwargs)
    threshold = func_minima(hist)
    new_img = np.where(image>=threshold, 255 * np.ones(image.shape),
                       np.zeros(image.shape))
    new_img = gaussian_filter(new_img, thresh_filter_sigma)
    thresh_img = ((new_img.astype(np.float32) / new_img.max()) * 255).astype(
                 np.uint8)

    if verbose:
        plt.figure()
        plt.title('Image Histogram')
        plt.plot(np.arange(len(hist)), hist)
        plt.plot(threshold, hist[threshold], 'rx')
        plt.show(block=False)

        display(thresh_img, 'Thresholded Image')

    return thresh_img

# Adaptive gaussian thresholding
def thresh_adaptive(image, binarize='mean', blocksize=17, thresh_C=6.5,
                    thresh_filter_sigma=1, clahe=True, verbose=False):
    if clahe:
        image = clahe_img(image, verbose=verbose)

    if binarize == 'mean':
        method = cv2.ADAPTIVE_THRESH_MEAN_C
    elif binarize == 'gaussian':
        method = cv2.ADAPTIVE_THRESH_GAUSSIAN_C
    else:
        raise ValueError('Invalid option for binarization')

    raw_thresh = cv2.adaptiveThreshold(image, 255, method,
                                       cv2.THRESH_BINARY, blocksize, thresh_C)
    smooth_thresh = gaussian_filter(raw_thresh, thresh_filter_sigma)
    thresh_img = ((smooth_thresh.astype(np.float32) / smooth_thresh.max()) *\
                  255).astype(np.uint8)

    if verbose:
        display(thresh_img, 'Thresholded Image')

    return thresh_img

# Thresholding with Otsu's Binarization
def thresh_otsu(image, thresh_filter_sigma=2, clahe=True, verbose=False):
    if clahe:
        image = clahe_img(image, verbose=verbose)
    _, raw_thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY +\
                                  cv2.THRESH_OTSU)
    smooth_thresh = gaussian_filter(raw_thresh, thresh_filter_sigma)
    thresh_img = ((smooth_thresh.astype(np.float32) / smooth_thresh.max()) *\
                  255).astype(np.uint8)

    if verbose:
        display(thresh_img, 'Thresholded Image')

    return thresh_img

# Canny-Edge detection
def canny_edge(image, edge_filter_sigma=4, binarize='histogram', verbose=False,
               **kwargs):
    if binarize == 'histogram':
        image = thresh_hist(image, verbose=verbose, **kwargs)
    elif binarize in ('gaussian', 'mean'):
        image = thresh_adaptive(image, binarize=binarize, verbose=verbose,
                                **kwargs)
    elif binarize == 'otsu':
        image = thresh_otsu(image, **kwargs)
    elif binarize is not None and not (type(binarize) == str and\
    binarize.lower() == 'none'):
        raise ValueError('Invalid option for binarization')

    edges = cv2.Canny(image, 100, 200)
    edges = gaussian_filter(edges, edge_filter_sigma)
    edges = ((edges.astype(np.float32) / edges.max()) * 255).astype(np.uint8)

    if verbose:
        display(edges, 'Image Edges')

    return edges

 
#laplacian edge detection
def laplacian(image,verbose=False,edge_filter_sigma=4,**kwargs):
    image = thresh_hist(image, verbose=verbose, **kwargs)
    edges= cv2.Laplacian(image,cv2.CV_64F)
    edges = gaussian_filter(edges, edge_filter_sigma)
    edges = ((edges.astype(np.float32) / edges.max()) * 255).astype(np.uint8)
    

    if verbose:
        display(edges, 'Image Edges')

    return edges
  
#Sobel filter edge detection
def sobel(image,verbose=False,**kwargs):
    image=thresh_hist(image,verbose=verbose,**kwargs)
    sobel64f = cv2.Sobel(img,cv2.CV_64F,1,1,ksize=5)
    abs_sobel64f = np.absolute(sobel64f)
    sobel_8u_M = np.uint8(abs_sobel64f)
    sobel_8u=gaussian_filter(sobel_8u_M,2)
    sobel_final=sobel_8u
    sobel_final=((sobel_final.astype(np.float32) / sobel_final.max()) * 255).astype(np.uint8)
    if verbose:
       display(sobel_final,'sobel_edges')
   
    
# Longest-edge from contours in image
def longest_edge(image, canny=False, outline_filter_sigma=2, verbose=False,
                 **kwargs):
    if canny:
        image = canny_edge(image, verbose=verbose, **kwargs)
    else:  
        image=laplacian(image,verbose=verbose,**kwargs)

    image, contours, hierarchy = cv2.findContours(image, cv2.RETR_EXTERNAL,
                                                  cv2.CHAIN_APPROX_SIMPLE)
    max_len = 0
    outline = None
    for contour in contours:
        if contour.shape[0] > max_len:
            max_len = contour.shape[0]
            outline = contour
    outline_img = cv2.drawContours(np.zeros(image.shape), [outline], -1,
                                   (255, 255, 255), 2)
    smooth_outline = gaussian_filter(outline_img, outline_filter_sigma)
    outline_img = ((smooth_outline.astype(np.float32) / smooth_outline.max(
                    )) * 255).astype(np.uint8)

    if verbose:
        display(outline_img, 'Longest Edge')
        
    return outline_img

# Harris Corners
def harris_corners(image, outline=True, blockSize=2, ksize=3, harris_k=0.06,
                   verbose=False, **kwargs):
    if outline:
        image = longest_edge(image, verbose=verbose, **kwargs)

    raw_corners = cv2.cornerHarris(image, blockSize, ksize, harris_k)
    dilated = cv2.dilate(raw_corners, None)
    _, scaled = cv2.threshold(dilated, 0.01 * dilated.max(), 255, 0)
    corners = scaled.astype(np.uint8)

    if verbose:
        display(corners, 'Outline corners')

    return corners
  
  #SIFT corner detection ERROR :'Module has no object SIFT'
def sift(image,outline=True,verbose=False,**kwargs):
    if outline:
      image=longest_edge(image,verbose=verbose,**kwargs)
    sift1 = cv2.SIFT()
    kp = sift1.detect(image,None)
    image=cv2.drawKeypoints(image,kp)
    
    if verbose: 
       display(image,'SIFT_corners')
    return image
    
# Shi-Tomasi corner detector
def shi_tomasi(image, maxCorners=25, qualityLevel=0.1, outline=True,
               verbose=False, **kwargs):
    if outline:
       image=longest_edge(image, verbose=verbose, **kwargs)

    corners = cv2.goodFeaturesToTrack(image, maxCorners, qualityLevel, 10)
    corners = np.int0(corners)
    x_coor=[]
    y_coor=[]
    for j in corners:
        a, b = j.ravel()
        x_coor.append(a)
        y_coor.append(b)
    z=zip(x_coor,y_coor)   
    for i in corners:
        x,y = i.ravel()
        cv2.circle(image,(x,y),3,255,-1)

    if verbose:
        display(image, "Shi-Tomasi Corner Detection")
    return image,z

#FAST corner detector
def fast(image,outline=False,nor_max_supperesion=True,verbose=False,**kwargs):
    if outline:
       image=longest_edge(image, verbose=verbose, **kwargs)
    fast = cv2.FastFeatureDetector_create() 
    if nor_max_supperesion is not True:
       kp = fast.detect(img,None)
    else:
       fast.setNonmaxSuppression(0)
       kp = fast.detect(img,None)
    img2 = cv2.drawKeypoints(img, kp, None, color=(127,0,0))
    if verbose:
       display(img2,'FAST Corners')

#ORB corner generator 
def orb_corner(image, verbose=False, WTA_K=4, nfeatures=100, outline=False,
               **kwargs):
    if outline:
       image = longest_edge(image, verbose=verbose, **kwargs)
    orb = cv2.ORB_create(nfeatures=nfeatures, WTA_K=WTA_K)
    kp = orb.detect(image, None)
    kp, des = orb.compute(image, kp)
    img2 = cv2.drawKeypoints(image, kp, None, color=(0,255,0), flags=0)
    if verbose:
       display(img2,'ORB Corners')  

# Cropping image
def crop(image, ur_size=120, ul_size=100, lr_size=120, ll_size=180,
         verbose=False, **kwargs):
     image = image[20:, :]
     col = image.shape[1]
     upper_right_triangle = np.array([[col - ur_size, 0], [col, 0],
                                      [col, ur_size]])
     lower_right_triangle = np.array([[col - lr_size, col], [col, col - lr_size],
                                      [col, col]])
     upper_left_triangle = np.array([[0, 0], [ul_size, 0], [0, ul_size]])
     lower_left_triangle = np.array([[0, col - ll_size], [ll_size, col],
                                     [0, col]])

     color = [0, 0, 0]
     #color = [255, 255, 255]
     image = cv2.fillConvexPoly(image, upper_right_triangle, color)
     image = cv2.fillConvexPoly(image, lower_right_triangle, color)
     image = cv2.fillConvexPoly(image, lower_left_triangle, color)
     image = cv2.fillConvexPoly(image, upper_left_triangle, color)

     if verbose:
        display(image, 'Cropped Image')

     return image

parser = argparse.ArgumentParser(description="Fiducial Localization")
parser.add_argument('-i', '--image', metavar='', type=str,
                    help='image to be processed')
args = parser.parse_args()
if args.image:
    try:
        img = import_dicom(args.image)
    except InvalidDicomError:
        img = cv2.imread(args.image, 0)
    if img is None:
        raise Exception('Image is of an unsupported type')
else:
    img = cv2.imread('./Downloads/IM106.jpg', 0)

if __name__ == '__main__':
    display(img, 'Image')
    img = crop(img, verbose=True)
    harris_corners(img, outline=True, verbose=True)

plt.show()


