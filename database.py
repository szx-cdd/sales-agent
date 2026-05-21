import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "sales_agent.db"

class Database:
    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                company TEXT,
                industry TEXT,
                phone TEXT,
                email TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                profile_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_histories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                source_type TEXT DEFAULT 'manual',
                source_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_histories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                analysis_type TEXT NOT NULL,
                result TEXT NOT NULL,
                chat_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_histories_customer ON chat_histories(customer_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_histories_customer ON analysis_histories(customer_id)")
        conn.commit()
        conn.close()

    def create_customer(self, name: str, company: str = None, industry: str = None,
                       phone: str = None, email: str = None, notes: str = None) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO customers (name, company, industry, phone, email, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, company, industry, phone, email, notes)
        )
        customer_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return customer_id

    def get_customer(self, customer_id: int):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_customers(self, search: str = None, industry: str = Query(None)):
        conn = self._get_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM customers WHERE 1=1"
        params = []
        if search:
            query += " AND (name LIKE ? OR company LIKE ? OR phone LIKE ?)"
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern, search_pattern])
        if industry:
            query += " AND industry = ?"
            params.append(industry)
        query += " ORDER BY updated_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def delete_customer(self, customer_id: int) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def add_chat_history(self, customer_id: int, content: str,
                        source_type: str = 'manual', source_file: str = None) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO chat_histories (customer_id, content, source_type, source_file)
               VALUES (?, ?, ?, ?)""",
            (customer_id, content, source_type, source_file)
        )
        chat_id = cursor.lastrowid
        cursor.execute(
            "UPDATE customers SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (customer_id,)
        )
        conn.commit()
        conn.close()
        return chat_id

    def get_chat_histories(self, customer_id: int, limit: int = None):
        conn = self._get_connection()
        cursor = conn.cursor()
        query = """SELECT * FROM chat_histories WHERE customer_id = ? ORDER BY created_at DESC"""
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query, (customer_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_all_chat_content(self, customer_id: int) -> str:
        histories = self.get_chat_histories(customer_id)
        if not histories:
            return ""
        contents = []
        for h in reversed(histories):
            time_str = h['created_at']
            contents.append(f"=== {time_str} ===\n{h['content']}")
        return "\n\n".join(contents)

    def save_analysis(self, customer_id: int, analysis_type: str,
                     result: dict, chat_summary: str = None) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO analysis_histories (customer_id, analysis_type, result, chat_summary)
               VALUES (?, ?, ?, ?)""",
            (customer_id, analysis_type, json.dumps(result, ensure_ascii=False), chat_summary)
        )
        analysis_id = cursor.lastrowid
        cursor.execute(
            "UPDATE customers SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (customer_id,)
        )
        conn.commit()
        conn.close()
        return analysis_id

    def get_analysis_histories(self, customer_id: int, analysis_type: str = None):
        conn = self._get_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM analysis_histories WHERE customer_id = ?"
        params = [customer_id]
        if analysis_type:
            query += " AND analysis_type = ?"
            params.append(analysis_type)
        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        results = []
        for row in rows:
            row_dict = dict(row)
            try:
                row_dict['result'] = json.loads(row_dict['result'])
            except:
                pass
            results.append(row_dict)
        conn.close()
        return results

    def save_profile(self, customer_id: int, profile_data: dict) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO customer_profiles (customer_id, profile_data)
               VALUES (?, ?)""",
            (customer_id, json.dumps(profile_data, ensure_ascii=False))
        )
        profile_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return profile_id

    def get_latest_profile(self, customer_id: int):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM customer_profiles WHERE customer_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (customer_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        row_dict = dict(row)
        try:
            row_dict['profile_data'] = json.loads(row_dict['profile_data'])
        except:
            pass
        return row_dict

    def get_statistics(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        stats = {}
        cursor.execute("SELECT COUNT(*) as count FROM customers")
        stats['total_customers'] = cursor.fetchone()['count']
        cursor.execute("""SELECT COUNT(*) as count FROM customers WHERE DATE(created_at) = DATE('now')""")
        stats['today_new'] = cursor.fetchone()['count']
        cursor.execute("""SELECT COUNT(DISTINCT customer_id) as count FROM (
            SELECT customer_id FROM chat_histories WHERE DATE(created_at) >= DATE('now', '-7 days')
            UNION SELECT customer_id FROM analysis_histories WHERE DATE(created_at) >= DATE('now', '-7 days')
        )""")
        stats['weekly_active'] = cursor.fetchone()['count']
        cursor.execute("""SELECT industry, COUNT(*) as count FROM customers WHERE industry IS NOT NULL GROUP BY industry ORDER BY count DESC""")
        stats['by_industry'] = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return stats

db = Database()
