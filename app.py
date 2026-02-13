from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import psycopg2
import psycopg2.extras
import pandas as pd
import os
import json
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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
    
    # Convert quantity and rate if available
    if detected_cols["qty"]:
        df[detected_cols["qty"]] = pd.to_numeric(df[detected_cols["qty"]], errors="coerce")
    if detected_cols["rate"]:
        df[detected_cols["rate"]] = pd.to_numeric(df[detected_cols["rate"]], errors="coerce")
    
    # Remove rows with invalid dates or amounts
    df_clean = df.dropna(subset=[detected_cols["date"], detected_cols["amount"]])
    
    if len(df_clean) == 0:
        return None
    
    # Get today's date
    today = datetime.now().date()
    
    # Calculate date ranges
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)
    last_60_days = today - timedelta(days=60)
    
    # Convert date column to date for comparison
    df_clean["date_only"] = df_clean[detected_cols["date"]].dt.date
    df_clean["month"] = df_clean[detected_cols["date"]].dt.to_period("M")
    df_clean["day_of_week"] = df_clean[detected_cols["date"]].dt.day_name()
    
    # Total sales
    total_sales = float(df_clean[detected_cols["amount"]].sum())
    
    # Last 7 days sales
    df_last_7 = df_clean[df_clean["date_only"] >= last_7_days]
    last_7_days_sales = float(df_last_7[detected_cols["amount"]].sum())
    
    # Last 30 days sales
    df_last_30 = df_clean[df_clean["date_only"] >= last_30_days]
    last_30_days_sales = float(df_last_30[detected_cols["amount"]].sum())
    
    # Last 60 days sales (for growth calculation)
    df_last_60 = df_clean[df_clean["date_only"] >= last_60_days]
    last_60_days_sales = float(df_last_60[detected_cols["amount"]].sum())
    
    # Average sales per day (last 7 days)
    if len(df_last_7) > 0:
        unique_days_week = df_last_7["date_only"].nunique()
        avg_sales_per_day_week = last_7_days_sales / unique_days_week if unique_days_week > 0 else 0
    else:
        avg_sales_per_day_week = 0
    
    # Average sales per day (last 30 days)
    if len(df_last_30) > 0:
        unique_days_month = df_last_30["date_only"].nunique()
        avg_sales_per_day_month = last_30_days_sales / unique_days_month if unique_days_month > 0 else 0
    else:
        avg_sales_per_day_month = 0
    
    # Growth rate (last 7 days vs previous 7 days)
    df_prev_7 = df_clean[(df_clean["date_only"] >= last_7_days - timedelta(days=7)) & 
                         (df_clean["date_only"] < last_7_days)]
    prev_7_days_sales = float(df_prev_7[detected_cols["amount"]].sum()) if len(df_prev_7) > 0 else 0
    growth_rate_week = ((last_7_days_sales - prev_7_days_sales) / prev_7_days_sales * 100) if prev_7_days_sales > 0 else 0
    
    # Growth rate (last 30 days vs previous 30 days)
    df_prev_30 = df_clean[(df_clean["date_only"] >= last_30_days - timedelta(days=30)) & 
                          (df_clean["date_only"] < last_30_days)]
    prev_30_days_sales = float(df_prev_30[detected_cols["amount"]].sum()) if len(df_prev_30) > 0 else 0
    growth_rate_month = ((last_30_days_sales - prev_30_days_sales) / prev_30_days_sales * 100) if prev_30_days_sales > 0 else 0
    
    # Best selling products (if item column exists)
    top_products = []
    if detected_cols["item"]:
        product_sales = df_clean.groupby(detected_cols["item"])[detected_cols["amount"]].sum().sort_values(ascending=False).head(10)
        top_products = [{"name": str(name), "sales": float(sales)} for name, sales in product_sales.items()]
    
    # Monthly sales trend
    monthly_sales = df_clean.groupby("month")[detected_cols["amount"]].sum()
    monthly_data = [{"month": str(month), "sales": float(sales)} for month, sales in monthly_sales.items()]
    
    # Daily sales trend (last 30 days)
    daily_sales = df_last_30.groupby("date_only")[detected_cols["amount"]].sum().sort_index()
    daily_data = [{"date": str(date), "sales": float(sales)} for date, sales in daily_sales.items()]
    
    # Day of week analysis
    day_of_week_sales = df_clean.groupby("day_of_week")[detected_cols["amount"]].sum()
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_of_week_data = [{"day": day, "sales": float(day_of_week_sales.get(day, 0))} for day in day_order]
    
    # Peak sales day
    peak_day = day_of_week_sales.idxmax() if len(day_of_week_sales) > 0 else None
    
    # Average transaction value
    avg_transaction_value = total_sales / len(df_clean) if len(df_clean) > 0 else 0
    
    # Total quantity sold (if available)
    total_quantity = float(df_clean[detected_cols["qty"]].sum()) if detected_cols["qty"] and not df_clean[detected_cols["qty"]].isna().all() else None
    
    return {
        "total_sales": round(total_sales, 2),
        "last_7_days_sales": round(last_7_days_sales, 2),
        "last_30_days_sales": round(last_30_days_sales, 2),
        "avg_sales_per_day_week": round(avg_sales_per_day_week, 2),
        "avg_sales_per_day_month": round(avg_sales_per_day_month, 2),
        "total_records": len(df_clean),
        "growth_rate_week": round(growth_rate_week, 2),
        "growth_rate_month": round(growth_rate_month, 2),
        "top_products": top_products,
        "monthly_data": monthly_data,
        "daily_data": daily_data,
        "day_of_week_data": day_of_week_data,
        "peak_day": peak_day,
        "avg_transaction_value": round(avg_transaction_value, 2),
        "total_quantity": round(total_quantity, 2) if total_quantity else None
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
        
        # Prepare additional metrics JSON
        additional_metrics = {
            "top_products": analysis_results.get("top_products", []),
            "monthly_data": analysis_results.get("monthly_data", []),
            "daily_data": analysis_results.get("daily_data", []),
            "day_of_week_data": analysis_results.get("day_of_week_data", [])
        }
        
        cur.execute("""
            INSERT INTO analyses (
                user_id, filename, date_column, item_column, qty_column, 
                rate_column, amount_column, total_sales, last_7_days_sales,
                last_30_days_sales, avg_sales_per_day_week, avg_sales_per_day_month,
                total_records, growth_rate_week, growth_rate_month, 
                avg_transaction_value, peak_day, total_quantity, additional_metrics
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            user_id, filename, detected_cols["date"], detected_cols["item"],
            detected_cols["qty"], detected_cols["rate"], detected_cols["amount"],
            analysis_results["total_sales"], analysis_results["last_7_days_sales"],
            analysis_results["last_30_days_sales"], analysis_results["avg_sales_per_day_week"],
            analysis_results["avg_sales_per_day_month"], analysis_results["total_records"],
            analysis_results.get("growth_rate_week", 0), analysis_results.get("growth_rate_month", 0),
            analysis_results.get("avg_transaction_value", 0), analysis_results.get("peak_day"),
            analysis_results.get("total_quantity"), json.dumps(additional_metrics)
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
    
    # Parse additional_metrics JSON if it exists
    if analysis.get("additional_metrics"):
        try:
            if isinstance(analysis["additional_metrics"], str):
                analysis["additional_metrics"] = json.loads(analysis["additional_metrics"])
        except:
            analysis["additional_metrics"] = {}
    else:
        analysis["additional_metrics"] = {}
    
    return render_template("results.html", analysis=analysis)


@app.route("/export_pdf/<int:analysis_id>")
def export_pdf(analysis_id):
    # Check if user is logged in
    if "user_id" not in session:
        flash("Please log in to export reports.", "error")
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    
    # Get analysis from database
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
        SELECT a.*, u.name as user_name, u.email as user_email
        FROM analyses a
        JOIN users u ON a.user_id = u.id
        WHERE a.id = %s AND a.user_id = %s
    """, (analysis_id, user_id))
    
    analysis = cur.fetchone()
    cur.close()
    conn.close()
    
    if not analysis:
        flash("Analysis not found.", "error")
        return redirect(url_for("index"))
    
    # Parse additional_metrics JSON if it exists
    if analysis.get("additional_metrics"):
        try:
            if isinstance(analysis["additional_metrics"], str):
                additional_metrics = json.loads(analysis["additional_metrics"])
            else:
                additional_metrics = analysis["additional_metrics"]
        except:
            additional_metrics = {}
    else:
        additional_metrics = {}
    
    # Create PDF
    buffer = os.path.join(app.config["UPLOAD_FOLDER"], f"report_{analysis_id}.pdf")
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#1e40af"),
        spaceAfter=30,
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=16,
        textColor=colors.HexColor("#374151"),
        spaceAfter=12,
    )
    
    # Title
    story.append(Paragraph("Smart Sales Data Analysis System", title_style))
    story.append(Paragraph("Sales Analysis Report", styles["Heading2"]))
    story.append(Spacer(1, 12))
    
    # Report Info
    report_data = [
        ["Report Generated On:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["File Analyzed:", analysis["filename"]],
        ["Uploaded On:", analysis["uploaded_at"].strftime("%Y-%m-%d %H:%M:%S") if analysis["uploaded_at"] else "N/A"],
        ["Total Records:", str(analysis["total_records"])],
    ]
    report_table = Table(report_data, colWidths=[3*inch, 4*inch])
    report_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(report_table)
    story.append(Spacer(1, 20))
    
    # Sales Metrics
    story.append(Paragraph("Sales Metrics", heading_style))
    metrics_data = [
        ["Metric", "Value"],
        ["Total Sales", f"₹{analysis['total_sales']:,.2f}"],
        ["Last 7 Days Sales", f"₹{analysis['last_7_days_sales']:,.2f}"],
        ["Last 30 Days Sales", f"₹{analysis['last_30_days_sales']:,.2f}"],
        ["Avg Sales/Day (Week)", f"₹{analysis['avg_sales_per_day_week']:,.2f}"],
        ["Avg Sales/Day (Month)", f"₹{analysis['avg_sales_per_day_month']:,.2f}"],
    ]
    
    if analysis.get("growth_rate_week") is not None:
        metrics_data.append(["Growth Rate (Week)", f"{analysis['growth_rate_week']:.2f}%"])
    if analysis.get("growth_rate_month") is not None:
        metrics_data.append(["Growth Rate (Month)", f"{analysis['growth_rate_month']:.2f}%"])
    if analysis.get("avg_transaction_value"):
        metrics_data.append(["Avg Transaction Value", f"₹{analysis['avg_transaction_value']:,.2f}"])
    if analysis.get("peak_day"):
        metrics_data.append(["Peak Sales Day", str(analysis["peak_day"])])
    if analysis.get("total_quantity"):
        metrics_data.append(["Total Quantity Sold", f"{analysis['total_quantity']:,.2f}"])
    
    metrics_table = Table(metrics_data, colWidths=[3*inch, 4*inch])
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 20))
    
    # Top Products
    if additional_metrics.get("top_products"):
        story.append(Paragraph("Top Selling Products", heading_style))
        products_data = [["Rank", "Product", "Sales"]]
        for idx, product in enumerate(additional_metrics["top_products"][:10], 1):
            products_data.append([str(idx), product["name"], f"₹{product['sales']:,.2f}"])
        
        products_table = Table(products_data, colWidths=[0.8*inch, 4*inch, 2.2*inch])
        products_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ]))
        story.append(products_table)
        story.append(Spacer(1, 20))
    
    # Detected Columns
    story.append(Paragraph("Detected Columns", heading_style))
    columns_data = [
        ["Column Type", "Detected Name"],
        ["Date", analysis["date_column"] or "Not detected"],
        ["Item", analysis["item_column"] or "Not detected"],
        ["Quantity", analysis["qty_column"] or "Not detected"],
        ["Rate", analysis["rate_column"] or "Not detected"],
        ["Amount", analysis["amount_column"] or "Not detected"],
    ]
    columns_table = Table(columns_data, colWidths=[3*inch, 4*inch])
    columns_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(columns_table)
    
    # Build PDF
    doc.build(story)
    
    return send_file(buffer, as_attachment=True, download_name=f"SSDAS_Report_{analysis_id}.pdf")


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