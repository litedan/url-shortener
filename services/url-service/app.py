from flask import Flask, jsonify, request, redirect, Response
import os
import secrets
import string
import time

import psycopg2

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


app = Flask(__name__)

# HTTP metrics
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"]
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request processing duration",
    ["method", "endpoint"]
)

# Business metrics
URLS_CREATED = Counter(
    "url_shortener_created_total",
    "Total number of successfully created short URLs"
)

DATABASE_ERRORS = Counter(
    "url_shortener_database_errors_total",
    "Total number of database errors"
)


@app.before_request
def start_timer():
    request.start_time = time.time()


@app.after_request
def record_metrics(response):
    # Do not count Prometheus scraping as application traffic
    if request.path != "/metrics":
        duration = time.time() - getattr(request, "start_time", time.time())

        HTTP_REQUESTS.labels(
            method=request.method,
            endpoint=request.endpoint or "unknown",
            status=response.status_code
        ).inc()

        HTTP_REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.endpoint or "unknown"
        ).observe(duration)

    return response


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


@app.get("/metrics")
def metrics():
    return Response(
        generate_latest(),
        mimetype=CONTENT_TYPE_LATEST
    )


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
        DATABASE_ERRORS.inc()

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

    try:
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

        URLS_CREATED.inc()

        return jsonify({
            "code": code,
            "url": original_url,
            "short_url": f"/{code}"
        }), 201

    except Exception:
        DATABASE_ERRORS.inc()
        raise


@app.get("/<code>")
def redirect_url(code):
    try:
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

    except Exception:
        DATABASE_ERRORS.inc()
        raise


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
