# Elehant Water Sensor SVD-15 for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Donate](https://img.shields.io/badge/donate-Yandex-red.svg)](https://money.yandex.ru/to/41001371678546)

# Компонент интеграции счетчиков воды Элехант СВД-15 с Home Assistant.
Для интеграции требуется наличие Bluetooth модуля в сервере HA.

**Установка**
Скопируйте папку elehant_water в custom_components в корне конфигурации Home Assistant
В configuration.yaml добавьте следующие строки:

```yaml
sensor:
- platform: elehant_water
    devices:
    - id: 30123
        name: "Горячая вода"
    - id: 30124
        name: "Холодная вода" 
```

Где id - номер счетчика. 

Система сканирует эфир раз в 30 секунд. На считывание первичных показателей потребуется 1-5 минут. Сами счетчики передают информацию в Advertise пакетах с рваной периодичностью.
