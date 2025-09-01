import sqlite3
import asyncio
from datetime import datetime
from typing import List, Optional, Dict

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Создание таблиц в базе данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                registration_date TIMESTAMP,
                total_points INTEGER DEFAULT 0,
                current_course_id INTEGER,
                subscription_active BOOLEAN DEFAULT 0
            )
        ''')
        
        # Таблица курсов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                price INTEGER,
                duration_days INTEGER,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Таблица уроков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                video_file_id TEXT,
                lesson_order INTEGER,
                points_reward INTEGER DEFAULT 10,
                FOREIGN KEY (course_id) REFERENCES courses (id)
            )
        ''')
        
        # Таблица заданий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                task_type TEXT,
                points_reward INTEGER DEFAULT 20,
                correct_answers TEXT,
                FOREIGN KEY (lesson_id) REFERENCES lessons (id)
            )
        ''')
        
        # Таблица прогресса
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                lesson_id INTEGER,
                task_id INTEGER,
                completed_at TIMESTAMP,
                points_earned INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Добавим несколько тестовых курсов
        cursor.execute('SELECT COUNT(*) FROM courses')
        if cursor.fetchone()[0] == 0:
            test_courses = [
                ("Основы футбола", "Базовый курс для начинающих", 1990, 30),
                ("Продвинутая техника", "Курс для опытных игроков", 2990, 45),
                ("Мастер-класс", "Профессиональный уровень", 4990, 60)
            ]
            cursor.executemany('''
                INSERT INTO courses (title, description, price, duration_days)
                VALUES (?, ?, ?, ?)
            ''', test_courses)
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id: int, username: str, full_name: str):
        """Добавление нового пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, full_name, registration_date)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, full_name, datetime.now()))
        conn.commit()
        conn.close()
    
    def get_user_points(self, user_id: int) -> int:
        """Получение очков пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT total_points FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0
    
    def add_points(self, user_id: int, points: int):
        """Добавление очков пользователю"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET total_points = total_points + ? WHERE user_id = ?
        ''', (points, user_id))
        conn.commit()
        conn.close()
    
    def get_courses(self) -> List[tuple]:
        """Получение всех активных курсов"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id, title, description, price FROM courses WHERE is_active = 1')
        courses = cursor.fetchall()
        conn.close()
        return courses
    
    def get_user_progress(self, user_id: int) -> Dict:
        """Получение прогресса пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Общие очки
        cursor.execute('SELECT total_points FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        total_points = result[0] if result else 0
        
        # Количество пройденных уроков
        cursor.execute('''
            SELECT COUNT(DISTINCT lesson_id) FROM user_progress 
            WHERE user_id = ? AND lesson_id IS NOT NULL
        ''', (user_id,))
        completed_lessons = cursor.fetchone()[0]
        
        # Количество выполненных заданий
        cursor.execute('''
            SELECT COUNT(*) FROM user_progress 
            WHERE user_id = ? AND task_id IS NOT NULL
        ''', (user_id,))
        completed_tasks = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_points': total_points,
            'completed_lessons': completed_lessons,
            'completed_tasks': completed_tasks
        }
    
    def record_lesson_completion(self, user_id: int, lesson_id: int, points: int):
        """Записать завершение урока"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_progress (user_id, lesson_id, completed_at, points_earned)
            VALUES (?, ?, ?, ?)
        ''', (user_id, lesson_id, datetime.now(), points))
        conn.commit()
        conn.close()
        self.add_points(user_id, points)
    
    def record_task_completion(self, user_id: int, task_id: int, points: int):
        """Записать выполнение задания"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_progress (user_id, task_id, completed_at, points_earned)
            VALUES (?, ?, ?, ?)
        ''', (user_id, task_id, datetime.now(), points))
        conn.commit()
        conn.close()
        self.add_points(user_id, points)