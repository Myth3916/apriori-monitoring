import os
import json
import logging
from prometheus_client import start_http_server, Gauge, Info
import paho.mqtt.client as mqtt

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация MQTT
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "#")

# HTTP порт для Prometheus
HTTP_PORT = int(os.getenv("HTTP_PORT", 8000))

# Создаем метрики Prometheus
# Общие метрики для всех ТС
vehicle_info = Info('vehicle', 'Информация о транспортном средстве', ['vehicle_type', 'fuel_type', 'vehicle_id'])
gps_lat = Gauge('vehicle_gps_lat', 'Широта GPS', ['vehicle_type', 'fuel_type', 'vehicle_id'])
gps_lon = Gauge('vehicle_gps_lon', 'Долгота GPS', ['vehicle_type', 'fuel_type', 'vehicle_id'])
gps_alt = Gauge('vehicle_gps_alt', 'Высота GPS', ['vehicle_type', 'fuel_type', 'vehicle_id'])
speed_kmh = Gauge('vehicle_speed_kmh', 'Скорость в км/ч', ['vehicle_type', 'fuel_type', 'vehicle_id'])
engine_status = Gauge('vehicle_engine_status', 'Статус двигателя (1=on, 0=off)', ['vehicle_type', 'fuel_type', 'vehicle_id'])

# Метрики для дизельной техники
engine_rpm = Gauge('vehicle_engine_rpm', 'Обороты двигателя', ['vehicle_type', 'fuel_type', 'vehicle_id'])
fuel_level_pct = Gauge('vehicle_fuel_level_pct', 'Уровень топлива в %', ['vehicle_type', 'fuel_type', 'vehicle_id'])
temp_c = Gauge('vehicle_temp_c', 'Температура в °C', ['vehicle_type', 'fuel_type', 'vehicle_id'])
oil_pressure_bar = Gauge('vehicle_oil_pressure_bar', 'Давление масла в бар', ['vehicle_type', 'fuel_type', 'vehicle_id'])
engine_hours = Gauge('vehicle_engine_hours', 'Моточасы', ['vehicle_type', 'fuel_type', 'vehicle_id'])

# Метрики для электрической техники
battery_soc_pct = Gauge('vehicle_battery_soc_pct', 'Заряд батареи в %', ['vehicle_type', 'fuel_type', 'vehicle_id'])
battery_temp_c = Gauge('vehicle_battery_temp_c', 'Температура батареи в °C', ['vehicle_type', 'fuel_type', 'vehicle_id'])
current_a = Gauge('vehicle_current_a', 'Ток в А', ['vehicle_type', 'fuel_type', 'vehicle_id'])
voltage_v = Gauge('vehicle_voltage_v', 'Напряжение в В', ['vehicle_type', 'fuel_type', 'vehicle_id'])

# Метрики для роботов
temp_cpu_c = Gauge('vehicle_temp_cpu_c', 'Температура CPU в °C', ['vehicle_type', 'fuel_type', 'vehicle_id'])
lte_rssi = Gauge('vehicle_lte_rssi', 'Сигнал LTE (RSSI)', ['vehicle_type', 'fuel_type', 'vehicle_id'])
steering_angle_deg = Gauge('vehicle_steering_angle_deg', 'Угол поворота руля в градусах', ['vehicle_type', 'fuel_type', 'vehicle_id'])

# Метрика для RTK статуса
rtk_status = Gauge('vehicle_rtk_status', 'Статус RTK (0=none, 1=float, 2=fix)', ['vehicle_type', 'fuel_type', 'vehicle_id'])

# Словарь для маппинга строковых статусов в числа
STATUS_MAP = {
    'on': 1, 'off': 0,
    'fix': 2, 'float': 1, 'none': 0,
    'idle': 0, 'human': 1, 'teleop': 2, 'supervis': 3, 'autonom': 4,
    'pause': 1, 'run': 2, 'complete': 3, 'abort': 4
}

def parse_topic(topic):
    """Извлекает vehicle_type, fuel_type, vehicle_id из топика"""
    parts = topic.split('/')
    if len(parts) >= 4:
        return parts[0], parts[1], parts[2]
    return None, None, None

