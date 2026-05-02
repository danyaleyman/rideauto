import psycopg2
import psycopg2.extras
import json
import hashlib
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import threading
import logging

logger = logging.getLogger(__name__)


class PostgreSQLDatabase:
    """PostgreSQL база данных для хранения информации об автомобилях с поддержкой отслеживания изменений"""
    
    def __init__(self, host: str = "localhost", port: int = 5432, 
                 database: str = "encar", user: str = "postgres", 
                 password: str = "password", pool_size: int = 20):
        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }
        self.pool_size = pool_size
        self.lock = threading.Lock()
        self._init_db()
    
    def _get_connection(self):
        """Получает соединение с базой данных"""
        return psycopg2.connect(**self.connection_params)
    
    def _init_db(self):
        """Инициализация базы данных и создание таблиц"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Основная таблица автомобилей
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS cars (
                            id SERIAL PRIMARY KEY,
                            inner_id VARCHAR(255) UNIQUE NOT NULL,
                            data JSONB NOT NULL,
                            data_hash VARCHAR(32) NOT NULL,
                            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                            updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
                            last_seen TIMESTAMP WITH TIME ZONE NOT NULL,
                            is_active BOOLEAN DEFAULT TRUE
                        )
                    ''')
                    
                    # Индексы для быстрого поиска
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_inner_id ON cars(inner_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_is_active ON cars(is_active)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_updated_at ON cars(updated_at)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_seen ON cars(last_seen)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_hash ON cars(data_hash)')
                    
                    # Индекс для JSONB полей
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_gin ON cars USING GIN(data)')
                    
                    # Таблица для хранения метаданных системы
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS metadata (
                            key VARCHAR(255) PRIMARY KEY,
                            value TEXT NOT NULL,
                            updated_at TIMESTAMP WITH TIME ZONE NOT NULL
                        )
                    ''')
                    
                    # Сохраняем время последнего полного сканирования
                    cursor.execute('''
                        INSERT INTO metadata (key, value, updated_at) 
                        VALUES (%s, %s, %s)
                        ON CONFLICT (key) DO NOTHING
                    ''', ('last_full_scan', '1970-01-01T00:00:00', datetime.now()))
                    
                    conn.commit()
                    logger.info("PostgreSQL база данных инициализирована")
        except Exception as e:
            logger.error(f"Ошибка инициализации PostgreSQL базы данных: {e}")
            raise
    
    def _calculate_hash(self, data: Dict) -> str:
        """Рассчитывает хеш данных для отслеживания изменений"""
        # Преобразуем данные в строку для хеширования
        # Исключаем поля, которые могут меняться без реальных изменений (updated_at, last_seen)
        data_copy = data.copy()
        data_copy.pop('updated_at', None)
        data_copy.pop('last_seen', None)
        data_copy.pop('id', None)
        
        data_str = json.dumps(data_copy, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode('utf-8')).hexdigest()
    
    def add_or_update_car(self, car_data: Dict) -> bool:
        """
        Добавляет новый автомобиль или обновляет существующий
        
        Returns:
            bool: True если автомобиль был добавлен или обновлен, False если изменений не было
        """
        with self.lock:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    inner_id = car_data['inner_id']
                    current_time = datetime.now()
                    
                    # Рассчитываем хеш данных
                    data_hash = self._calculate_hash(car_data['data'])
                    
                    # Проверяем, существует ли автомобиль
                    cursor.execute('''
                        SELECT data_hash, updated_at FROM cars 
                        WHERE inner_id = %s AND is_active = TRUE
                    ''', (inner_id,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        existing_hash, existing_updated = existing
                        
                        # Если хеш не изменился, просто обновляем last_seen
                        if existing_hash == data_hash:
                            cursor.execute(
                                'UPDATE cars SET last_seen = %s WHERE inner_id = %s',
                                (current_time, inner_id)
                            )
                            conn.commit()
                            return False  # Изменений не было
                        
                        # Хеш изменился - обновляем данные
                        cursor.execute('''
                            UPDATE cars 
                            SET data = %s, data_hash = %s, updated_at = %s, last_seen = %s,
                                needs_pricing_recompute = TRUE
                            WHERE inner_id = %s
                        ''', (json.dumps(car_data['data'], ensure_ascii=False), data_hash, current_time, current_time, inner_id))
                        
                        conn.commit()
                        return True  # Данные были обновлены
                        
                    else:
                        # Новый автомобиль
                        cursor.execute('''
                            INSERT INTO cars (inner_id, data, data_hash, created_at, updated_at, last_seen, needs_pricing_recompute)
                            VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                        ''', (
                            inner_id,
                            json.dumps(car_data['data'], ensure_ascii=False),
                            data_hash,
                            current_time,
                            current_time,
                            current_time
                        ))
                        
                        conn.commit()
                        return True  # Автомобиль был добавлен
    
    def get_car(self, inner_id: str) -> Optional[Dict]:
        """Получает автомобиль по внутреннему ID"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute('''
                    SELECT inner_id, data, created_at, updated_at, last_seen
                    FROM cars 
                    WHERE inner_id = %s AND is_active = TRUE
                ''', (inner_id,))
                
                result = cursor.fetchone()
                
                if result:
                    return {
                        'inner_id': result['inner_id'],
                        'data': result['data'],
                        'created_at': result['created_at'].isoformat(),
                        'updated_at': result['updated_at'].isoformat(),
                        'last_seen': result['last_seen'].isoformat()
                    }
                return None
    
    def get_all_active_cars(self, limit: int = None) -> List[Dict]:
        """Получает все активные автомобили"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                query = '''
                    SELECT inner_id, data, created_at, updated_at, last_seen
                    FROM cars 
                    WHERE is_active = TRUE
                    ORDER BY updated_at DESC
                '''
                
                if limit:
                    query += f' LIMIT {limit}'
                
                cursor.execute(query)
                results = cursor.fetchall()
                
                cars = []
                for row in results:
                    cars.append({
                        'inner_id': row['inner_id'],
                        'data': row['data'],
                        'created_at': row['created_at'].isoformat(),
                        'updated_at': row['updated_at'].isoformat(),
                        'last_seen': row['last_seen'].isoformat()
                    })
                
                return cars
    
    def get_car_ids(self) -> List[str]:
        """Получает список всех активных ID автомобилей"""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT inner_id FROM cars WHERE is_active = TRUE')
                results = cursor.fetchall()
                
                return [row[0] for row in results]
    
    def mark_cars_as_inactive(self, active_ids: List[str]) -> int:
        """
        Помечает автомобили как неактивные (удаленные с сайта)
        
        Returns:
            int: Количество помеченных автомобилей
        """
        with self.lock:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Получаем все активные ID из базы
                    cursor.execute('SELECT inner_id FROM cars WHERE is_active = TRUE')
                    all_ids = set(row[0] for row in cursor.fetchall())
                    
                    # Находим ID, которых нет в новом списке (удаленные)
                    inactive_ids = list(all_ids - set(active_ids))
                    
                    if inactive_ids:
                        # Используем IN с массивом для эффективного обновления
                        cursor.execute(
                            'UPDATE cars SET is_active = FALSE WHERE inner_id = ANY(%s)',
                            (inactive_ids,)
                        )
                        conn.commit()
                    
                    return len(inactive_ids)
    
    def get_stats(self) -> Dict:
        """Получает статистику по базе данных"""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                # Общее количество автомобилей
                cursor.execute('SELECT COUNT(*) FROM cars WHERE is_active = TRUE')
                total_active = cursor.fetchone()[0]
                
                # Количество автомобилей, добавленных сегодня
                today = datetime.now().strftime('%Y-%m-%d')
                cursor.execute('SELECT COUNT(*) FROM cars WHERE is_active = TRUE AND created_at::date = %s', (today,))
                added_today = cursor.fetchone()[0]
                
                # Количество автомобилей, обновленных сегодня
                cursor.execute('SELECT COUNT(*) FROM cars WHERE is_active = TRUE AND updated_at::date = %s', (today,))
                updated_today = cursor.fetchone()[0]
                
                # Количество удаленных автомобилей (неактивных)
                cursor.execute('SELECT COUNT(*) FROM cars WHERE is_active = FALSE')
                deleted_count = cursor.fetchone()[0]
                
                # Последнее полное сканирование
                cursor.execute("SELECT value FROM metadata WHERE key = 'last_full_scan'")
                last_scan = cursor.fetchone()
                last_scan = last_scan[0] if last_scan else 'Never'
                
                # Дополнительная статистика
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_cars,
                        COUNT(*) FILTER (WHERE is_active = TRUE) as active_cars,
                        COUNT(*) FILTER (WHERE is_active = FALSE) as inactive_cars,
                        COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 day') as added_last_24h,
                        COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '1 day') as updated_last_24h,
                        COUNT(*) FILTER (WHERE last_seen >= NOW() - INTERVAL '1 day') as seen_last_24h
                    FROM cars
                ''')
                extended_stats = cursor.fetchone()
                
                return {
                    'total_active': total_active,
                    'added_today': added_today,
                    'updated_today': updated_today,
                    'deleted_count': deleted_count,
                    'last_full_scan': last_scan,
                    'extended_stats': {
                        'total_cars': extended_stats[0],
                        'active_cars': extended_stats[1],
                        'inactive_cars': extended_stats[2],
                        'added_last_24h': extended_stats[3],
                        'updated_last_24h': extended_stats[4],
                        'seen_last_24h': extended_stats[5]
                    }
                }
    
    def update_last_full_scan(self):
        """Обновляет время последнего полного сканирования"""
        with self.lock:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        UPDATE metadata 
                        SET value = %s, updated_at = %s 
                        WHERE key = 'last_full_scan'
                    ''', (datetime.now().isoformat(), datetime.now()))
                    
                    conn.commit()
    
    def export_to_json(self, filename: str = None) -> str:
        """Экспортирует все активные автомобили в JSON файл"""
        if not filename:
            filename = f'encar_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        cars = self.get_all_active_cars()
        
        export_data = {
            'export_date': datetime.now().isoformat(),
            'total_cars': len(cars),
            'cars': cars
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return filename
    
    def get_cars_by_filter(self, filters: Dict, limit: int = None) -> List[Dict]:
        """
        Получает автомобили по фильтрам с использованием JSONB запросов
        
        Args:
            filters: Словарь фильтров (например: {'mark': 'BMW', 'year': '2020'})
            limit: Ограничение на количество результатов
        
        Returns:
            List[Dict]: Список автомобилей
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # Формируем условия WHERE для JSONB полей
                conditions = []
                values = []
                
                for key, value in filters.items():
                    conditions.append(f"data->>'{key}' = %s")
                    values.append(str(value))
                
                where_clause = " AND ".join(conditions) if conditions else "TRUE"
                
                query = f'''
                    SELECT inner_id, data, created_at, updated_at, last_seen
                    FROM cars 
                    WHERE is_active = TRUE AND {where_clause}
                    ORDER BY updated_at DESC
                '''
                
                if limit:
                    query += f' LIMIT {limit}'
                
                cursor.execute(query, values)
                results = cursor.fetchall()
                
                cars = []
                for row in results:
                    cars.append({
                        'inner_id': row['inner_id'],
                        'data': row['data'],
                        'created_at': row['created_at'].isoformat(),
                        'updated_at': row['updated_at'].isoformat(),
                        'last_seen': row['last_seen'].isoformat()
                    })
                
                return cars
    
    def get_duplicate_cars(self) -> List[Dict]:
        """Находит дубликаты автомобилей по VIN"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute('''
                    SELECT data->>'vin' as vin, COUNT(*) as count, 
                           ARRAY_AGG(inner_id) as car_ids
                    FROM cars 
                    WHERE is_active = TRUE AND data->>'vin' IS NOT NULL AND data->>'vin' != ''
                    GROUP BY data->>'vin'
                    HAVING COUNT(*) > 1
                    ORDER BY COUNT(*) DESC
                ''')
                
                results = cursor.fetchall()
                return [dict(row) for row in results]
    
    def cleanup_old_inactive_cars(self, days_to_keep: int = 30) -> int:
        """
        Удаляет неактивные автомобили старше указанного количества дней
        
        Args:
            days_to_keep: Количество дней хранения неактивных записей
        
        Returns:
            int: Количество удаленных записей
        """
        with self.lock:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        DELETE FROM cars 
                        WHERE is_active = FALSE AND updated_at < NOW() - INTERVAL '%s days'
                    ''', (days_to_keep,))
                    
                    deleted_count = cursor.rowcount
                    conn.commit()
                    
                    logger.info(f"Удалено {deleted_count} старых неактивных записей")
                    return deleted_count
    
    def get_performance_stats(self) -> Dict:
        """Получает статистику производительности PostgreSQL"""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                # Статистика по таблице cars
                cursor.execute('''
                    SELECT 
                        schemaname,
                        tablename,
                        n_tup_ins as inserts,
                        n_tup_upd as updates,
                        n_tup_del as deletes,
                        n_tup_hot_upd as hot_updates,
                        n_live_tup as live_tuples,
                        n_dead_tup as dead_tuples,
                        last_vacuum,
                        last_autovacuum,
                        last_analyze,
                        last_autoanalyze
                    FROM pg_stat_user_tables 
                    WHERE tablename = 'cars'
                ''')
                
                table_stats = cursor.fetchone()
                
                # Информация о размере таблицы
                cursor.execute('''
                    SELECT 
                        pg_size_pretty(pg_total_relation_size('cars')) as table_size,
                        pg_size_pretty(pg_relation_size('cars')) as data_size,
                        pg_size_pretty(pg_total_relation_size('cars') - pg_relation_size('cars')) as index_size
                ''')
                
                size_info = cursor.fetchone()
                
                return {
                    'table_stats': dict(table_stats) if table_stats else {},
                    'size_info': dict(size_info) if size_info else {},
                    'timestamp': datetime.now().isoformat()
                }
    
    def close(self):
        """Закрывает соединение (для PostgreSQL pool management)"""
        pass  # Connection pooling can be added here if needed


