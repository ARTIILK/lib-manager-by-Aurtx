import os
import sqlite3
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request

app = Flask(__name__)
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'app.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # Students
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            admission_number TEXT NOT NULL UNIQUE,
            class_name TEXT,
            contact TEXT,
            section TEXT,
            warnings INTEGER NOT NULL DEFAULT 0,
            created_at TEXT
        );
        """
    )
    # Books
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS books (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            author TEXT,
            sbin TEXT UNIQUE,
            stamp TEXT UNIQUE,
            available INTEGER NOT NULL DEFAULT 1,
            created_at TEXT
        );
        """
    )
    # Borrows
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS borrows (
            id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            book_id TEXT NOT NULL,
            borrow_date TEXT NOT NULL,
            due_date TEXT,
            return_date TEXT,
            returned INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(book_id) REFERENCES books(id)
        );
        """
    )
    conn.commit()
    conn.close()


@app.before_request
def ensure_db():
    if not os.path.exists(DB_PATH):
        init_db()


# Helpers

def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def row_to_dict(row: sqlite3.Row):
    return {k: row[k] for k in row.keys()}


# Health
@app.get('/api/health')
def health():
    return jsonify({"ok": True, "service": "biblioflow", "db": "SQLite(Flask)"})


# Students
@app.post('/api/students')
def create_student():
    data = request.get_json(force=True) or {}
    name = data.get('name', '').strip()
    adm = data.get('admission_number', '').strip()
    class_name = data.get('class_name')
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if len(adm) != 6:
        return jsonify({"error": "Admission number must be 6 characters"}), 400
    doc = {
        'id': str(uuid4()),
        'name': name,
        'admission_number': adm,
        'class_name': class_name,
        'contact': data.get('contact'),
        'section': data.get('section'),
        'warnings': 0,
        'created_at': iso(datetime.now(timezone.utc))
    }
    try:
        conn = get_conn()
        conn.execute(
            'INSERT INTO students (id,name,admission_number,class_name,contact,section,warnings,created_at) VALUES (?,?,?,?,?,?,?,?)',
            (doc['id'], doc['name'], doc['admission_number'], doc['class_name'], doc['contact'], doc['section'], doc['warnings'], doc['created_at'])
        )
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Admission number already exists"}), 400
    return jsonify(doc)


@app.get('/api/students')
def list_students():
    q = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 50)), 100)
    skip = int(request.args.get('skip', 0))
    conn = get_conn()
    if q:
        like = f"%{q}%"
        rows = conn.execute(
            'SELECT * FROM students WHERE name LIKE ? OR admission_number LIKE ? OR class_name LIKE ? ORDER BY name LIMIT ? OFFSET ?',
            (like, like, like, limit, skip)
        ).fetchall()
    else:
        rows = conn.execute('SELECT * FROM students ORDER BY name LIMIT ? OFFSET ?', (limit, skip)).fetchall()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])


@app.get('/api/students/<student_id>')
def get_student(student_id):
    conn = get_conn()
    row = conn.execute('SELECT * FROM students WHERE id=?', (student_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Student not found"}), 404
    return jsonify(row_to_dict(row))


@app.put('/api/students/<student_id>')
def update_student(student_id):
    data = request.get_json(force=True) or {}
    # Validate admission number length if provided
    if 'admission_number' in data and len(str(data['admission_number'])) != 6:
        return jsonify({"error": "Admission number must be 6 characters"}), 400

    # Build dynamic update
    fields = []
    values = []
    for k in ['name', 'admission_number', 'class_name', 'contact', 'section']:
        if k in data and data[k] is not None:
            fields.append(f"{k}=?")
            values.append(data[k])
    if not fields:
        return jsonify({"error": "No fields to update"}), 400
    values.append(student_id)
    try:
        conn = get_conn()
        cur = conn.execute(f"UPDATE students SET {', '.join(fields)} WHERE id=?", tuple(values))
        conn.commit()
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": "Student not found"}), 404
        row = conn.execute('SELECT * FROM students WHERE id=?', (student_id,)).fetchone()
        conn.close()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Admission number already exists"}), 400
    return jsonify(row_to_dict(row))


@app.delete('/api/students/<student_id>')
def delete_student(student_id):
    conn = get_conn()
    active = conn.execute('SELECT 1 FROM borrows WHERE student_id=? AND returned=0', (student_id,)).fetchone()
    if active:
        conn.close()
        return jsonify({"error": "Student has active borrow"}), 400
    cur = conn.execute('DELETE FROM students WHERE id=?', (student_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify({"error": "Student not found"}), 404
    return jsonify({"deleted": True})


# Books
@app.post('/api/books')
def create_book():
    data = request.get_json(force=True) or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({"error": "Title is required"}), 400
    if not data.get('sbin') and not data.get('stamp'):
        return jsonify({"error": "Provide at least SBIN or Stamp code"}), 400
    doc = {
        'id': str(uuid4()),
        'title': title,
        'author': data.get('author'),
        'sbin': data.get('sbin'),
        'stamp': data.get('stamp'),
        'available': 1,
        'created_at': iso(datetime.now(timezone.utc))
    }
    try:
        conn = get_conn()
        conn.execute(
            'INSERT INTO books (id,title,author,sbin,stamp,available,created_at) VALUES (?,?,?,?,?,?,?)',
            (doc['id'], doc['title'], doc['author'], doc['sbin'], doc['stamp'], doc['available'], doc['created_at'])
        )
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Duplicate SBIN or Stamp code"}), 400
    doc['available'] = True
    return jsonify(doc)


@app.get('/api/books')
def list_books():
    q = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 50)), 100)
    skip = int(request.args.get('skip', 0))
    conn = get_conn()
    if q:
        like = f"%{q}%"
        rows = conn.execute(
            'SELECT * FROM books WHERE title LIKE ? OR author LIKE ? OR sbin LIKE ? OR stamp LIKE ? ORDER BY title LIMIT ? OFFSET ?',
            (like, like, like, like, limit, skip)
        ).fetchall()
    else:
        rows = conn.execute('SELECT * FROM books ORDER BY title LIMIT ? OFFSET ?', (limit, skip)).fetchall()
    conn.close()
    items = [row_to_dict(r) for r in rows]
    for it in items:
        it['available'] = bool(it.get('available', 1))
    return jsonify(items)


@app.get('/api/books/<book_id>')
def get_book(book_id):
    conn = get_conn()
    row = conn.execute('SELECT * FROM books WHERE id=?', (book_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Book not found"}), 404
    d = row_to_dict(row)
    d['available'] = bool(d.get('available', 1))
    return jsonify(d)


@app.get('/api/books/by-code/<code>')
def get_book_by_code(code):
    conn = get_conn()
    row = conn.execute('SELECT * FROM books WHERE sbin=? OR stamp=?', (code, code)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Book not found"}), 404
    d = row_to_dict(row)
    d['available'] = bool(d.get('available', 1))
    return jsonify(d)


@app.put('/api/books/<book_id>')
def update_book(book_id):
    data = request.get_json(force=True) or {}
    fields = []
    values = []
    for k in ['title', 'author', 'sbin', 'stamp', 'available']:
        if k in data:
            v = data[k]
            if k == 'available':
                v = 1 if bool(v) else 0
            fields.append(f"{k}=?")
            values.append(v)
    if not fields:
        return jsonify({"error": "No fields to update"}), 400
    values.append(book_id)
    try:
        conn = get_conn()
        cur = conn.execute(f"UPDATE books SET {', '.join(fields)} WHERE id=?", tuple(values))
        conn.commit()
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": "Book not found"}), 404
        row = conn.execute('SELECT * FROM books WHERE id=?', (book_id,)).fetchone()
        conn.close()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Duplicate SBIN or Stamp code"}), 400
    d = row_to_dict(row)
    d['available'] = bool(d.get('available', 1))
    return jsonify(d)


@app.delete('/api/books/<book_id>')
def delete_book(book_id):
    conn = get_conn()
    active = conn.execute('SELECT 1 FROM borrows WHERE book_id=? AND returned=0', (book_id,)).fetchone()
    if active:
        conn.close()
        return jsonify({"error": "Book is currently borrowed"}), 400
    cur = conn.execute('DELETE FROM books WHERE id=?', (book_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify({"error": "Book not found"}), 404
    return jsonify({"deleted": True})


# Borrow / Return
@app.post('/api/borrow')
def borrow_book():
    data = request.get_json(force=True) or {}
    student_id = data.get('student_id')
    code = data.get('book_code')
    conn = get_conn()
    s = conn.execute('SELECT * FROM students WHERE id=?', (student_id,)).fetchone()
    if not s:
        conn.close()
        return jsonify({"error": "Student not found"}), 404
    b = conn.execute('SELECT * FROM books WHERE sbin=? OR stamp=?', (code, code)).fetchone()
    if not b:
        conn.close()
        return jsonify({"error": "Book not found"}), 404
    if b['available'] == 0:
        conn.close()
        return jsonify({"error": "Book is not available"}), 400
    # Set unavailable and create borrow
    conn.execute('UPDATE books SET available=0 WHERE id=? AND available=1', (b['id'],))
    borrow_date = datetime.now(timezone.utc)
    due_date = borrow_date + timedelta(days=7)
    doc = {
        'id': str(uuid4()),
        'student_id': s['id'],
        'book_id': b['id'],
        'borrow_date': iso(borrow_date),
        'due_date': iso(due_date),
        'returned': 0,
    }
    conn.execute('INSERT INTO borrows (id,student_id,book_id,borrow_date,due_date,returned) VALUES (?,?,?,?,?,0)',
                 (doc['id'], doc['student_id'], doc['book_id'], doc['borrow_date'], doc['due_date']))
    conn.commit()
    conn.close()
    doc['returned'] = False
    return jsonify(doc)


@app.post('/api/return')
def return_book():
    data = request.get_json(force=True) or {}
    code = data.get('book_code')
    conn = get_conn()
    b = conn.execute('SELECT * FROM books WHERE sbin=? OR stamp=?', (code, code)).fetchone()
    if not b:
        conn.close()
        return jsonify({"error": "Book not found"}), 404
    br = conn.execute('SELECT * FROM borrows WHERE book_id=? AND returned=0', (b['id'],)).fetchone()
    if not br:
        conn.close()
        return jsonify({"error": "No active borrow for this book"}), 400
    now = datetime.now(timezone.utc)
    conn.execute('UPDATE borrows SET returned=1, return_date=? WHERE id=?', (iso(now), br['id']))
    conn.execute('UPDATE books SET available=1 WHERE id=?', (b['id'],))
    # Overdue warnings
    try:
        borrow_dt = datetime.fromisoformat(br['borrow_date'])
    except Exception:
        borrow_dt = now
    if (now - borrow_dt).days > 7:
        conn.execute('UPDATE students SET warnings = warnings + 1 WHERE id=?', (br['student_id'],))
    conn.commit()
    ret = conn.execute('SELECT * FROM borrows WHERE id=?', (br['id'],)).fetchone()
    conn.close()
    d = row_to_dict(ret)
    if not d.get('due_date'):
        d['due_date'] = iso(borrow_dt + timedelta(days=7))
    d['returned'] = True
    return jsonify(d)


@app.get('/api/borrows')
def list_borrows():
    active = request.args.get('active', 'true').lower() == 'true'
    limit = min(int(request.args.get('limit', 50)), 100)
    skip = int(request.args.get('skip', 0))
    conn = get_conn()
    if active:
        rows = conn.execute('SELECT * FROM borrows WHERE returned=0 ORDER BY borrow_date DESC LIMIT ? OFFSET ?', (limit, skip)).fetchall()
    else:
        rows = conn.execute('SELECT * FROM borrows ORDER BY borrow_date DESC LIMIT ? OFFSET ?', (limit, skip)).fetchall()
    conn.close()
    items = [row_to_dict(r) for r in rows]
    for it in items:
        if not it.get('due_date') and it.get('borrow_date'):
            try:
                bd = datetime.fromisoformat(it['borrow_date'])
                it['due_date'] = iso(bd + timedelta(days=7))
            except Exception:
                pass
        it['returned'] = bool(it.get('returned', 0))
    return jsonify(items)


# Suggestions
@app.get('/api/suggest/students')
def suggest_students():
    q = request.args.get('q', '').strip()
    conn = get_conn()
    if q:
        like = f"%{q}%"
        rows = conn.execute('SELECT * FROM students WHERE name LIKE ? OR admission_number LIKE ? ORDER BY name LIMIT 10', (like, like)).fetchall()
    else:
        rows = conn.execute('SELECT * FROM students ORDER BY name LIMIT 10').fetchall()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])


@app.get('/api/suggest/books')
def suggest_books():
    q = request.args.get('q', '').strip()
    conn = get_conn()
    if q:
        like = f"%{q}%"
        rows = conn.execute('SELECT * FROM books WHERE title LIKE ? OR sbin LIKE ? OR stamp LIKE ? ORDER BY title LIMIT 10', (like, like, like)).fetchall()
    else:
        rows = conn.execute('SELECT * FROM books ORDER BY title LIMIT 10').fetchall()
    conn.close()
    items = [row_to_dict(r) for r in rows]
    for it in items:
        it['available'] = bool(it.get('available', 1))
    return jsonify(items)


if __name__ == '__main__':
    # Local run: python app.py
    app.run(host='0.0.0.0', port=8001, debug=True)