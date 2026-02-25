import sqlite3

def migrate():
    conn = sqlite3.connect('sql_app.db')
    cursor = conn.cursor()
    
    # Tables to update and columns to add
    migrations = [
        ('database_schemas', 'code', 'TEXT'),
        ('api_endpoints', 'code', 'TEXT'),
        ('ui_components', 'code', 'TEXT')
    ]
    
    for table, column, col_type in migrations:
        try:
            print(f"Adding column '{column}' to '{table}'...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            print("Done.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"Column '{column}' already exists in '{table}'. skipping.")
            else:
                print(f"Error adding column to {table}: {e}")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
