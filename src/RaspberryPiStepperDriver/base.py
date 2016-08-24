import asyncio, logging, time
import RPi.GPIO as GPIO

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

# Motor rotation direction
CLOCKWISE = 1
COUNTERCLOCKWISE = -1

# Motor driver state
ENABLED = 1
DISABLED = -1

def sleep_microseconds(us_to_sleep):
  # log.debug('sleeping for seconds', us_to_sleep / float(1000000))
  time.sleep(us_to_sleep / float(1000000))

class StepperDriver:
  """
  Basic driver for all stepper drivers with DIR and STEP pins.
  """

  def __init__(self, motor_steps, dir_pin, step_pin,
               enable_pin=None, pin_mode=GPIO.BOARD, microsteps=1, rpm=60):
    """
    Arguments:
        motor_steps: number of steps per revolution
        dir_pin: pin number of DIR pin
        step_pin: pin number of STEP pin
        enable_pin: pin number of ENABLE pin
        us_to_step: Number of microseconds to wait for motor to take a step.
    """
    self.motor_steps = motor_steps
    self.dir_pin = dir_pin
    self.step_pin = step_pin
    self.enable_pin = enable_pin
    self.microsteps = microsteps
    self.rpm = rpm
    self._direction = CLOCKWISE
    self._aborted = False
    self._is_moving = False
    self._calc_step_pulse_us()

    GPIO.setmode(pin_mode)
    GPIO.setup(dir_pin, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(step_pin, GPIO.OUT, initial=GPIO.LOW)

  def _calc_step_pulse_us(self):
    """
    Calculate the step pulse in microseconds for a given rpm value.
    60[s/min] * 1000000[us/s] / microsteps / steps / rpm
    """
    if self.motor_steps and self.microsteps and self.rpm:
      self.step_pulse_us = 60 * 1000000 / self.motor_steps / self.microsteps / self.rpm
      log.debug('base.StepperDriver calculated step pulse %s motor_steps %s microsteps %s rpm %s',
        self.step_pulse_us, self.motor_steps, self.microsteps, self.rpm)
      # We currently try to do a 50% duty cycle so it's easy to see.
      # Other option is step_high_min, pulse_duration-step_high_min.
      self.pulse_duration_us = self.step_pulse_us / 2

  async def move(self, steps):
    """
    Move the motor a given number of steps.

    Can be called rapidly and repeately.
    Returns 0 if motor is already moving.
    Call abort() first to immediately start another move.

    Arguments:
        steps: Number of steps to move. positive to move forward, negative to reverse.
    """
    # Dont enter this method if we are already moving.
    if self._is_moving == True:
      log.debug('Already moving. Call abort() first if you want to move immediately')
      return 0
    self._aborted = False

    log.debug('Should move %s steps', steps)
    if steps == 0:
      return 0

    # Figure out direction and set accordingly
    direction = 1 if steps > 0 else -1
    self.set_direction(direction)

    steps_to_move = steps * direction # so steps is always positive

    # Move the motor
    self._is_moving = True
    while steps_to_move > 0:
      await asyncio.sleep(0)
      if self._aborted:
        log.debug('Aborted move with %s steps still to move', steps_to_move)
        break
      ts = time.time()
      GPIO.output(self.step_pin, GPIO.HIGH)
      sleep_microseconds(self.pulse_duration_us)
      GPIO.output(self.step_pin, GPIO.LOW)
      sleep_microseconds(self.pulse_duration_us)
      steps_to_move -= 1
    self._is_moving = False

    actual_steps = steps - ( steps_to_move * direction)
    log.debug('Actual steps moved %s', actual_steps)
    return actual_steps

  async def rotate(self, degrees):
    """
    Rotate motor a given number of degrees. Set the motor direction with
    set_direction.
    """
    steps = degrees * self.motor_steps * self.microsteps / 360
    await self.move(steps)

  def abort(self):
    """ Abort an asyncronous move """
    #if self._is_moving:
    log.debug('Aborting move')
    self._aborted = True

  def enable(self):
    if self.enable_pin:
      GPIO.setup(self.enable_pin, GPIO.OUT, initial=GPIO.LOW)
    # else error

  def disable(self):
    if self.enable_pin:
      GPIO.setup(self.enable_pin, GPIO.OUT, initial=GPIO.HIGH)
    # else error

  def set_state(self, state):
    if state == ENABLED:
      self.enable()
    elif state == DISABLED:
      self.disable()

  def set_rpm(self, rpm):
    self.rpm = rpm
    self._calc_step_pulse_us()

  def set_microstep(self, microsteps):
    self.microsteps = microsteps
    self._calc_step_pulse_us()

  def set_direction(self, direction):
    """
    Counter-clockwise when direction < 0.
    Clockwise when direction > 0.
    Only applies to rotate(). move() direction is set by passing positive or
    negative numbers.

    Direction: HIGH = forward, LOW = reverse
    """
    self._direction = direction
    logic_value = GPIO.LOW if direction < 0 else GPIO.HIGH
    GPIO.output(self.dir_pin, logic_value)

  @property
  def direction(self):
    return self._direction

  @property
  def is_moving(self):
      return self._is_moving

  @property
  def was_aborted(self):
      return self._aborted
