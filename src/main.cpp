#include <Arduino.h>
#include <BleGamepad.h>
#include <esp_system.h>
#include <esp_mac.h>

BleGamepad bleGamepad("ESP32 Controller", "Espressif");

// NEW PIN MAPPINGS
const int PIN_BTN_LT = 15;
const int PIN_BTN_LB = 2;
const int PIN_BTN_VIEW = 4;
const int PIN_BTN_GUIDE = 16;
const int PIN_BTN_MENU = 17;
const int PIN_BTN_DPAD_UP = 5;
const int PIN_BTN_DPAD_DOWN = 18;
const int PIN_BTN_DPAD_LEFT = 19;
const int PIN_BTN_DPAD_RIGHT = 21;

const int PIN_BTN_RT = 13;
const int PIN_BTN_RB = 12;
const int PIN_BTN_Y = 14;
const int PIN_BTN_B = 27;
const int PIN_BTN_A = 26;
const int PIN_BTN_X = 25;

const int PIN_RIGHT_JOY_BTN_U = 33;
const int PIN_RIGHT_JOY_BTN_D = 32;
const int PIN_RIGHT_JOY_BTN_L = 39;
const int PIN_RIGHT_JOY_BTN_R = 36;

const int PIN_LEFT_JOY_X = 34;
const int PIN_LEFT_JOY_Y = 35;

const int PIN_LED_BLUE = 22;
const int PIN_LED_RED = 23;

// Calibration
int leftJoyCenterX = 2048;
int leftJoyCenterY = 2048;
const int JOY_DEADZONE = 200;

const unsigned long UPDATE_INTERVAL = 10;
unsigned long lastUpdate = 0;

void setup() {
    Serial.begin(115200);

    uint8_t new_mac[6] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF};
    esp_base_mac_addr_set(new_mac);

    int pullup_pins[] = {PIN_BTN_LT, PIN_BTN_LB, PIN_BTN_VIEW, PIN_BTN_GUIDE, PIN_BTN_MENU, 
                         PIN_BTN_DPAD_UP, PIN_BTN_DPAD_DOWN, PIN_BTN_DPAD_LEFT, PIN_BTN_DPAD_RIGHT,
                         PIN_BTN_RT, PIN_BTN_RB, PIN_BTN_Y, PIN_BTN_B, PIN_BTN_A, PIN_BTN_X,
                         PIN_RIGHT_JOY_BTN_U, PIN_RIGHT_JOY_BTN_D};
    for(int pin : pullup_pins) pinMode(pin, INPUT_PULLUP);
    
    pinMode(PIN_RIGHT_JOY_BTN_L, INPUT);
    pinMode(PIN_RIGHT_JOY_BTN_R, INPUT);

    pinMode(PIN_LED_RED, OUTPUT);
    pinMode(PIN_LED_BLUE, OUTPUT);
    digitalWrite(PIN_LED_RED, HIGH);
    digitalWrite(PIN_LED_BLUE, LOW);

    delay(100);

    long sumLX = 0, sumLY = 0;
    for (int i = 0; i < 50; i++) {
        sumLX += analogRead(PIN_LEFT_JOY_X);
        sumLY += analogRead(PIN_LEFT_JOY_Y);
        delay(5);
    }
    leftJoyCenterX = sumLX / 50;
    leftJoyCenterY = sumLY / 50;
    if (leftJoyCenterX < 1500 || leftJoyCenterX > 2500) leftJoyCenterX = 2048;
    if (leftJoyCenterY < 1500 || leftJoyCenterY > 2500) leftJoyCenterY = 2048;

    BleGamepadConfiguration bleGamepadConfig;
    bleGamepadConfig.setAutoReport(false);
    bleGamepadConfig.setAxesMin(-32767);
    bleGamepadConfig.setAxesMax(32767);

    NimBLEDevice::setSecurityAuth(true, true, true);
    NimBLEDevice::setSecurityIOCap(BLE_HS_IO_NO_INPUT_OUTPUT);
    bleGamepad.begin(&bleGamepadConfig);
}

int16_t processBipolarAxis(int rawVal, int centerVal, bool invert, int deadzone) {
    if (invert) {
        rawVal = 4095 - rawVal;
        centerVal = 4095 - centerVal;
    }
    int diff = rawVal - centerVal;
    if (abs(diff) <= deadzone) return 0;
    if (diff > 0) {
        long mapped = (long)(diff - deadzone) * 32767 / (4095 - centerVal - deadzone);
        return (int16_t)constrain(mapped, 0, 32767);
    } else {
        long mapped = (long)(diff + deadzone) * 32767 / (centerVal - deadzone);
        return (int16_t)constrain(mapped, -32767, 0);
    }
}

