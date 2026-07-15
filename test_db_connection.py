from app.database import db_connection, db_settings, DatabaseConfigError


def main() -> int:
    settings = db_settings()
    masked = {
        **settings,
        "password": "***" if settings.get("password") else "",
    }
    print("Using DB settings:", masked)

    try:
        conn = db_connection()
    except DatabaseConfigError as exc:
        print("Database config error:", exc)
        return 1
    except Exception as exc:
        print("Connection failed:", exc)
        return 2

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 AS ok")
            row = cursor.fetchone()
            print("Connection successful. Query result:", row)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
