import sqlite3

def migrate():
    conn = sqlite3.connect('sql_app.db')
    cursor = conn.cursor()
    
    # Tables to update and columns to add
    migrations = [
        ('database_schemas', 'code', 'TEXT'),
        ('api_endpoints', 'code', 'TEXT'),
        ('ui_components', 'code', 'TEXT'),
        ('projects', 'project_type', 'TEXT'),
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
    
    # Create new tables
    try:
        print("Creating 'dismissed_recommendations' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dismissed_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                recommendation_id TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                UNIQUE(project_id, recommendation_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_dismissed_rec_id ON dismissed_recommendations(recommendation_id)")
        print("Done.")
    except Exception as e:
        print(f"Error creating dismissed_recommendations: {e}")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
