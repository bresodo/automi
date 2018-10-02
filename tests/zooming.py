import cv2

cap = cv2.VideoCapture(0)

ret, frame = cap.read()
h, w = frame.shape[:2]
center = (w/2, h/2)
print(center)

frameWidth = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frameHeight = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

cv2.putText(img = frame, text = 'How are you', org = (int(frameWidth/2 - 20),int(frameHeight/2)), fontFace = cv2.FONT_HERSHEY_DUPLEX, fontScale = 3,
                    color = (0, 255, 0))
cv2.namedWindow('orig', cv2.WINDOW_NORMAL)
cv2.resizeWindow('orig', (600, 480))
cv2.imshow('orig', frame)

# crop_img = frame[70:170, 440:540]  # Vertical, Horizontal
# cv2.imshow('cropped', crop_img)

cv2.namedWindow('failed', cv2.WINDOW_NORMAL)
cv2.resizeWindow('failed', (600, 480))
crop_img = frame[int(center[0])-50:int(center[0])+50, int(center[1])-50:int(center[1])+50]  # Vertical, Horizontal
cv2.imshow('failed', crop_img)

cv2.namedWindow('cropped', cv2.WINDOW_NORMAL)
cv2.resizeWindow('cropped', (600, 480))
r = 100.0 / frame.shape[1]
dim = (100, int(frame.shape[0] * r))
zoom = 50
crop_img = frame[int(center[1]) - zoom:int(center[1]) + zoom, int(center[0]) - zoom:int(center[0]) + zoom]  # Vertical, Horizontal
crop_img = cv2.resize(crop_img, dim, interpolation = cv2.INTER_AREA)
cv2.imshow('cropped', crop_img)

cv2.waitKey()
cap.release()