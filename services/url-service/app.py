from flask import Flask, jsonify, request, redirect
import os
import secrets
import string

import psycopg2


app = Flask(__name__)


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=os.getenv("DATABASE_PORT", "5432"),
        database=os.getenv("DATABASE_NAME", "urlshortener"),
        user=os.getenv("DATABASE_USER", "urluser"),
        password=os.getenv("DATABASE_PASSWORD", "urlpassword"),
    )


def generate_code(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


@app.get("/health")
def health():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")

        cur.close()
        conn.close()

        return jsonify({
            "status": "ok",
            "database": "ok"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "database": str(e)
        }), 500


@app.post("/shorten")
def shorten_url():
    data = request.get_json()

    if not data or "url" not in data:
        return jsonify({
            "error": "url is required"
        }), 400

    original_url = data["url"]
    code = generate_code()

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO urls (code, original_url)
        VALUES (%s, %s)
        """,
        (code, original_url)
    )

    conn.commit()

    cur.close()
    conn.close()

    return jsonify({
        "code": code,
        "url": original_url,
        "short_url": f"/{code}"
    }), 201


@app.get("/<code>")
def redirect_url(code):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT original_url
        FROM urls
        WHERE code = %s
        """,
        (code,)
    )

    result = cur.fetchone()

    cur.close()
    conn.close()

    if not result:
        return jsonify({
            "error": "URL not found"
        }), 404

    return redirect(result[0])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
