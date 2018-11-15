updown_position = 500
new_position = 0
prev_position = updown_position

steps = None
direction = None
if new_position >= updown_position:
    direction = "up"
    steps = new_position - updown_position
elif new_position <= updown_position:
    direction = "down"
    steps = updown_position - new_position

for step in range(steps):
    if direction == "up" and updown_position < 5500:
        updown_position += 1
    elif direction == "down" and updown_position > 0:
        updown_position -= 1
    else:
        print("Limit Reach!")
        break



print("Steps: {steps}\nDirection: {dir}\nPrevious Position: {prevpos}\nNew Position: {newpos}\nCurrent Position: {pos}"
      .format(
        steps=steps,
        dir=direction,
        pos=updown_position,
        newpos=new_position,
        prevpos=prev_position)
      )