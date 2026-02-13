from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import psycopg2
import psycopg2.extras
import pandas as pd
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "change_this_secret_key"  # put a strong random string here

# Create uploads directory if it doesn't exist
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def get_db():
    return psycopg2.connect(
        dbname="ssdas",
        user="postgres",
        password="password",
        host="localhost",
        port=5432,
    )


# ---------- AUTH HELPERS ----------

def get_user_by_email(email):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


# ---------- ANALYSIS HELPERS ----------

def detect_columns(df):
    """Detect date, item name, quantity, rate, and amount columns"""
    columns = {
        "date": None,
        "item": None,
        "qty": None,
        "rate": None,
        "amount": None
    }
    
    # Convert column names to lowercase for matching
    col_lower = {col.lower(): col for col in df.columns}
    
    # Date column detection
    date_keywords = ["date", "datetime", "order_date", "sale_date", "transaction_date", "time"]
    for keyword in date_keywords:
        for col_low, col_orig in col_lower.items():
            if keyword in col_low:
                columns["date"] = col_orig
                break
        if columns["date"]:
            break
    
    # Item/Product column detection
    item_keywords = ["item", "product", "name", "item_name", "product_name", "description"]
    for keyword in item_keywords:
        for col_low, col_orig in col_lower.items():
            if keyword in col_low:
                columns["item"] = col_orig
                break
        if columns["item"]:
            break
    
    # Quantity column detection
    qty_keywords = ["qty", "quantity", "units", "count", "qty_sold"]
    for keyword in qty_keywords:
        for col_low, col_orig in col_lower.items():
            if keyword in col_low:
                columns["qty"] = col_orig
                break
        if columns["qty"]:
            break
    
    # Rate/Price column detection
    rate_keywords = ["rate", "price", "unit_price", "cost", "unit_cost"]
    for keyword in rate_keywords:
        for col_low, col_orig in col_lower.items():
            if keyword in col_low:
                columns["rate"] = col_orig
                break
        if columns["rate"]:
            break
    
    # Amount/Total column detection
    amount_keywords = ["amount", "total", "sales", "revenue", "value", "total_amount", "sales_amount"]
    for keyword in amount_keywords:
        for col_low, col_orig in col_lower.items():
            if keyword in col_low:
                columns["amount"] = col_orig
                break
        if columns["amount"]:
            break
    
    return columns


def analyze_sales_data(df, detected_cols):
    """Analyze sales data and calculate metrics"""
    if not detected_cols["date"] or not detected_cols["amount"]:
        return None
    
    # Convert date column to datetime
    try:
        df[detected_cols["date"]] = pd.to_datetime(df[detected_cols["date"]], errors="coerce")
    except:
        return None
    
    # Convert amount to numeric
    df[detected_cols["amount"]] = pd.to_numeric(df[detected_cols["amount"]], errors="coerce")
    
    # Remove rows with invalid dates or amounts
    df_clean = df.dropna(subset=[detected_cols["date"], detected_cols["amount"]])
    
    if len(df_clean) == 0:
        return None
    
    # Get today's date
    today = datetime.now().date()
    
    # Calculate date ranges
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)
    
    # Convert date column to date for comparison
    df_clean["date_only"] = df_clean[detected_cols["date"]].dt.date
    
    # Total sales
    total_sales = float(df_clean[detected_cols["amount"]].sum())
    
    # Last 7 days sales
    df_last_7 = df_clean[df_clean["date_only"] >= last_7_days]
    last_7_days_sales = float(df_last_7[detected_cols["amount"]].sum())
    
    # Last 30 days sales
    df_last_30 = df_clean[df_clean["date_only"] >= last_30_days]
    last_30_days_sales = float(df_last_30[detected_cols["amount"]].sum())
    
    # Average sales per day (last 7 days)
    days_in_week = 7
    if len(df_last_7) > 0:
        unique_days_week = df_last_7["date_only"].nunique()
        avg_sales_per_day_week = last_7_days_sales / unique_days_week if unique_days_week > 0 else 0
    else:
        avg_sales_per_day_week = 0
    
    # Average sales per day (last 30 days)
    days_in_month = 30
    if len(df_last_30) > 0:
        unique_days_month = df_last_30["date_only"].nunique()
        avg_sales_per_day_month = last_30_days_sales / unique_days_month if unique_days_month > 0 else 0
    else:
        avg_sales_per_day_month = 0
    
    return {
        "total_sales": round(total_sales, 2),
        "last_7_days_sales": round(last_7_days_sales, 2),
        "last_30_days_sales": round(last_30_days_sales, 2),
        "avg_sales_per_day_week": round(avg_sales_per_day_week, 2),
        "avg_sales_per_day_month": round(avg_sales_per_day_month, 2),
        "total_records": len(df_clean)
    }