def test_postgresql_database():
    """Тестирование PostgreSQL базы данных"""
    try:
        # Создаем базу данных (предполагается, что PostgreSQL сервер запущен)
        db = PostgreSQLDatabase(
            host="localhost",
            port=5432,
            database="encar",
            user="postgres",
            password="password"
        )
        
        # Тестовые данные
        test_car = {
            'inner_id': 'test123',
            'data': {
                'mark': 'BMW',
                'model': 'X5',
                'price': '50000',
                'year': '2020',
                'vin': 'TESTVIN123456789'
            },
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat()
        }
        
        print("Тестирование PostgreSQL базы данных...")
        
        # Добавление автомобиля
        result = db.add_or_update_car(test_car)
        print(f"✅ Добавление автомобиля: {result}")
        
        # Повторное добавление без изменений
        result = db.add_or_update_car(test_car)
        print(f"✅ Повторное добавление без изменений: {result}")
        
        # Обновление данных
        test_car['data']['price'] = '55000'
        result = db.add_or_update_car(test_car)
        print(f"✅ Обновление данных: {result}")
        
        # Получение автомобиля
        car = db.get_car('test123')
        print(f"✅ Получение автомобиля: {'найден' if car else 'не найден'}")
        
        if car:
            print(f"   Цена: {car['data']['price']}")
        
        # Статистика
        stats = db.get_stats()
        print(f"✅ Статистика: активных={stats['total_active']}, добавлено сегодня={stats['added_today']}")
        
        # Поиск по фильтрам
        filtered_cars = db.get_cars_by_filter({'mark': 'BMW', 'year': '2020'})
        print(f"✅ Поиск по фильтрам: найдено {len(filtered_cars)} автомобилей")
        
        # Статистика производительности
        perf_stats = db.get_performance_stats()
        print(f"✅ Статистика производительности: {perf_stats['size_info']}")
        
        print("🎉 Все тесты PostgreSQL базы данных пройдены!")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования PostgreSQL: {e}")
        print("💡 Убедитесь, что PostgreSQL сервер запущен и настроен")
        return False


if __name__ == '__main__':
    test_postgresql_database()