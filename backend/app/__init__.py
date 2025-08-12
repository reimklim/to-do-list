from flask import Flask, request, jsonify, abort
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import os

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

def create_app():
    app = Flask(__name__)

    @app.get("/")
    def index():
        return "Flask backend is up and running"

    @app.get("/health")
    def health():
        return "OK", 200

    db_url = os.getenv("DATABASE_URL")
    print("DATABASE_URL =", os.getenv("DATABASE_URL"))
    engine = create_engine(db_url, pool_pre_ping=True, future=True) if db_url else None

    # Вспомогательный сериализатор: RowMapping -> dict и приведение дат к строкам
    def serialize_task(row_mapping):
        d = dict(row_mapping)
        if d.get("created_at") is not None:
            d["created_at"] = d["created_at"].isoformat()
        if d.get("updated_at") is not None:
            d["updated_at"] = d["updated_at"].isoformat()
        return d

    # инициализация таблицы tasks
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                is_done BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

    @app.get("/health/db")
    def health_db():
        if engine is None:
            return "DB Error: DATABASE_URL is not set", 500
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return "DB OK", 200
        except Exception as e:
            return f"DB Error: {e}", 500
    
    # получение всех задач
    @app.get("/tasks")
    def get_tasks():
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT id, title, description, is_done, created_at, updated_at
                FROM tasks
                ORDER BY id
            """)).mappings().all()
        return jsonify([serialize_task(r) for r in rows]), 200

    # создание задачи
    @app.post("/tasks")
    def create_task():
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        description = data.get("description")
        if not title:
            return jsonify({"error": "title is required"}), 400
        with engine.begin() as conn:
            row = conn.execute(text("""
                INSERT INTO tasks (title, description)
                VALUES (:title, :description)
                RETURNING id, title, description, is_done, created_at, updated_at
            """), {"title": title, "description": description}).mappings().one()
        return jsonify(serialize_task(row)), 201
    
    # получение задачи по id
    @app.get("/tasks/<int:task_id>")
    def get_task(task_id: int):
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT id, title, description, is_done, created_at, updated_at
                FROM tasks WHERE id = :id
            """), {"id": task_id}).mappings().first()
        if not row:
            abort(404, description="Task not found")
        return jsonify(serialize_task(row)), 200
    
    # обновление задачи
    @app.put("/tasks/<int:task_id>")
    def update_task(task_id: int):
        data = request.get_json(silent=True) or {}
        fields = []
        params = {"id": task_id}

        if "title" in data:
            title = (data.get("title") or "").strip()
            if not title:
                return jsonify({"error": "title cannot be empty"}), 400
            fields.append("title = :title")
            params["title"] = title

        if "description" in data:
            fields.append("description = :description")
            params["description"] = data.get("description")

        if "is_done" in data:
            fields.append("is_done = :is_done")
            params["is_done"] = bool(data.get("is_done"))

        if not fields:
            return jsonify({"error": "no fields to update"}), 400

        fields.append("updated_at = NOW()")

        with engine.begin() as conn:
            row = conn.execute(text(f"""
                UPDATE tasks SET {", ".join(fields)}
                WHERE id = :id
                RETURNING id, title, description, is_done, created_at, updated_at
            """), params).mappings().first()
        if not row:
            abort(404, description="Task not found")
        return jsonify(serialize_task(row)), 200
    
    # удаление задачи
    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id: int):
        with engine.begin() as conn:
            row = conn.execute(text("""
                DELETE FROM tasks WHERE id = :id
                RETURNING id
            """), {"id": task_id}).first()
        if not row:
            abort(404, description="Task not found")
        return "", 204

    return app

app = create_app()