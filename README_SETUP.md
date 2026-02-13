# SSDAS Setup Guide

## Step 1: Install PostgreSQL
Make sure PostgreSQL is installed and running on your system.

## Step 2: Create Database and Table

### Option A: Using psql (Command Line)
1. Open Command Prompt or PowerShell
2. Run: `psql -U postgres`
3. Enter your PostgreSQL password when prompted
4. Copy and paste the contents of `setup_database.sql` into psql
5. Or run: `psql -U postgres -f setup_database.sql`

### Option B: Using pgAdmin
1. Open pgAdmin
2. Connect to your PostgreSQL server
3. Right-click on "Databases" → Create → Database
4. Name it: `ssdass`
5. Open Query Tool
6. Run this SQL:
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Step 3: Update Database Connection in app.py

Edit `app.py` and update the `get_db()` function with your PostgreSQL credentials:

```python
def get_db():
    return psycopg2.connect(
        dbname="ssdass",
        user="postgres",           # Your PostgreSQL username
        password="YOUR_PASSWORD",  # Your PostgreSQL password
        host="localhost",
        port=5432,
    )
```

## Step 4: Run the Application

```bash
python app.py
```

The app will run on: http://127.0.0.1:5000

## Step 5: Test the Application

1. Open http://127.0.0.1:5000 in your browser
2. Click "Sign Up" (top left)
3. Fill in:
   - Name: Your Name
   - Email: something@gmail.com (must end with @gmail.com)
   - Password: your password
   - Confirm Password: same password
4. After signup, you'll be redirected to login
5. Login with your email and password
6. You should see "Hello, Your Name!" in the top left
7. Try uploading a .csv or .xlsx file (analysis logic will be added later)

## Troubleshooting

### Database Connection Error
- Make sure PostgreSQL is running
- Check your password in `app.py`
- Verify database `ssdass` exists
- Verify `users` table exists

### Port Already in Use
- Change port in `app.py`: `app.run(debug=True, port=5001)`