void loop() {
    bool isConnected = bleGamepad.isConnected();
    if (isConnected) {
        analogWrite(PIN_LED_BLUE, 1);
        digitalWrite(PIN_LED_RED, LOW);
    } else {
        analogWrite(PIN_LED_BLUE, 0);
        digitalWrite(PIN_LED_RED, HIGH);
        delay(100);
        return;
    }

    unsigned long currentMillis = millis();
    if (currentMillis - lastUpdate >= UPDATE_INTERVAL) {
        lastUpdate = currentMillis;

        int rawLX = analogRead(PIN_LEFT_JOY_X);
        int rawLY = analogRead(PIN_LEFT_JOY_Y);

        int16_t mappedLX = processBipolarAxis(rawLX, leftJoyCenterX, false, JOY_DEADZONE);
        int16_t mappedLY = processBipolarAxis(rawLY, leftJoyCenterY, true, JOY_DEADZONE);

        bool rsUp = (digitalRead(PIN_RIGHT_JOY_BTN_U) == LOW);
        bool rsDown = (digitalRead(PIN_RIGHT_JOY_BTN_D) == LOW);
        bool rsLeft = (digitalRead(PIN_RIGHT_JOY_BTN_L) == LOW);
        bool rsRight = (digitalRead(PIN_RIGHT_JOY_BTN_R) == LOW);
        
        int16_t mappedRX = 0;
        int16_t mappedRY = 0;
        if(rsLeft) mappedRX = -32767;
        else if(rsRight) mappedRX = 32767;
        if(rsUp) mappedRY = 32767;
        else if(rsDown) mappedRY = -32767;

        bleGamepad.setX(mappedLX);
        bleGamepad.setY(mappedLY);
        bleGamepad.setZ(mappedRX);
        bleGamepad.setRZ(mappedRY);

        if(digitalRead(PIN_BTN_A) == LOW) bleGamepad.press(BUTTON_1); else bleGamepad.release(BUTTON_1);
        if(digitalRead(PIN_BTN_B) == LOW) bleGamepad.press(BUTTON_2); else bleGamepad.release(BUTTON_2);
        if(digitalRead(PIN_BTN_X) == LOW) bleGamepad.press(BUTTON_3); else bleGamepad.release(BUTTON_3);
        if(digitalRead(PIN_BTN_Y) == LOW) bleGamepad.press(BUTTON_4); else bleGamepad.release(BUTTON_4);
        if(digitalRead(PIN_BTN_LB) == LOW) bleGamepad.press(BUTTON_5); else bleGamepad.release(BUTTON_5);
        if(digitalRead(PIN_BTN_RB) == LOW) bleGamepad.press(BUTTON_6); else bleGamepad.release(BUTTON_6);
        
        if(digitalRead(PIN_BTN_MENU) == LOW) bleGamepad.press(BUTTON_10); else bleGamepad.release(BUTTON_10);
        if(digitalRead(PIN_BTN_VIEW) == LOW) bleGamepad.press(BUTTON_9); else bleGamepad.release(BUTTON_9);
        if(digitalRead(PIN_BTN_GUIDE) == LOW) bleGamepad.press(BUTTON_13); else bleGamepad.release(BUTTON_13);
        
        bool dpadUp = (digitalRead(PIN_BTN_DPAD_UP) == LOW);
        bool dpadDown = (digitalRead(PIN_BTN_DPAD_DOWN) == LOW);
        bool dpadLeft = (digitalRead(PIN_BTN_DPAD_LEFT) == LOW);
        bool dpadRight = (digitalRead(PIN_BTN_DPAD_RIGHT) == LOW);
        
        uint8_t hat = DPAD_CENTERED;
        if (dpadUp && dpadRight) hat = DPAD_UP_RIGHT;
        else if (dpadUp && dpadLeft) hat = DPAD_UP_LEFT;
        else if (dpadDown && dpadRight) hat = DPAD_DOWN_RIGHT;
        else if (dpadDown && dpadLeft) hat = DPAD_DOWN_LEFT;
        else if (dpadUp) hat = DPAD_UP;
        else if (dpadDown) hat = DPAD_DOWN;
        else if (dpadLeft) hat = DPAD_LEFT;
        else if (dpadRight) hat = DPAD_RIGHT;
        bleGamepad.setHat1(hat);

        if(digitalRead(PIN_BTN_LT) == LOW) bleGamepad.setLeftTrigger(32767); else bleGamepad.setLeftTrigger(-32767);
        if(digitalRead(PIN_BTN_RT) == LOW) bleGamepad.setRightTrigger(32767); else bleGamepad.setRightTrigger(-32767);

        bleGamepad.sendReport();
    }
}
