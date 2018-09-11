import cv2


def get_frame():
    return False, None


ret, frame = get_frame()
print(ret)
print(frame)
if frame:
    print('Has frame')
else:
    print('No Frame')