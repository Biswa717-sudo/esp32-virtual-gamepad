#include <Arduino.h>
#include <BleGamepad.h>
#include <esp_system.h>
#include <esp_mac.h>

// Initialize BLE Gamepad instance
// Name: ESP32 Controller, Developer: Espressif
BleGamepad bleGamepad("ESP32 Controller", "Espressif");

// Define pin numbers (Suitable for ESP32 30-pin)
// Joystick (ADC1 pins must be used with BLE)
const int PIN_JOY_X = 32;
const int PIN_JOY_Y = 33;
const int PIN_JOY_BTN = 25;

// 4 Push Buttons
const int PIN_BTN_A = 26;
const int PIN_BTN_B = 27;
const int PIN_BTN_X = 14;
const int PIN_BTN_Y = 12;

// Shoulder Buttons & Triggers
const int PIN_BTN_LB = 23;
const int PIN_BTN_RB = 21;
const int PIN_BTN_LT = 22;
const int PIN_BTN_RT = 4;

// Status LEDs
const int PIN_LED_RED = 18;
const int PIN_LED_BLUE = 19;

// Joystick calibration variables
int joyCenterX = 2048;
int joyCenterY = 2048;
const int JOY_DEADZONE = 200;

// Button state variables
bool btnAPressed = false;
bool btnBPressed = false;
bool btnXPressed = false;
bool btnYPressed = false;
bool btnLBPressed = false;
bool btnRBPressed = false;
bool btnLTPressed = false;
bool btnRTPressed = false;
bool btnJoyPressed = false;

// Trigger time-based simulation variables
int triggerLTValue = 0; // 0 to 255
int triggerRTValue = 0; // 0 to 255
unsigned long lastLTRampTime = 0;
unsigned long lastRTRampTime = 0;
unsigned long rampUpDelay = 5;   // ms per step
unsigned long rampDownDelay = 3; // ms per step

// Update interval (in milliseconds)
const unsigned long UPDATE_INTERVAL = 10;
unsigned long lastUpdate = 0;

void setup() {
    Serial.begin(115200);
    Serial.println("Starting BLE Gamepad Setup...");

    // Forcefully change the hardware MAC address so Windows treats it as a 100% brand new device
    uint8_t new_mac[6] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF};
    esp_base_mac_addr_set(new_mac);

    // Setup digital pins with internal pull-ups
    pinMode(PIN_BTN_A, INPUT_PULLUP);
    pinMode(PIN_BTN_B, INPUT_PULLUP);
    pinMode(PIN_BTN_X, INPUT_PULLUP);
    pinMode(PIN_BTN_Y, INPUT_PULLUP);
    pinMode(PIN_BTN_LB, INPUT_PULLUP);
    pinMode(PIN_BTN_RB, INPUT_PULLUP);
    pinMode(PIN_BTN_LT, INPUT_PULLUP);
    pinMode(PIN_BTN_RT, INPUT_PULLUP);
    pinMode(PIN_JOY_BTN, INPUT_PULLUP);

    // Setup LED pins
    pinMode(PIN_LED_RED, OUTPUT);
    pinMode(PIN_LED_BLUE, OUTPUT);
    
    // Initial state: Disconnected (Red ON, Blue OFF)
    digitalWrite(PIN_LED_RED, HIGH);
    digitalWrite(PIN_LED_BLUE, LOW);

    // Let the ADC settle
    delay(100);

    // Calibrate joystick center
    long sumX = 0;
    long sumY = 0;
    const int numSamples = 50;

    for (int i = 0; i < numSamples; i++) {
        sumX += analogRead(PIN_JOY_X);
        sumY += analogRead(PIN_JOY_Y);
        delay(5);
    }

    joyCenterX = sumX / numSamples;
    joyCenterY = sumY / numSamples;

    Serial.printf("Joystick Calibrated Center - X: %d, Y: %d\n", joyCenterX, joyCenterY);

    // Fallback if values are way off
    if (joyCenterX < 1500 || joyCenterX > 2500) joyCenterX = 2048;
    if (joyCenterY < 1500 || joyCenterY > 2500) joyCenterY = 2048;

    // Configure gamepad properties
    BleGamepadConfiguration bleGamepadConfig;
    bleGamepadConfig.setAutoReport(false);
    bleGamepadConfig.setAxesMin(-32767);
    bleGamepadConfig.setAxesMax(32767);

    // Override NimBLE Security for strict Windows 10/11 Bluetooth drivers
    NimBLEDevice::setSecurityAuth(true, true, true);
    NimBLEDevice::setSecurityIOCap(BLE_HS_IO_NO_INPUT_OUTPUT);

    // Start BLE Gamepad
    bleGamepad.begin(&bleGamepadConfig);
    
    Serial.println("BLE Gamepad Initialized. Waiting for connection...");
}

