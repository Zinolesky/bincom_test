from flask import Flask, render_template, request, jsonify
import mysql.connector
from datetime import datetime

app = Flask(__name__)

PARTIES = ['PDP', 'APC', 'ACN', 'DPP', 'PPA', 'CDC', 'JP', 'ANPP', 'LABO', 'CPP']


import os

def get_db():
    return mysql.connector.connect(
        host=os.environ.get("MYSQLHOST", os.environ.get("DB_HOST", "localhost")),
        user=os.environ.get("MYSQLUSER", os.environ.get("DB_USER", "root")),
        password=os.environ.get("MYSQLPASSWORD", os.environ.get("DB_PASSWORD", "")),
        database=os.environ.get("MYSQLDATABASE", os.environ.get("DB_NAME", "bincomphptest")),
        port=int(os.environ.get("MYSQLPORT", os.environ.get("DB_PORT", "3306")))
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/polling_unit_result", methods=["GET", "POST"])
def polling_unit_result():
    results = None
    pu_id = None
    if request.method == "POST":
        pu_id = request.form["polling_unit_id"]
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT party_abbreviation, party_score FROM announced_pu_results WHERE polling_unit_uniqueid = %s"
        cursor.execute(query, (pu_id,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
    return render_template("polling_unit.html", results=results, pu_id=pu_id)


@app.route("/lga_result", methods=["GET", "POST"])
def lga_result():
    lgas = []
    results = None
    selected_lga = None
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT uniqueid, lga_name FROM lga")
    lgas = cursor.fetchall()
    cursor.close()
    conn.close()

    if request.method == "POST":
        selected_lga = request.form["lga_id"]
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT apr.party_abbreviation, SUM(apr.party_score) as total_score
            FROM announced_pu_results apr
            JOIN polling_unit pu ON apr.polling_unit_uniqueid = pu.uniqueid
            WHERE pu.lga_id = %s
            GROUP BY apr.party_abbreviation
            ORDER BY total_score DESC
        """
        cursor.execute(query, (selected_lga,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
    return render_template("lga_result.html", lgas=lgas, results=results, selected_lga=selected_lga)


@app.route("/api/polling_units/<int:lga_id>")
def api_polling_units(lga_id):
    """Returns polling units for a given LGA as JSON (for the chained combo box)."""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT uniqueid, polling_unit_name FROM polling_unit WHERE lga_id = %s ORDER BY polling_unit_name",
        (lga_id,)
    )
    units = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(units)


@app.route("/store_result", methods=["GET", "POST"])
def store_result():
    message = None
    error = None
    lgas = []

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT uniqueid, lga_name FROM lga ORDER BY lga_name")
    lgas = cursor.fetchall()
    cursor.close()
    conn.close()

    if request.method == "POST":
        pu_id = request.form.get("polling_unit_id")
        entered_by = request.form.get("entered_by", "")
        user_ip = request.remote_addr or "127.0.0.1"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        scores = {}
        for party in PARTIES:
            score_str = request.form.get(f"score_{party}", "").strip()
            if score_str:
                scores[party] = int(score_str)

        if not pu_id:
            error = "Please select a polling unit."
        elif not scores:
            error = "Please enter at least one party score."
        else:
            try:
                conn = get_db()
                cursor = conn.cursor()
                query = """INSERT INTO announced_pu_results
                           (polling_unit_uniqueid, party_abbreviation, party_score,
                            entered_by_user, date_entered, user_ip_address)
                           VALUES (%s, %s, %s, %s, %s, %s)"""
                for party, score in scores.items():
                    cursor.execute(query, (pu_id, party, score, entered_by, now, user_ip))
                conn.commit()
                message = f"Successfully stored {len(scores)} party result(s) for Polling Unit #{pu_id}!"
                cursor.close()
                conn.close()
            except Exception as e:
                error = f"Database error: {str(e)}"

    return render_template("store_result.html", message=message, error=error, lgas=lgas, parties=PARTIES)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
