"""
Database Access Module for Lady卡卡 Calories Tracking System.
Provides thread-safe, parameterized SQLite operations for Userdata and Dailydata.
"""

import os
import sqlite3
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

DB_DIR = Path(__file__).resolve().parent

class SafeDBConnection:
    """Context manager for thread-safe SQLite connections with row dict support."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Connection:
        self.conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()


class Userdata:
    """Manages user profile data (height, weight, age, gender, activity level)."""

    def __init__(self, user_id: str):
        self.user_id = str(user_id)
        self.db_file = str(DB_DIR / f"{self.user_id}.db")
        self.table = "users"
        self._init_table()

    def _init_table(self):
        """Initialize the users table schema safely."""
        with SafeDBConnection(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    u_id TEXT PRIMARY KEY NOT NULL,
                    name TEXT,
                    gender BOOLEAN,
                    age INTEGER,
                    weight REAL,
                    height REAL,
                    activity_level REAL
                )
                """
            )

    def add_data(
        self,
        name: str = "test",
        gender: Union[bool, int, str] = True,
        age: float = 20,
        weight: float = 60,
        height: float = 160,
        activity_level: float = 1.2,
    ) -> Optional[Dict[str, Any]]:
        """Add user profile data if not exists."""
        # Convert gender to boolean
        if isinstance(gender, str):
            gender_bool = gender.lower() in ("true", "1", "男", "male")
        else:
            gender_bool = bool(gender)

        existing = self.search_data("u_id", self.user_id)
        if not existing:
            with SafeDBConnection(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    INSERT INTO {self.table} (u_id, name, gender, age, weight, height, activity_level)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.user_id,
                        str(name),
                        gender_bool,
                        int(age),
                        float(weight),
                        float(height),
                        float(activity_level),
                    ),
                )
        return self.search_data("u_id", self.user_id)

    def search_data(self, field: str, data: Any) -> Optional[Dict[str, Any]]:
        """Search user data by field name using parameterized query."""
        # Whitelist permitted column names to prevent identifier injection
        valid_columns = {"u_id", "name", "gender", "age", "weight", "height", "activity_level"}
        if field not in valid_columns:
            return None

        with SafeDBConnection(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {self.table} WHERE {field} = ?", (str(data),))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def update_data(self, field: str, data: Any) -> Optional[Dict[str, Any]]:
        """Update a specific field for the user."""
        valid_columns = {"name", "gender", "age", "weight", "height", "activity_level"}
        if field not in valid_columns:
            return None

        # Format and validate value type
        if field == "name":
            val = str(data)
        elif field == "gender":
            if isinstance(data, str):
                val = 1 if data in ("男", "male", "True", "true", "1") else 0
            else:
                val = 1 if data else 0
        elif field == "age":
            val = int(data)
        else:
            val = float(data)

        # Ensure user exists before update
        if not self.search_data("u_id", self.user_id):
            self.add_data()

        with SafeDBConnection(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE {self.table} SET {field} = ? WHERE u_id = ?",
                (val, self.user_id),
            )
        return self.search_data("u_id", self.user_id)

    def delete_data(self) -> Optional[Dict[str, Any]]:
        """Delete user profile record."""
        current = self.search_data("u_id", self.user_id)
        if current:
            with SafeDBConnection(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {self.table} WHERE u_id = ?", (self.user_id,))
        return current

    def get_all_columns(self) -> List[str]:
        """Get column names of users table."""
        with SafeDBConnection(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({self.table});")
            return [col["name"] for col in cursor.fetchall()]


class Dailydata:
    """Manages daily calorie intake, exercise logs, target weight and BMR."""

    def __init__(self, user_id: str):
        self.user_id = str(user_id)
        self.db_file = str(DB_DIR / f"{self.user_id}.db")
        self.table = "daily_info"
        self._init_table()

    def _init_table(self):
        """Initialize table and auto-migrate any missing columns."""
        with SafeDBConnection(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    date TEXT,
                    time TEXT,
                    u_id TEXT,
                    food_name TEXT,
                    food_calories REAL,
                    exercise_name TEXT,
                    exercise_duration REAL,
                    weight_target REAL,
                    bmr_target REAL,
                    calories_burned REAL
                )
                """
            )
            # Ensure schema migration for missing columns
            cursor.execute(f"PRAGMA table_info({self.table});")
            existing_cols = {col["name"] for col in cursor.fetchall()}
            required_cols = {
                "weight_target": "REAL",
                "bmr_target": "REAL",
                "calories_burned": "REAL",
            }
            for col_name, col_type in required_cols.items():
                if col_name not in existing_cols:
                    cursor.execute(f"ALTER TABLE {self.table} ADD COLUMN {col_name} {col_type}")

    def add_data(
        self,
        food_name: Optional[str] = None,
        food_calories: float = 0,
        exercise_name: Optional[str] = None,
        exercise_duration: float = 0,
        weight_target: float = 0,
        bmr_target: float = 0,
        calories_burned: float = 0,
    ) -> Optional[Dict[str, Any]]:
        """Add a daily food / exercise log entry."""
        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        with SafeDBConnection(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                INSERT INTO {self.table} (
                    date, time, u_id, food_name, food_calories,
                    exercise_name, exercise_duration, weight_target, bmr_target, calories_burned
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    date_str,
                    time_str,
                    self.user_id,
                    str(food_name) if food_name is not None else "",
                    float(food_calories or 0),
                    str(exercise_name) if exercise_name is not None else "",
                    float(exercise_duration or 0),
                    float(weight_target or 0),
                    float(bmr_target or 0),
                    float(calories_burned or 0),
                ),
            )
        return self.search_data("time", time_str)

    def search_data(self, field: str, data: Any) -> Optional[Dict[str, Any]]:
        """Search a single daily entry."""
        valid_columns = {
            "date", "time", "u_id", "food_name", "food_calories",
            "exercise_name", "exercise_duration", "weight_target", "bmr_target", "calories_burned"
        }
        if field not in valid_columns:
            return None

        with SafeDBConnection(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {self.table} WHERE {field} = ?", (str(data),))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def summary_calories_data(self, field: str = "food_calories", data: str = "1d") -> float:
        """Calculate the sum of calories or duration for a specific date range."""
        if field not in ("food_calories", "exercise_duration", "calories_burned"):
            return 0.0

        now = datetime.datetime.now()
        before_day = now.strftime("%Y-%m-%d")

        if data.endswith("d") and data[:-1].isdigit():
            days_ago = int(data[:-1])
            if days_ago > 0:
                before_day = (now - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")

        with SafeDBConnection(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT SUM({field}) FROM {self.table} WHERE date >= ?",
                (before_day,),
            )
            result = cursor.fetchone()
            if result and result[0] is not None:
                return float(result[0])
        return 0.0

    def search_all_data(self, field: str, data: str) -> Optional[Union[List[Dict[str, Any]], Dict[str, Any]]]:
        """Search records for a specific date or date range."""
        with SafeDBConnection(self.db_file) as conn:
            cursor = conn.cursor()

            if field == "date":
                if data.endswith("d") and data[:-1].isdigit():
                    days_ago = int(data[:-1])
                    before_day = (
                        (datetime.datetime.now() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")
                        if days_ago > 0
                        else datetime.datetime.now().strftime("%Y-%m-%d")
                    )
                    cursor.execute(f"SELECT * FROM {self.table} WHERE date >= ?", (before_day,))
                else:
                    cursor.execute(f"SELECT * FROM {self.table} WHERE date = ?", (data,))
            else:
                cursor.execute(f"SELECT * FROM {self.table} WHERE {field} = ?", (data,))

            rows = cursor.fetchall()
            if not rows:
                return None
            return [dict(row) for row in rows]

    def update_data(self, field: str, data: Any) -> Optional[Dict[str, Any]]:
        """Update a specific field for current user."""
        valid_columns = {"weight_target", "bmr_target", "food_calories", "calories_burned"}
        if field not in valid_columns:
            return None

        with SafeDBConnection(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE {self.table} SET {field} = ? WHERE u_id = ?",
                (float(data), self.user_id),
            )
        return self.search_data("u_id", self.user_id)

    def delete_data(self, field: str, data: str) -> Optional[Dict[str, Any]]:
        """Delete records matching criteria."""
        valid_columns = {"date", "time", "u_id"}
        if field not in valid_columns:
            return None

        current = self.search_data(field, data)
        if current:
            with SafeDBConnection(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {self.table} WHERE {field} = ?", (str(data),))
        return current

    def get_all_columns(self) -> List[str]:
        """Get column names."""
        with SafeDBConnection(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({self.table});")
            return [col["name"] for col in cursor.fetchall()]