# ---------- ROUTES ----------

@app.route("/")
def index():
    user = None
    if "user_id" in session:
        user = get_user_by_id(session["user_id"])
    return render_template("index.html", user=user)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Basic validations
        if not name or not email or not password or not confirm_password:
            flash("All fields are required.", "error")
            return redirect(url_for("register"))

        if not email.endswith("@gmail.com"):
            flash("Only Gmail addresses are allowed (must end with @gmail.com).", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        # Check if email already exists
        if get_user_by_email(email) is not None:
            flash("This email is already registered. Please log in.", "error")
            return redirect(url_for("login"))

        # Create user
        password_hash = generate_password_hash(password)

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
            (name, email, password_hash),
        )
        conn.commit()
        cur.close()
        conn.close()

        flash("Signup successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = get_user_by_email(email)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        # Save user in session
        session["user_id"] = user["id"]
        flash("Logged in successfully.", "success")
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/upload", methods=["POST"])
def upload():
    # Check if user is logged in
    if "user_id" not in session:
        flash("Please log in to upload files.", "error")
        return redirect(url_for("login"))
    
    if "file" not in request.files:
        flash("No file part.", "error")
        return redirect(url_for("index"))

    file = request.files["file"]
    if file.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("index"))

    if not (file.filename.endswith(".csv") or file.filename.endswith(".xlsx")):
        flash("Only .csv or .xlsx files are allowed.", "error")
        return redirect(url_for("index"))

    try:
        # Save file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)
        
        # Read file with pandas
        if filename.endswith(".csv"):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        # Detect columns
        detected_cols = detect_columns(df)
        
        if not detected_cols["date"] or not detected_cols["amount"]:
            flash("Could not detect required columns (Date and Amount). Please check your file format.", "error")
            os.remove(filepath)
            return redirect(url_for("index"))
        
        # Analyze data
        analysis_results = analyze_sales_data(df, detected_cols)
        
        if not analysis_results:
            flash("Error analyzing data. Please check your file format.", "error")
            os.remove(filepath)
            return redirect(url_for("index"))
        
        # Store analysis in database
        user_id = session["user_id"]
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO analyses (
                user_id, filename, date_column, item_column, qty_column, 
                rate_column, amount_column, total_sales, last_7_days_sales,
                last_30_days_sales, avg_sales_per_day_week, avg_sales_per_day_month,
                total_records
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            user_id, filename, detected_cols["date"], detected_cols["item"],
            detected_cols["qty"], detected_cols["rate"], detected_cols["amount"],
            analysis_results["total_sales"], analysis_results["last_7_days_sales"],
            analysis_results["last_30_days_sales"], analysis_results["avg_sales_per_day_week"],
            analysis_results["avg_sales_per_day_month"], analysis_results["total_records"]
        ))
        
        analysis_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        # Clean up uploaded file (optional - you can keep it if needed)
        # os.remove(filepath)
        
        # Redirect to results page
        return redirect(url_for("results", analysis_id=analysis_id))
        
    except Exception as e:
        flash(f"Error processing file: {str(e)}", "error")
        if os.path.exists(filepath):
            os.remove(filepath)
        return redirect(url_for("index"))


@app.route("/results/<int:analysis_id>")
def results(analysis_id):
    # Check if user is logged in
    if "user_id" not in session:
        flash("Please log in to view results.", "error")
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    
    # Get analysis from database
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
        SELECT * FROM analyses 
        WHERE id = %s AND user_id = %s
    """, (analysis_id, user_id))
    
    analysis = cur.fetchone()
    cur.close()
    conn.close()
    
    if not analysis:
        flash("Analysis not found or you don't have permission to view it.", "error")
        return redirect(url_for("index"))
    
    return render_template("results.html", analysis=analysis)


@app.route("/history")
def history():
    # Check if user is logged in
    if "user_id" not in session:
        flash("Please log in to view history.", "error")
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    
    # Get all analyses for this user
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
        SELECT * FROM analyses 
        WHERE user_id = %s 
        ORDER BY uploaded_at DESC
    """, (user_id,))
    
    analyses = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template("history.html", analyses=analyses)


if __name__ == "__main__":
    app.run(debug=True)