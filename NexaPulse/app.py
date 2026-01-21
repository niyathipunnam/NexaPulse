from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    g,
    session,
)
import mysql.connector

app = Flask(__name__)
app.config["SECRET_KEY"] = "nexapulse-secret-key"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "punnam@2051",   # change if needed
    "database": "nexapulse",
}

# ---------- DB helpers ----------

def get_db():
    if "db" not in g or not g.db.is_connected():
        g.db = mysql.connector.connect(**DB_CONFIG)
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None and db.is_connected():
        db.close()


def init_db():
    # create database if not exist
    root_conn = mysql.connector.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )
    cur = root_conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
    cur.close()
    root_conn.close()

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    # doctors table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS doctors (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(120) NOT NULL UNIQUE,
            specialization VARCHAR(120) NOT NULL,
            experience_level VARCHAR(20) NULL,
            experience_years INT NULL,
            workplace VARCHAR(255) NULL,
            password VARCHAR(255) NOT NULL
        )
        """
    )

    # patients table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS patients (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(120) UNIQUE,
            age INT,
            gender VARCHAR(20),
            password VARCHAR(255)
        )
        """
    )

    # questions = posts
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            patient_id INT NULL,
            question_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # replies = comments for each question
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS question_replies (
            id INT AUTO_INCREMENT PRIMARY KEY,
            question_id INT NOT NULL,
            doctor_id INT NOT NULL,
            reply_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (question_id) REFERENCES questions(id),
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        )
        """
    )

    conn.commit()
    cur.close()
    conn.close()


init_db()

# ---------- Home ----------

@app.route("/")
def home():
    return render_template("home.html")


# ---------- Doctor auth ----------

@app.route("/doctor/login", methods=["GET", "POST"])
def doctor_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute(
            "SELECT * FROM doctors WHERE email = %s AND password = %s",
            (email, password),
        )
        doctor = cur.fetchone()
        cur.close()

        if doctor is None:
            return render_template(
                "doctor_login.html",
                error="Invalid email or password.",
            )

        session["doctor_id"] = doctor["id"]
        session["doctor_name"] = doctor["name"]
        session["doctor_speciality"] = doctor["specialization"]
        session["doctor_experience_level"] = doctor.get("experience_level")
        session["doctor_workplace"] = doctor.get("workplace")

        return redirect(url_for("doctor_dashboard"))

    return render_template("doctor_login.html")


@app.route("/doctor/register", methods=["GET", "POST"])
def doctor_register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        specialization = request.form.get("specialization")
        experience_level = request.form.get("experience_level")
        experience_years = request.form.get("experience_years") or None
        workplace = request.form.get("workplace")
        password = request.form.get("password")

        db = get_db()
        cur = db.cursor()
        try:
            cur.execute(
                """
                INSERT INTO doctors (
                    name, email, specialization,
                    experience_level, experience_years, workplace,
                    password
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    name,
                    email,
                    specialization,
                    experience_level,
                    experience_years,
                    workplace,
                    password,
                ),
            )
            db.commit()
        except mysql.connector.IntegrityError:
            db.rollback()
            cur.close()
            return render_template(
                "doctor_register.html",
                error="A doctor with this email already exists.",
            )

        cur.close()
        return redirect(url_for("doctor_login"))

    return render_template("doctor_register.html")


@app.route("/doctor/logout")
def doctor_logout():
    session.clear()
    return redirect(url_for("home"))


# ---------- Doctor profile (viewed by patient) ----------

