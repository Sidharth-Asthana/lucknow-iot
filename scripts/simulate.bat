@echo off
REM simulate.bat — Windows wrapper: publishes fake sensor data via Docker exec.
REM Run this while dev stack is up: docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
REM
REM Usage:
REM   scripts\simulate.bat              normal   (default)
REM   scripts\simulate.bat              monsoon
REM   scripts\simulate.bat              winter
REM   scripts\simulate.bat              lowwater

SET SCENARIO=%1
IF "%SCENARIO%"=="" SET SCENARIO=normal

ECHO [simulate.bat] Scenario: %SCENARIO%
ECHO Publishing sensor data via Docker Mosquitto container...
ECHO.

REM Helper macro — publishes one retained MQTT message via docker exec
REM Usage: CALL :pub <topic> <payload>

IF "%SCENARIO%"=="monsoon" (
  SET OUTDOOR_TEMP=32& SET OUTDOOR_RH=80& SET INDOOR_TEMP=29& SET INDOOR_RH=72
  SET INLET_TEMP=28& SET SOIL_E=55& SET SOIL_S=60& SET TANK=70& SET PV=2400& SET SOC=88
  ECHO [monsoon] Indoor RH 72%% will trigger bypass in ~3 min
) ELSE IF "%SCENARIO%"=="winter" (
  SET OUTDOOR_TEMP=12& SET OUTDOOR_RH=45& SET INDOOR_TEMP=18& SET INDOOR_RH=40
  SET INLET_TEMP=13& SET SOIL_E=20& SET SOIL_S=18& SET TANK=85& SET PV=900& SET SOC=60
  ECHO [winter] Outdoor T 12C will trigger winter bypass in ~30 min
) ELSE IF "%SCENARIO%"=="lowwater" (
  SET OUTDOOR_TEMP=44& SET OUTDOOR_RH=30& SET INDOOR_TEMP=34& SET INDOOR_RH=40
  SET INLET_TEMP=30& SET SOIL_E=15& SET SOIL_S=12& SET TANK=10& SET PV=5500& SET SOC=98
  ECHO [lowwater] Tank 10%% will cut beehive valve and send alert
) ELSE (
  SET OUTDOOR_TEMP=44& SET OUTDOOR_RH=35& SET INDOOR_TEMP=31& SET INDOOR_RH=52
  SET INLET_TEMP=30& SET SOIL_E=35& SET SOIL_S=42& SET TANK=68& SET PV=4200& SET SOC=76
  ECHO [normal] Hot summer afternoon, cooling mode active
)

ECHO.
ECHO [PV] Power: %PV%W  Battery: %SOC%%%
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/pv/power_w"       -m "{\"value\": %PV%}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/pv/battery_soc"   -m "{\"value\": %SOC%}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/pv/grid_import_w" -m "{\"value\": 0}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/pv/grid_export_w" -m "{\"value\": 500}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/pv/daily_kwh"     -m "{\"value\": 18.4}" -r

ECHO [Water] Tank: %TANK%%%
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/rwh/level"          -m "{\"value\": %TANK%}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/rwh/domestic_flow"  -m "{\"value\": 3.2}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/rwh/beehive_flow"   -m "{\"value\": 1.8}" -r

ECHO [Cooling] Outdoor: %OUTDOOR_TEMP%C / %OUTDOOR_RH%%%  Indoor: %INDOOR_TEMP%C / %INDOOR_RH%%%
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/beehive/outdoor_temp" -m "{\"value\": %OUTDOOR_TEMP%}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/beehive/outdoor_rh"   -m "{\"value\": %OUTDOOR_RH%}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/beehive/indoor_temp"  -m "{\"value\": %INDOOR_TEMP%}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/beehive/indoor_rh"    -m "{\"value\": %INDOOR_RH%}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/beehive/inlet_temp"   -m "{\"value\": %INLET_TEMP%}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/beehive/soil_e"       -m "{\"value\": %SOIL_E%}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/beehive/soil_s"       -m "{\"value\": %SOIL_S%}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/fan/beehive/fan_e/state"     -m "ON" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/fan/beehive/fan_e/speed"     -m "70" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/switch/beehive/damper_e/state" -m "ON" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/switch/beehive/damper_s/state" -m "ON" -r

ECHO [Security] Alarm: armed_home
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/alarm_control_panel/lucknow/state" -m "armed_home" -r

ECHO [Console] Panel: locked
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/lock/server_panel"            -m "{\"state\": \"LOCKED\"}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/console/cpu_pct_a"     -m "{\"value\": 8}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/ups/battery_charge"    -m "{\"value\": 100}" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/sensor/ups/status"            -m "{\"value\": \"OL\"}" -r

ECHO [Elevator] Ground floor, no fault
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/binary_sensor/elevator_floor_g/state"  -m "on" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/binary_sensor/elevator_floor_f1/state" -m "off" -r
docker exec mosquitto mosquitto_pub -h localhost -t "homeassistant/binary_sensor/elevator_fault/state"    -m "off" -r

ECHO.
ECHO Done. Open http://localhost:8123 and check Developer Tools ^> States