def on_connect(client, userdata, flags, rc):
    """Callback при подключении к MQTT брокеру"""
    logger.info(f"Connected to MQTT broker with result code {rc}")
    client.subscribe(MQTT_TOPIC)
    logger.info(f"Subscribed to topic: {MQTT_TOPIC}")

def on_message(client, userdata, msg):
    """Callback при получении сообщения"""
    # СРАЗУ логируем факт получения сообщения
    logger.info(f"📥 Received message on topic: {msg.topic}")
    
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())
        
        # Извлекаем labels из топика
        vehicle_type, fuel_type, vehicle_id = parse_topic(topic)
        if not vehicle_type:
            logger.warning(f"Cannot parse topic: {topic}")
            return
        
        labels = {'vehicle_type': vehicle_type, 'fuel_type': fuel_type, 'vehicle_id': vehicle_id}
        
        # Обновляем info метрику
        vehicle_info.labels(**labels).info({
            'schema_version': str(payload.get('schema_version', '')),
            'timestamp': str(payload.get('timestamp', ''))
        })
        
        # Обрабатываем метрики
        metrics = payload.get('metrics', {})
        
        # Общие метрики
        if 'gps_lat' in metrics:
            gps_lat.labels(**labels).set(metrics['gps_lat'])
        if 'gps_lon' in metrics:
            gps_lon.labels(**labels).set(metrics['gps_lon'])
        if 'gps_alt' in metrics:
            gps_alt.labels(**labels).set(metrics['gps_alt'])
        if 'speed_kmh' in metrics:
            speed_kmh.labels(**labels).set(metrics['speed_kmh'])
        if 'engine_status' in metrics:
            engine_status.labels(**labels).set(STATUS_MAP.get(metrics['engine_status'], 0))
        
        # Дизельные метрики
        if 'engine_rpm' in metrics:
            engine_rpm.labels(**labels).set(metrics['engine_rpm'])
        if 'fuel_level_pct' in metrics:
            fuel_level_pct.labels(**labels).set(metrics['fuel_level_pct'])
        if 'temp_c' in metrics:
            temp_c.labels(**labels).set(metrics['temp_c'])
        if 'oil_pressure_bar' in metrics:
            oil_pressure_bar.labels(**labels).set(metrics['oil_pressure_bar'])
        if 'engine_hours' in metrics:
            engine_hours.labels(**labels).set(metrics['engine_hours'])
        
        # Электрические метрики
        if 'battery_soc_pct' in metrics:
            battery_soc_pct.labels(**labels).set(metrics['battery_soc_pct'])
        if 'battery_temp_c' in metrics:
            battery_temp_c.labels(**labels).set(metrics['battery_temp_c'])
        if 'current_a' in metrics:
            current_a.labels(**labels).set(metrics['current_a'])
        if 'voltage_v' in metrics:
            voltage_v.labels(**labels).set(metrics['voltage_v'])
        
        # Метрики роботов
        if 'temp_cpu_c' in metrics:
            temp_cpu_c.labels(**labels).set(metrics['temp_cpu_c'])
        if 'lte_rssi' in metrics:
            lte_rssi.labels(**labels).set(metrics['lte_rssi'])
        if 'steering_angle_deg' in metrics:
            steering_angle_deg.labels(**labels).set(metrics['steering_angle_deg'])
        
        # RTK статус
        if 'rtk_status' in metrics:
            rtk_status.labels(**labels).set(STATUS_MAP.get(metrics['rtk_status'], 0))
        
        logger.info(f"✅ Successfully processed message from {topic}")
        
    except Exception as e:
        logger.error(f"❌ Error processing message: {e}", exc_info=True)

def main():
    """Главная функция"""
    logger.info(f"Starting MQTT Exporter on HTTP port {HTTP_PORT}")
    
    # Запускаем HTTP сервер для Prometheus
    start_http_server(HTTP_PORT)
    logger.info(f"Prometheus metrics available at http://0.0.0.0:{HTTP_PORT}/metrics")
    
    # Настраиваем MQTT клиент
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Подключаемся к MQTT брокеру
    logger.info(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    
    # Запускаем цикл обработки сообщений
    client.loop_forever()

if __name__ == "__main__":
    main()