
from flask import Flask, render_template, request, redirect, url_for, flash, Response
import sqlite3
import csv
import io
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
app.secret_key = "student-feedback-project"
DB_PATH = Path(__file__).resolve().parent / "feedback.db"

RATING_FIELDS = [
    "teaching", "clarity", "interaction", "punctuality", "facilities"
]

RATING_LABELS = {
    "teaching": "Teaching Quality",
    "clarity": "Subject Clarity",
    "interaction": "Faculty Interaction",
    "punctuality": "Punctuality",
    "facilities": "Learning Facilities"
}

POSITIVE_WORDS = {
    "good", "great", "excellent", "helpful", "clear", "wonderful",
    "friendly", "amazing", "best", "nice", "supportive", "interesting"
}

NEGATIVE_WORDS = {
    "bad", "poor", "boring", "unclear", "confusing", "worst",
    "terrible", "slow", "problem", "difficult", "late", "weak"
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                roll_number TEXT NOT NULL,
                department TEXT NOT NULL,
                year TEXT NOT NULL,
                subject TEXT NOT NULL,
                faculty TEXT NOT NULL,
                teaching INTEGER NOT NULL,
                clarity INTEGER NOT NULL,
                interaction INTEGER NOT NULL,
                punctuality INTEGER NOT NULL,
                facilities INTEGER NOT NULL,
                comments TEXT,
                sentiment TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def analyze_sentiment(comment):
    words = set(
        "".join(c.lower() if c.isalnum() else " " for c in comment).split()
    )
    positive = len(words & POSITIVE_WORDS)
    negative = len(words & NEGATIVE_WORDS)

    if positive > negative:
        return "Positive"
    if negative > positive:
        return "Negative"
    return "Neutral"


def get_filters():
    return {
        "department": request.args.get("department", "").strip(),
        "year": request.args.get("year", "").strip(),
        "subject": request.args.get("subject", "").strip(),
        "sentiment": request.args.get("sentiment", "").strip(),
        "search": request.args.get("search", "").strip()
    }


def fetch_feedback(filters=None):
    sql = "SELECT * FROM feedback WHERE 1=1"
    params = []

    if filters:
        for key in ["department", "year", "subject", "sentiment"]:
            if filters.get(key):
                sql += f" AND {key} = ?"
                params.append(filters[key])

        if filters.get("search"):
            sql += """ AND (
                student_name LIKE ? OR roll_number LIKE ?
                OR faculty LIKE ? OR comments LIKE ?
            )"""
            pattern = "%" + filters["search"] + "%"
            params.extend([pattern] * 4)

    sql += " ORDER BY id DESC"

    with get_db() as conn:
        return conn.execute(sql, params).fetchall()


def build_insights(total, average, rating_values, sentiments):
    if total == 0:
        return ["Submit feedback to unlock your first insights."]

    insights = []

    if average >= 4.2:
        insights.append(
            "Overall satisfaction is strong. Continue the practices students value."
        )
    elif average >= 3.3:
        insights.append(
            "Overall satisfaction is moderate. Review the lowest-rated category."
        )
    else:
        insights.append(
            "Overall satisfaction needs attention. Plan targeted improvements."
        )

    if rating_values:
        lowest = min(rating_values, key=lambda item: item["score"])
        highest = max(rating_values, key=lambda item: item["score"])

        insights.append(
            f"Improvement opportunity: {lowest['label']} averages "
            f"{lowest['score']:.2f}/5."
        )
        insights.append(
            f"Strongest category: {highest['label']} averages "
            f"{highest['score']:.2f}/5."
        )

    if sentiments["Negative"]:
        insights.append(
            f"Review the {sentiments['Negative']} comment(s) classified as "
            "negative to identify recurring concerns."
        )

    return insights[:4]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/submit", methods=["POST"])
def submit():
    fields = [
        "student_name", "roll_number", "department",
        "year", "subject", "faculty"
    ]
    data = {
        field: request.form.get(field, "").strip()
        for field in fields
    }
    comments = request.form.get("comments", "").strip()

    if any(not value for value in data.values()):
        flash("Please complete all student details.", "error")
        return redirect(url_for("index"))

    if len(comments) > 2000:
        flash("Comments cannot exceed 2,000 characters.", "error")
        return redirect(url_for("index"))

    ratings = {}
    try:
        for field in RATING_FIELDS:
            value = int(request.form.get(field, ""))
            if value not in range(1, 6):
                raise ValueError
            ratings[field] = value
    except ValueError:
        flash("Please rate every category from 1 to 5.", "error")
        return redirect(url_for("index"))

    with get_db() as conn:
        conn.execute("""
            INSERT INTO feedback (
                student_name, roll_number, department, year,
                subject, faculty, teaching, clarity, interaction,
                punctuality, facilities, comments, sentiment, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["student_name"], data["roll_number"],
            data["department"], data["year"], data["subject"],
            data["faculty"], ratings["teaching"], ratings["clarity"],
            ratings["interaction"], ratings["punctuality"],
            ratings["facilities"], comments, analyze_sentiment(comments),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    flash("Feedback submitted successfully!", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    filters = get_filters()
    rows = fetch_feedback(filters)
    total = len(rows)

    average = round(
        sum(
            sum(row[field] for field in RATING_FIELDS) / len(RATING_FIELDS)
            for row in rows
        ) / total, 2
    ) if total else 0

    sentiments = {"Positive": 0, "Neutral": 0, "Negative": 0}
    for row in rows:
        sentiments[row["sentiment"]] += 1

    rating_values = []
    for field in RATING_FIELDS:
        score = round(
            sum(row[field] for row in rows) / total, 2
        ) if total else 0
        rating_values.append({
            "label": RATING_LABELS[field],
            "score": score
        })

    department_counts = {}
    daily_counts = {}

    for row in rows:
        department = row["department"]
        day = row["created_at"][:10]
        department_counts[department] = department_counts.get(department, 0) + 1
        daily_counts[day] = daily_counts.get(day, 0) + 1

    all_rows = fetch_feedback()
    departments = sorted({row["department"] for row in all_rows})
    years = sorted({row["year"] for row in all_rows})
    subjects = sorted({row["subject"] for row in all_rows})

    return render_template(
        "dashboard.html",
        filters=filters,
        total=total,
        average=average,
        sentiment_counts=sentiments,
        rating_values=rating_values,
        rating_labels=[item["label"] for item in rating_values],
        rating_scores=[item["score"] for item in rating_values],
        insights=build_insights(total, average, rating_values, sentiments),
        dept_labels=list(department_counts.keys()),
        dept_values=list(department_counts.values()),
        trend_labels=sorted(daily_counts.keys()),
        trend_values=[daily_counts[key] for key in sorted(daily_counts)],
        departments=departments,
        years=years,
        subjects=subjects,
        recent=rows[:5]
    )


@app.route("/history")
def history():
    filters = get_filters()
    rows = fetch_feedback(filters)

    all_rows = fetch_feedback()
    departments = sorted({row["department"] for row in all_rows})
    years = sorted({row["year"] for row in all_rows})
    subjects = sorted({row["subject"] for row in all_rows})

    return render_template(
        "history.html",
        feedback=rows,
        filters=filters,
        departments=departments,
        years=years,
        subjects=subjects
    )


@app.route("/export.csv")
def export_csv():
    rows = fetch_feedback(get_filters())
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Date", "Student", "Roll Number", "Department", "Year",
        "Subject", "Faculty", "Teaching", "Clarity", "Interaction",
        "Punctuality", "Facilities", "Comments", "Sentiment"
    ])

    for row in rows:
        writer.writerow([
            row["created_at"], row["student_name"], row["roll_number"],
            row["department"], row["year"], row["subject"], row["faculty"],
            row["teaching"], row["clarity"], row["interaction"],
            row["punctuality"], row["facilities"], row["comments"],
            row["sentiment"]
        ])

    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=student_feedback_export.csv"
        }
    )


init_db()

if __name__ == "__main__":
    app.run(debug=True)