// Function to process and map analog joystick reading to 16-bit signed integer
int16_t processBipolarAxis(int rawVal, int centerVal, bool invert, int deadzone) {
    if (invert) {
        rawVal = 4095 - rawVal;
        centerVal = 4095 - centerVal;
    }
    
    int diff = rawVal - centerVal;
    
    if (abs(diff) <= deadzone) {
        return 0; // Inside deadzone
    }
    
    if (diff > 0) {
        long mapped = (long)(diff - deadzone) * 32767 / (4095 - centerVal - deadzone);
        return (int16_t)constrain(mapped, 0, 32767);
    } else {
        long mapped = (long)(diff + deadzone) * 32767 / (centerVal - deadzone);
        return (int16_t)constrain(mapped, -32767, 0);
    }
}

// Helper function to update button states
void updateButton(uint8_t buttonId, bool isPressed, bool& currentState) {
    if (isPressed != currentState) {
        currentState = isPressed;
        if (currentState) {
            bleGamepad.press(buttonId);
        } else {
            bleGamepad.release(buttonId);
        }
    }
}

void loop() {
    bool isConnected = bleGamepad.isConnected();

    // Update LED status based on connection
    if (isConnected) {
        analogWrite(PIN_LED_BLUE, 1); // Dim the blue LED via PWM (1 out of 255)
        digitalWrite(PIN_LED_RED, LOW);
    } else {
        analogWrite(PIN_LED_BLUE, 0); // Turn off
        digitalWrite(PIN_LED_RED, HIGH);
    }

    if (!isConnected) {
        delay(100);
        return;
    }

    unsigned long currentMillis = millis();

    // Process Time-Based Analog Triggers (Non-blocking, runs every loop iteration)
    bool stateLT = (digitalRead(PIN_BTN_LT) == LOW);
    bool stateRT = (digitalRead(PIN_BTN_RT) == LOW);

    if (stateLT) {
        if (currentMillis - lastLTRampTime >= rampUpDelay) {
            if (triggerLTValue < 255) triggerLTValue++;
            lastLTRampTime = currentMillis;
        }
    } else {
        if (currentMillis - lastLTRampTime >= rampDownDelay) {
            if (triggerLTValue > 0) triggerLTValue--;
            lastLTRampTime = currentMillis;
        }
    }

    if (stateRT) {
        if (currentMillis - lastRTRampTime >= rampUpDelay) {
            if (triggerRTValue < 255) triggerRTValue++;
            lastRTRampTime = currentMillis;
        }
    } else {
        if (currentMillis - lastRTRampTime >= rampDownDelay) {
            if (triggerRTValue > 0) triggerRTValue--;
            lastRTRampTime = currentMillis;
        }
    }

    if (currentMillis - lastUpdate >= UPDATE_INTERVAL) {
        lastUpdate = currentMillis;

        // Read analog joystick values
        int rawX = analogRead(PIN_JOY_X);
        int rawY = analogRead(PIN_JOY_Y);

        // Read digital button values (LOW means pressed due to INPUT_PULLUP)
        bool stateA = (digitalRead(PIN_BTN_A) == LOW);
        bool stateB = (digitalRead(PIN_BTN_B) == LOW);
        bool stateX = (digitalRead(PIN_BTN_X) == LOW);
        bool stateY = (digitalRead(PIN_BTN_Y) == LOW);
        bool stateLB = (digitalRead(PIN_BTN_LB) == LOW);
        bool stateRB = (digitalRead(PIN_BTN_RB) == LOW);
        bool stateJoyBtn = (digitalRead(PIN_JOY_BTN) == LOW);

        // Process analog axes
        // Y is usually inverted on joysticks (pushing up lowers the voltage)
        int16_t mappedX = processBipolarAxis(rawX, joyCenterX, false, JOY_DEADZONE);
        int16_t mappedY = processBipolarAxis(rawY, joyCenterY, true, JOY_DEADZONE);

        // Update axes
        bleGamepad.setX(mappedX);
        bleGamepad.setY(mappedY);

        // Map 0-255 trigger values to -32767 to 32767 for BleGamepad
        int16_t bleLT = map(triggerLTValue, 0, 255, -32767, 32767);
        int16_t bleRT = map(triggerRTValue, 0, 255, -32767, 32767);
        bleGamepad.setLeftTrigger(bleLT);
        bleGamepad.setRightTrigger(bleRT);

        // Update buttons (Mapping to standard buttons)
        updateButton(BUTTON_1, stateA, btnAPressed);
        updateButton(BUTTON_2, stateB, btnBPressed);
        updateButton(BUTTON_3, stateX, btnXPressed);
        updateButton(BUTTON_4, stateY, btnYPressed);
        updateButton(BUTTON_5, stateLB, btnLBPressed);
        updateButton(BUTTON_6, stateRB, btnRBPressed);
        updateButton(BUTTON_7, stateLT, btnLTPressed);
        updateButton(BUTTON_8, stateRT, btnRTPressed);
        updateButton(BUTTON_11, stateJoyBtn, btnJoyPressed); // Usually mapped to left thumb click (L3)

        // Send the complete report to the host
        bleGamepad.sendReport();
    }
}
