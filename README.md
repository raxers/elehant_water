# Elehant Water and Gas Sensor for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

# Компонент интеграции счётчиков воды и газа Элехант с Home Assistant.
## Требования
* Для интеграции требуется наличие Bluetooth модуля в сервере HA.

## Поддерживаются
### Газовые счётчики:
* СГБД-1.8
* СГБД-3.2
* СГБД-4.0
* СГБД-4.0 ТК
* СОНИК G4TK

### Счётчики воды:
* СВД-15
* СВД-20
* СВТ-15
* СВТ-20

*Если ваш счётчик Элехант отсутствует в списке - пишите - добавим*

## Установка
Скопируйте папку elehant_water в custom_components в корне конфигурации Home Assistant
В configuration.yaml добавьте следующие строки:

```yaml
sensor:
  - platform: elehant_water
    scan_duration: 10
    scan_interval: 600
    measurement_water: m3
    measurement_gas: m3
    devices:
      - id: 31560
        type: water
        name: "Вода Горячая Ванная"
      - id: 31561
        type: water
        name: "Вода Холодная Кухня"
      # Для двухтарифных счётчиков номера надо указывать через подчеркивание и в кавычках
      # Под первой записью укажите так же название для датчика температуры
      - id: '31562_1'
        type: water
        name: "Вода Горячая Кухня 1"
        name_temp: "Температура воды Кухня"
      - id: '31562_2'
        type: water
        name: "Вода Горячая Кухня 2"
      - id: 6998
        type: gas
        name: "Счетчик газа"
```

Где: 
* **id** - номер счётчика.
* **measurement_water: l** - отображать показания воды в литрах
* **measurement_water: m3** - отображать в метрах кубических
* **measurement_gas: l** - отображать показания газа в литрах
* **measurement_gas: m3** - отображать в метрах кубических

Частота и продолжительность сканирования задается в конфиге. На считывание первичных показателей потребуется 1-5 минут. Сами счетчики передают информацию в Advertise пакетах с рваной периодичностью.

Лицензия GPL v.3
