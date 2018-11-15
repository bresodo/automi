import base64
import pickle
import struct

import cv2

cap = cv2.VideoCapture(0)

ok,frame = cap.read()
cv2.imshow("Frame", frame)
print(base64.b64encode(frame))
print(len(frame))
print(len(base64.b64encode(frame)))
print(len(pickle.dumps(frame)))

file = open("img.txt", "wb")
pickle.dump(frame, file)

# data = pickle.dumps(frame)
# frame_struct = b""
# if len(data) >= 65535:
#     frame_struct = struct.pack("L", len(data)) + data
# else:
#     frame_struct = struct.pack("L", len(data))  + data
#
# payload_size = struct.calcsize("L")


# file = open("frame_struct.txt", "w")
# file.write(str(frame_struct))
# print(frame_struct)
# print(data)
# print(frame)
# print(frame.shape)
cv2.waitKey(0)
cap.release()