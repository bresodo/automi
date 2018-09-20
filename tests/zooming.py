import cv2
import imutils
def Zoom(cv2Object, zoomSize):
    # Resizes the image/video frame to the specified amount of "zoomSize".
    # A zoomSize of "2", for example, will double the canvas size
    cv2Object = imutils.resize(cv2Object, width=(zoomSize * cv2Object.shape[1]))
    # center is simply half of the height & width (y/2,x/2)
    center = (cv2Object.shape[0]/2,cv2Object.shape[1]/2)
    # cropScale represents the top left corner of the cropped frame (y/x)
    cropScale = (center[0]/zoomSize, center[1]/zoomSize)
    # The image/video frame is cropped to the center with a size of the original picture
    # image[y1:y2,x1:x2] is used to iterate and grab a portion of an image
    # (y1,x1) is the top left corner and (y2,x1) is the bottom right corner of new cropped frame.
    cv2Object = cv2Object[cropScale[0]:(center[0] + cropScale[0]), cropScale[1]:(center[1] + cropScale[1])]
    return cv2Object


cap = cv2.VideoCapture(0)
retval, frame = cap.read()
# scale = 1
# height, width, channel = frame.shape
# centerX, centerY = int(height / 2), int(width / 2)
# radiusX, radiusY = int(scale * height / 100), int(scale * width / 100)
# minX, maxX = centerX - radiusX, centerX + radiusX
# minY, maxY = centerY - radiusY, centerY + radiusY
# cropped = frame[minX:maxX, minY:maxY]
# cropped_zoom =  cv2.resize(frame,(width, height), interpolation=cv2.INTER_LINEAR)
frame = Zoom(frame, 2)
cv2.imshow("Cropped-Zoomed", frame)
cv2.waitKey()

