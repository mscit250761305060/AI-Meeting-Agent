import sqlite3
import os

DATABASE_NAME = 'employee_management.db'

def get_db_connection():
    """Establishes and returns a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        conn.row_factory = sqlite3.Row  # This allows accessing columns by name
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None

def close_db_connection(conn):
    """Closes the given database connection."""
    if conn:
        conn.close()

def create_tables():
    """Creates necessary tables in the database if they don't already exist."""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    position TEXT,
                    salary REAL,
                    email TEXT UNIQUE,
                    phone TEXT
                )
            ''')
            conn.commit()
            print("Tables created or already exist.")
        except sqlite3.Error as e:
            print(f"Error creating tables: {e}")
        finally:
            close_db_connection(conn)

def init_db():
    """Initializes the database by creating tables."""
    create_tables()

if __name__ == '__main__':
    # This block is for demonstration/testing purposes
    print(f"Initializing database: {DATABASE_NAME}")
    init_db()

    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()

            # Example: Add an employee if the table is empty
            cursor.execute("SELECT COUNT(*) FROM employees")
            if cursor.fetchone()[0] == 0:
                print("Adding sample employee...")
                cursor.execute(
                    "INSERT INTO employees (name, position, salary, email, phone) VALUES (?, ?, ?, ?, ?)",
                    ('Alice Smith', 'Software Engineer', 75000.00, 'alice.smith@example.com', '555-1234')
                )
                conn.commit()
                print("Sample employee added.")
            else:
                print("Employees table is not empty, skipping sample data insertion.")

            # Example: Fetch all employees
            print("\nCurrent Employees:")
            cursor.execute("SELECT id, name, position, salary, email, phone FROM employees")
            employees = cursor.fetchall()
            if employees:
                for emp in employees:
                    print(f"ID: {emp['id']}, Name: {emp['name']}, Position: {emp['position']}, Salary: {emp['salary']}, Email: {emp['email']}, Phone: {emp['phone']}")
            else:
                print("No employees found.")

        except sqlite3.Error as e:
            print(f"Error during example operations: {e}")
        finally:
            close_db_connection(conn)