
from flask import Flask, request, jsonify, render_template
import sqlite3
from datetime import datetime

app = Flask(__name__)

DATABASE = "smart_bins.db"


# ---------- DATABASE SETUP ----------

def get_db():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def current_time():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def get_status(fill):
    if fill >= 90:
        return "CRITICAL"
    elif fill >= 70:
        return "HIGH"
    return "NORMAL"


def initialize_database():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bins (
                bin_id TEXT PRIMARY KEY,
                fill REAL NOT NULL,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_collected TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS collection_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bin_id TEXT NOT NULL,
                fill_before REAL NOT NULL,
                collected_at TEXT NOT NULL
            )
        """)


# Create the database tables when the application starts.
initialize_database()


# ---------- HOME PAGE ----------

@app.route("/")
def home():
    return "Smart Bin Backend is Running!"


# ---------- RECEIVE BIN READINGS ----------

@app.route("/api/bin", methods=["POST"])
def update_bin():
    data = request.get_json(silent=True) or {}

    bin_id = str(data.get("bin_id", "")).strip()
    fill = data.get("fill")

    if not bin_id or fill is None:
        return jsonify({
            "error": "bin_id and fill are required"
        }), 400

    try:
        fill = float(fill)
    except (TypeError, ValueError):
        return jsonify({"error": "fill must be a number"}), 400

    if not 0 <= fill <= 100:
        return jsonify({
            "error": "fill must be between 0 and 100"
        }), 400

    status = get_status(fill)
    now = current_time()

    with get_db() as conn:
        conn.execute("""
            INSERT INTO bins (
                bin_id, fill, status, updated_at, last_collected
            )
            VALUES (?, ?, ?, ?, NULL)
            ON CONFLICT(bin_id) DO UPDATE SET
                fill = excluded.fill,
                status = excluded.status,
                updated_at = excluded.updated_at
        """, (bin_id, fill, status, now))

    return jsonify({
        "message": "Bin updated successfully",
        "bin": {
            "bin_id": bin_id,
            "fill": fill,
            "status": status,
            "updated_at": now
        }
    })


# ---------- GET ALL BINS ----------

@app.route("/api/bins")
def get_bins():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT bin_id, fill, status, updated_at, last_collected
            FROM bins
        """).fetchall()

    result = [dict(row) for row in rows]

    priority_order = {
        "CRITICAL": 1,
        "HIGH": 2,
        "NORMAL": 3
    }

    result.sort(key=lambda b: (
        priority_order[b["status"]],
        -b["fill"]
    ))

    for index, bin_data in enumerate(result, start=1):
        bin_data["priority"] = index

    return jsonify(result)


# ---------- MARK A BIN AS COLLECTED ----------

@app.route("/api/collect", methods=["POST"])
def collect_bin():
    data = request.get_json(silent=True) or {}
    bin_id = str(data.get("bin_id", "")).strip()

    if not bin_id:
        return jsonify({"error": "bin_id is required"}), 400

    now = current_time()

    with get_db() as conn:
        row = conn.execute("""
            SELECT fill FROM bins WHERE bin_id = ?
        """, (bin_id,)).fetchone()

        if row is None:
            return jsonify({"error": "Bin not found"}), 404

        fill_before = row["fill"]

        # Save the collection event before resetting the bin.
        conn.execute("""
            INSERT INTO collection_history (
                bin_id, fill_before, collected_at
            )
            VALUES (?, ?, ?)
        """, (bin_id, fill_before, now))

        conn.execute("""
            UPDATE bins
            SET fill = 0,
                status = 'NORMAL',
                updated_at = ?,
                last_collected = ?
            WHERE bin_id = ?
        """, (now, now, bin_id))

    return jsonify({
        "message": f"{bin_id} marked as collected",
        "bin": {
            "bin_id": bin_id,
            "fill": 0,
            "status": "NORMAL",
            "last_collected": now
        }
    })


# ---------- COLLECTION HISTORY ----------

@app.route("/api/collections")
def get_collections():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, bin_id, fill_before, collected_at
            FROM collection_history
            ORDER BY id DESC
        """).fetchall()

    return jsonify([dict(row) for row in rows])


# ---------- DASHBOARD ----------


@app.route("/dashboard")
def dashboard():
    print("TEMPLATE FOLDER:", app.template_folder)
    print("TEMPLATE FILE:", app.jinja_env.get_template("index.html").filename)
    return render_template("index.html")



if __name__ == "__main__":
    app.run(debug=False)
