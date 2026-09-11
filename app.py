from flask import Flask, render_template, request, url_for, jsonify
import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv


# =========================================
# FLASK APPLICATION
# =========================================

app = Flask(__name__)


# =========================================
# DATABASE CONFIGURATION
# =========================================

# .env file থেকে environment variables লোড করছি
load_dotenv()

# Neon PostgreSQL connection string
DATABASE_URL = os.getenv("DATABASE_URL")


# =========================================
# DATABASE CONNECTION
# =========================================

def get_db():

    # Neon PostgreSQL database-এর সাথে connection তৈরি করছি
    connection = psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )

    return connection


# =========================================
# DATABASE TABLE তৈরি
# =========================================

def init_db():

    # Database connection নিচ্ছি
    connection = get_db()

    # SQL command চালানোর জন্য cursor তৈরি করছি
    cursor = connection.cursor()

    # Invitations table তৈরি করছি
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invitations (
            id SERIAL PRIMARY KEY,
            invitation_id TEXT UNIQUE NOT NULL,
            dashboard_token TEXT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            message TEXT NOT NULL,
            response TEXT DEFAULT NULL
        )
    """)

    # পুরোনো database-এ column না থাকলে যোগ করছি
    cursor.execute("""
        ALTER TABLE invitations
        ADD COLUMN IF NOT EXISTS dashboard_token TEXT
    """)

    cursor.execute("""
        ALTER TABLE invitations
        ADD COLUMN IF NOT EXISTS response TEXT DEFAULT NULL
    """)

    # পুরোনো invitation-এর token না থাকলে নতুন secure token তৈরি করছি
    cursor.execute("""
        SELECT invitation_id
        FROM invitations
        WHERE dashboard_token IS NULL
    """)

    old_invitations = cursor.fetchall()

    for invitation in old_invitations:

        # নতুন secure dashboard token তৈরি করছি
        dashboard_token = uuid.uuid4().hex

        cursor.execute(
            """
            UPDATE invitations
            SET dashboard_token = %s
            WHERE invitation_id = %s
            """,
            (
                dashboard_token,
                invitation["invitation_id"]
            )
        )

    # Database save করছি
    connection.commit()

    # Cursor বন্ধ করছি
    cursor.close()

    # Connection বন্ধ করছি
    connection.close()


# =========================================
# HOME PAGE
# =========================================

@app.route("/")
def home():

    # Home page দেখাচ্ছি
    return render_template("index.html")


# =========================================
# CREATE INVITATION PAGE
# =========================================

@app.route("/create", methods=["GET"])
def create():

    # Create page দেখাচ্ছি
    return render_template("create.html")


# =========================================
# CREATE INVITATION
# =========================================

@app.route("/invitation", methods=["POST"])
def create_invitation():

    # Sender-এর নাম নিচ্ছি
    sender = request.form["sender"].strip()

    # Receiver-এর নাম নিচ্ছি
    receiver = request.form["receiver"].strip()

    # Message নিচ্ছি
    message = request.form["message"].strip()

    # =====================================
    # BASIC VALIDATION
    # =====================================

    if not sender or not receiver or not message:

        return "সবগুলো ঘর পূরণ করুন ❤️", 400

    # =====================================
    # UNIQUE INVITATION ID
    # =====================================

    invitation_id = str(uuid.uuid4())[:8]

    # =====================================
    # PRIVATE DASHBOARD TOKEN
    # =====================================

    dashboard_token = uuid.uuid4().hex

    # =====================================
    # DATABASE SAVE
    # =====================================

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO invitations
        (
            invitation_id,
            dashboard_token,
            sender,
            receiver,
            message
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            invitation_id,
            dashboard_token,
            sender,
            receiver,
            message
        )
    )

    connection.commit()

    cursor.close()
    connection.close()

    # =====================================
    # INVITATION LINK
    # =====================================

    invitation_link = url_for(
        "show_invitation",
        invitation_id=invitation_id,
        _external=True
    )

    # =====================================
    # PRIVATE DASHBOARD LINK
    # =====================================

    dashboard_link = url_for(
        "dashboard",
        dashboard_token=dashboard_token,
        _external=True
    )

    # =====================================
    # SUCCESS PAGE
    # =====================================

    return render_template(
        "success.html",
        invitation_link=invitation_link,
        dashboard_link=dashboard_link
    )


# =========================================
# SHOW INVITATION
# =========================================

@app.route("/invitation/<invitation_id>")
def show_invitation(invitation_id):

    # Database connection নিচ্ছি
    connection = get_db()
    cursor = connection.cursor()

    # Invitation খুঁজছি
    cursor.execute(
        """
        SELECT
            sender,
            receiver,
            message
        FROM invitations
        WHERE invitation_id = %s
        """,
        (invitation_id,)
    )

    invitation = cursor.fetchone()

    cursor.close()
    connection.close()

    # Invitation না পাওয়া গেলে
    if invitation is None:

        return "Invitation not found ❤️", 404

    # Invitation page দেখাচ্ছি
    return render_template(
        "invitation.html",
        sender=invitation["sender"],
        receiver=invitation["receiver"],
        message=invitation["message"],
        invitation_id=invitation_id
    )


# =========================================
# YES RESPONSE
# =========================================

@app.route("/invitation/<invitation_id>/yes", methods=["POST"])
def invitation_yes(invitation_id):

    # Database connection নিচ্ছি
    connection = get_db()
    cursor = connection.cursor()

    # Invitation খুঁজছি
    cursor.execute(
        """
        SELECT
            invitation_id,
            receiver
        FROM invitations
        WHERE invitation_id = %s
        """,
        (invitation_id,)
    )

    invitation = cursor.fetchone()

    # Invitation না থাকলে
    if invitation is None:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Invitation not found ❤️"
        }), 404

    # YES response save করছি
    connection.execute(
        """
        UPDATE invitations
        SET response = %s
        WHERE invitation_id = %s
        """,
        (
            "YES",
            invitation_id
        )
    )

    # Database save করছি
    connection.commit()

    # Connection বন্ধ করছি
    connection.close()

    # Success response পাঠাচ্ছি
    return jsonify({
        "success": True,
        "message": "Invitation accepted ❤️",
        "receiver": invitation["receiver"]
    })


# =========================================
# PRIVATE SENDER DASHBOARD
# =========================================

@app.route("/dashboard/<dashboard_token>")
def dashboard(dashboard_token):

    # Database connection নিচ্ছি
    connection = get_db()
    cursor = connection.cursor()

    # Secret dashboard token দিয়ে invitation খুঁজছি
    cursor.execute(
        """
        SELECT
            invitation_id,
            dashboard_token,
            sender,
            receiver,
            message,
            response
        FROM invitations
        WHERE dashboard_token = %s
        """,
        (dashboard_token,)
    )

    invitation = cursor.fetchone()

    cursor.close()
    connection.close()

    # Token ভুল হলে
    if invitation is None:

        return """
        <div style="
            text-align:center;
            margin-top:100px;
            font-family:Arial;
        ">
            <h2>🔐 Private Dashboard</h2>
            <p>This dashboard link is invalid ❤️</p>
        </div>
        """, 404

    # Secure dashboard দেখাচ্ছি
    return render_template(
        "dashboard.html",
        invitation=invitation
    )


# =========================================
# LIVE DASHBOARD STATUS
# =========================================

@app.route("/dashboard/<dashboard_token>/status")
def dashboard_status(dashboard_token):

    # Database connection নিচ্ছি
    connection = get_db()
    cursor = connection.cursor()

    # Secret token দিয়ে current status খুঁজছি
    cursor.execute(
        """
        SELECT
            response,
            receiver
        FROM invitations
        WHERE dashboard_token = %s
        """,
        (dashboard_token,)
    )

    invitation = cursor.fetchone()

    cursor.close()
    connection.close()

    # Token ভুল হলে
    if invitation is None:

        return jsonify({
            "success": False,
            "message": "Dashboard not found"
        }), 404

    # Current response JSON আকারে পাঠাচ্ছি
    return jsonify({
        "success": True,
        "response": invitation["response"],
        "receiver": invitation["receiver"]
    })


# =========================================
# APPLICATION START
# =========================================

if __name__ == "__main__":

    # Database initialize করছি
    init_db()

    # Flask application চালু করছি
    app.run(
        debug=True
    )