@app.route("/doctor/profile/<int:doctor_id>")
def doctor_profile(doctor_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute(
        """
        SELECT id, name, email, specialization,
               experience_level, experience_years, workplace
        FROM doctors
        WHERE id = %s
        """,
        (doctor_id,),
    )
    doctor = cur.fetchone()
    cur.close()

    if not doctor:
        return "Doctor not found", 404

    return render_template("doctor_profile.html", doctor=doctor)


# ---------- Doctor dashboard (feed + replies) ----------

@app.route("/doctor/dashboard")
def doctor_dashboard():
    if "doctor_id" not in session:
        return redirect(url_for("doctor_login"))

    doctor_name = session.get("doctor_name", "Doctor")
    doctor_speciality = session.get("doctor_speciality", "Specialist")
    experience_level = session.get("doctor_experience_level", "")
    workplace = session.get("doctor_workplace", "")

    db = get_db()
    cur = db.cursor(dictionary=True)

    # 1) Check if any posts exist
    cur.execute("SELECT COUNT(*) AS c FROM questions")
    count_row = cur.fetchone()
    has_posts = count_row["c"] > 0

    # 2) If no posts, insert 10 demo posts
    if not has_posts:
        sample_posts = [
            "I am 26 and keep getting a dull chest pain when I climb stairs or walk fast. It goes away after rest. Should I be worried about my heart?",
            "My blood pressure is usually around 150/95 even though I am taking tablets regularly. What lifestyle changes can actually bring it down?",
            "After recovering from dengue two months ago I am facing severe hair fall and constant tiredness. Is this a normal recovery or a sign of deficiency?",
            "I work on a laptop for 9–10 hours a day and get strong headaches every evening. Blue‑light glasses are not helping. Which doctor should I consult?",
            "My 8‑year‑old gets cold, cough and fever almost every month after school reopens. Should I go for an allergy test or immunity check‑up?",
            "I am on thyroid medication but still feel sleepy, gain weight and have dry skin. Do I need to adjust my dosage or check anything else?",
            "There is a small painless lump on the side of my neck for almost 2 months. It has not grown much but it is still there. Which tests are needed?",
            "I feel very anxious before exams, my heart races and I cannot sleep at all the previous night. Is this just stress or do I need treatment?",
            "My fasting sugar is normal but my post‑meal sugar goes very high after lunch and dinner. What does it mean and how should I control it?",
            "I have knee pain whenever I climb stairs or sit cross‑legged for some time. I am 35 and slightly overweight. Do I start with an X‑ray or MRI?"
        ]

        cur2 = db.cursor()
        cur2.executemany(
            "INSERT INTO questions (patient_id, question_text) VALUES (NULL, %s)",
            [(text,) for text in sample_posts],
        )
        db.commit()
        cur2.close()

    # 3) Load latest 10 posts
    cur.execute(
        """
        SELECT q.id, q.question_text, q.created_at,
               p.id AS patient_id,
               p.name AS patient_name
        FROM questions q
        LEFT JOIN patients p ON q.patient_id = p.id
        ORDER BY q.created_at DESC
        LIMIT 10
        """
    )
    posts = cur.fetchall()

    # 4) Load all replies for these posts
    post_ids = [p["id"] for p in posts]
    replies_by_post = {pid: [] for pid in post_ids}

    if post_ids:
        format_strings = ",".join(["%s"] * len(post_ids))
        cur.execute(
            f"""
            SELECT r.id,
                   r.question_id,
                   r.reply_text,
                   r.created_at,
                   r.doctor_id,
                   d.name AS doctor_name,
                   d.specialization
            FROM question_replies r
            JOIN doctors d ON r.doctor_id = d.id
            WHERE r.question_id IN ({format_strings})
            ORDER BY r.created_at ASC
            """,
            post_ids,
        )
        all_replies = cur.fetchall()
        for r in all_replies:
            replies_by_post[r["question_id"]].append(r)

    cur.close()

    # attach replies to each post
    for p in posts:
        p["replies"] = replies_by_post.get(p["id"], [])

    # KPIs
    new_cases = len(posts)
    total_replies = sum(len(v) for v in replies_by_post.values())
    followups = 0

    return render_template(
        "doctor_dashboard.html",
        doctor_name=doctor_name,
        doctor_speciality=doctor_speciality,
        experience_level=experience_level,
        workplace=workplace,
        new_cases=new_cases,
        responses_today=total_replies,
        followups=followups,
        posts=posts,
    )


@app.route("/doctor/posts/<int:question_id>/reply", methods=["POST"])
def doctor_post_reply(question_id):
    if "doctor_id" not in session:
        return redirect(url_for("doctor_login"))

    reply_text = request.form.get("reply_text")
    if not reply_text:
        return redirect(url_for("doctor_dashboard"))

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO question_replies (question_id, doctor_id, reply_text)
        VALUES (%s, %s, %s)
        """,
        (question_id, session["doctor_id"], reply_text),
    )
    db.commit()
    cur.close()

    return redirect(url_for("doctor_dashboard"))


# ---------- Patient auth ----------

@app.route("/patient/login", methods=["GET", "POST"])
def patient_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute(
            "SELECT * FROM patients WHERE email = %s AND password = %s",
            (email, password),
        )
        patient = cur.fetchone()
        cur.close()

        if not patient:
            return render_template(
                "patient_login.html",
                error="Invalid email or password.",
            )

        session["patient_id"] = patient["id"]
        session["patient_name"] = patient["name"]
        return redirect(url_for("patient_dashboard"))

    return render_template("patient_login.html")


@app.route("/patient/register", methods=["GET", "POST"])
def patient_register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        age = request.form.get("age") or None
        gender = request.form.get("gender") or None
        password = request.form.get("password")

        db = get_db()
        cur = db.cursor()
        try:
            cur.execute(
                """
                INSERT INTO patients (name, email, age, gender, password)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (name, email, age, gender, password),
            )
            db.commit()
        except mysql.connector.IntegrityError:
            db.rollback()
            cur.close()
            return render_template(
                "patient_register.html",
                error="A patient with this email already exists.",
            )

        cur.close()
        return redirect(url_for("patient_login"))

    return render_template("patient_register.html")


