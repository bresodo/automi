import cv2

cap = cv2.VideoCapture(0)
ret, frame = cap.read()
print('Original Frame Size: {}'.format(len(frame)))
print('JPG')
ret, img = cv2.imencode('.jpg', frame)
print('Encoded(Pure) Frame Size: {} kb'.format(len(img)))

encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
ret, encimg = cv2.imencode('.jpg', frame, encode_param)
print('Encoded(90) Frame Size: {} kb'.format(len(encimg)))

encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
ret, encimg50 = cv2.imencode('.jpg', frame, encode_param)
print('Encoded(50) Frame Size: {} kb'.format(len(encimg50)))

cv2.imshow('Pure', cv2.imdecode(img, 1))
cv2.imshow('90', cv2.imdecode(encimg, 1))
cv2.imshow('50', cv2.imdecode(encimg50, 1))
cv2.waitKey()

print('PNG')
ret, img = cv2.imencode('.png', frame)
print('Encoded(Pure) Frame Size: {} kb'.format(len(img)))
encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 90]
ret, encimg = cv2.imencode('.png', frame, encode_param)
print('Encoded(90) Frame Size: {} kb'.format(len(encimg)))