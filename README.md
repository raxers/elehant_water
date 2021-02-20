# Elehant Water Sensor SVD-15 and SVT-15 for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Donate](https://img.shields.io/badge/donate-Yandex-red.svg)](https://money.yandex.ru/to/41001371678546)

# Компонент интеграции счетчиков воды Элехант СВД-15 и СВТ-15 с Home Assistant.
Для интеграции требуется наличие Bluetooth модуля в сервере HA.

**Установка**
Скопируйте папку elehant_water в custom_components в корне конфигурации Home Assistant
В configuration.yaml добавьте следующие строки:

```yaml
sensor:
  - platform: elehant_water
    scan_duration: 10
    scan_interval: 30
    measurement: l
    devices:
      - id: 31560
        name: "Вода Горячая Ванная"
      - id: 31561
        name: "Вода Холодная Кухня"
      # Для двухтарифных счетчиков номера надо указывать через подчеркивание и в кавычках
      # Под первой записью укажите так же название для датчика температуры
      - id: '31562_1'
        name: "Вода Горячая Кухня 1"
        name_temp: "Температура воды Кухня"
      - id: '31562_2'
        name: "Вода Горячая Кухня 2"
```

Где: 

id - номер счетчика.

measurement: l - отображать показания в литрах или 

measurement: m3 - отображать в метрах кубических

Частота и продолжительность сканирования задается в конфиге. На считывание первичных показателей потребуется 1-5 минут. Сами счетчики передают информацию в Advertise пакетах с рваной периодичностью.

Лицензия GPL v.3