@app.route("/patient/logout")
def patient_logout():
    session.pop("patient_id", None)
    session.pop("patient_name", None)
    return redirect(url_for("home"))


# ---------- Patient dashboard ----------

@app.route("/patient/dashboard")
def patient_dashboard():
    if "patient_id" not in session:
        return redirect(url_for("patient_login"))

    patient_name = session.get("patient_name", "Patient")

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute(
        """
        SELECT q.id, q.question_text, q.created_at,
               p.name AS patient_name
        FROM questions q
        LEFT JOIN patients p ON q.patient_id = p.id
        ORDER BY q.created_at DESC
        LIMIT 10
        """
    )
    posts = cur.fetchall()

    post_ids = [p["id"] for p in posts]
    replies_by_post = {pid: [] for pid in post_ids}

    if post_ids:
        format_strings = ",".join(["%s"] * len(post_ids))
        cur.execute(
            f"""
            SELECT r.id,
                   r.question_id,
                   r.reply_text,
                   r.created_at,
                   r.doctor_id,
                   d.name AS doctor_name,
                   d.specialization
            FROM question_replies r
            JOIN doctors d ON r.doctor_id = d.id
            WHERE r.question_id IN ({format_strings})
            ORDER BY r.created_at ASC
            """,
            post_ids,
        )
        all_replies = cur.fetchall()
        for r in all_replies:
            replies_by_post[r["question_id"]].append(r)

    cur.close()

    for p in posts:
        p["replies"] = replies_by_post.get(p["id"], [])

    return render_template(
        "patient_dashboard.html",
        patient_name=patient_name,
        posts=posts,
    )


@app.route("/patient/create-post", methods=["POST"])
def patient_create_post():
    if "patient_id" not in session:
        return redirect(url_for("patient_login"))

    question_text = request.form.get("question_text")
    if question_text:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO questions (patient_id, question_text) VALUES (%s, %s)",
            (session["patient_id"], question_text),
        )
        db.commit()
        cur.close()

    return redirect(url_for("patient_dashboard"))


# ---------- Patient private chat (patient view) ----------

@app.route("/patient/chat/<int:doctor_id>/<int:question_id>")
def patient_chat(doctor_id, question_id):
    if "patient_id" not in session:
        return redirect(url_for("patient_login"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute(
        "SELECT id, name, specialization, workplace FROM doctors WHERE id = %s",
        (doctor_id,),
    )
    doctor = cur.fetchone()

    cur.execute(
        "SELECT question_text, patient_id FROM questions WHERE id = %s",
        (question_id,),
    )
    question = cur.fetchone()

    cur.close()

    messages = []  # later load real chat messages

    return render_template(
        "patient_chat.html",
        doctor=doctor,
        question=question,
        question_id=question_id,
        messages=messages,
    )


# ---------- Doctor private chat (doctor view) ----------

@app.route("/doctor/chat/<int:patient_id>/<int:question_id>")
def doctor_chat(patient_id, question_id):
    if "doctor_id" not in session:
        return redirect(url_for("doctor_login"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    # patient info
    cur.execute(
        "SELECT id, name, email, age, gender FROM patients WHERE id = %s",
        (patient_id,),
    )
    patient = cur.fetchone()

    # question info
    cur.execute(
        "SELECT question_text FROM questions WHERE id = %s",
        (question_id,),
    )
    question = cur.fetchone()

    cur.close()

    messages = []  # later load real chat messages

    return render_template(
        "doctor_chat.html",
        patient=patient,
        question=question,
        question_id=question_id,
        messages=messages,
    )


if __name__ == "__main__":
    app.run(debug=True)
