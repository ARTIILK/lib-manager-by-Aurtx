import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

try:
    # Optional imports; only used if Mongo backend is selected
    from motor.motor_asyncio import AsyncIOMotorClient
    from pymongo.errors import DuplicateKeyError
    from pymongo import ReturnDocument
except Exception:  # pragma: no cover
    AsyncIOMotorClient = None
    DuplicateKeyError = Exception
    ReturnDocument = None

import aiosqlite

ISO = lambda dt: dt.astimezone(timezone.utc).isoformat() if isinstance(dt, datetime) else str(dt)


class AbstractRepo:
    async def init(self):
        raise NotImplementedError

    # Students
    async def create_student(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    async def list_students(self, q: Optional[str], limit: int, skip: int) -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def get_student(self, student_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def update_student(self, student_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    async def delete_student(self, student_id: str) -> bool:
        raise NotImplementedError

    async def suggest_students(self, q: Optional[str]) -> List[Dict[str, Any]]:
        raise NotImplementedError

    # Books
    async def create_book(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    async def list_books(self, q: Optional[str], limit: int, skip: int) -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def get_book(self, book_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def get_book_by_code(self, code: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def update_book(self, book_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    async def delete_book(self, book_id: str) -> bool:
        raise NotImplementedError

    async def suggest_books(self, q: Optional[str]) -> List[Dict[str, Any]]:
        raise NotImplementedError

    # Borrow
    async def borrow_book(self, student_id: str, book_code: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def return_book(self, book_code: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def list_borrows(self, active: bool, limit: int, skip: int) -> List[Dict[str, Any]]:
        raise NotImplementedError


class MongoRepo(AbstractRepo):
    def __init__(self, mongo_url: str):
        if not AsyncIOMotorClient:
            raise RuntimeError("motor not installed")
        self.client = AsyncIOMotorClient(mongo_url)
        try:
            self.db = self.client.get_default_database()
        except Exception:
            self.db = self.client["biblioflow"]
        self.students = self.db["students"]
        self.books = self.db["books"]
        self.borrows = self.db["borrows"]

    async def init(self):
        await self.students.create_index("id", unique=True)
        await self.students.create_index("admission_number", unique=True)
        await self.books.create_index("id", unique=True)
        await self.books.create_index("sbin", unique=True, sparse=True)
        await self.books.create_index("stamp", unique=True, sparse=True)
        await self.borrows.create_index("id", unique=True)
        await self.borrows.create_index([("book_id", 1), ("returned", 1)])
        await self.borrows.create_index([("student_id", 1), ("returned", 1)])

    # Students
    async def create_student(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        doc = {
            **payload,
            "id": str(uuid4()),
            "warnings": 0,
            "created_at": ISO(datetime.now(timezone.utc)),
        }
        try:
            await self.students.insert_one(doc)
        except DuplicateKeyError:
            raise ValueError("ADMISSION_DUPLICATE")
        return doc

    async def list_students(self, q: Optional[str], limit: int, skip: int) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if q:
            query = {"$or": [
                {"name": {"$regex": q, "$options": "i"}},
                {"admission_number": {"$regex": q, "$options": "i"}},
                {"class_name": {"$regex": q, "$options": "i"}},
            ]}
        cursor = self.students.find(query).skip(skip).limit(min(limit, 100)).sort("name")
        return [d async for d in cursor]

    async def get_student(self, student_id: str) -> Dict[str, Any]:
        doc = await self.students.find_one({"id": student_id})
        if not doc:
            raise KeyError("NOT_FOUND")
        return doc

    async def update_student(self, student_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            res = await self.students.find_one_and_update({"id": student_id}, {"$set": payload}, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError:
            raise ValueError("ADMISSION_DUPLICATE")
        if not res:
            raise KeyError("NOT_FOUND")
        return res

    async def delete_student(self, student_id: str) -> bool:
        active = await self.borrows.find_one({"student_id": student_id, "returned": False})
        if active:
            raise ValueError("STUDENT_ACTIVE_BORROW")
        res = await self.students.delete_one({"id": student_id})
        if res.deleted_count == 0:
            raise KeyError("NOT_FOUND")
        return True

    async def suggest_students(self, q: Optional[str]) -> List[Dict[str, Any]]:
        return await self.list_students(q, 10, 0)

    # Books
    async def create_book(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        doc = {**payload, "id": str(uuid4()), "available": True, "created_at": ISO(datetime.now(timezone.utc))}
        try:
            await self.books.insert_one(doc)
        except DuplicateKeyError:
            raise ValueError("BOOK_DUPLICATE_CODE")
        return doc

    async def list_books(self, q: Optional[str], limit: int, skip: int) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if q:
            query = {"$or": [
                {"title": {"$regex": q, "$options": "i"}},
                {"author": {"$regex": q, "$options": "i"}},
                {"sbin": {"$regex": q, "$options": "i"}},
                {"stamp": {"$regex": q, "$options": "i"}},
            ]}
        cursor = self.books.find(query).skip(skip).limit(min(limit, 100)).sort("title")
        return [d async for d in cursor]

    async def get_book(self, book_id: str) -> Dict[str, Any]:
        doc = await self.books.find_one({"id": book_id})
        if not doc:
            raise KeyError("NOT_FOUND")
        return doc

    async def get_book_by_code(self, code: str) -> Dict[str, Any]:
        doc = await self.books.find_one({"$or": [{"sbin": code}, {"stamp": code}]})
        if not doc:
            raise KeyError("NOT_FOUND")
        return doc

    async def update_book(self, book_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            res = await self.books.find_one_and_update({"id": book_id}, {"$set": payload}, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError:
            raise ValueError("BOOK_DUPLICATE_CODE")
        if not res:
            raise KeyError("NOT_FOUND")
        return res

    async def delete_book(self, book_id: str) -> bool:
        active = await self.borrows.find_one({"book_id": book_id, "returned": False})
        if active:
            raise ValueError("BOOK_ACTIVE_BORROW")
        res = await self.books.delete_one({"id": book_id})
        if res.deleted_count == 0:
            raise KeyError("NOT_FOUND")
        return True

    async def suggest_books(self, q: Optional[str]) -> List[Dict[str, Any]]:
        return await self.list_books(q, 10, 0)

    # Borrow
    async def borrow_book(self, student_id: str, book_code: str) -> Dict[str, Any]:
        student = await self.get_student(student_id)
        book = await self.get_book_by_code(book_code)
        updated = await self.books.find_one_and_update({"id": book["id"], "available": True}, {"$set": {"available": False}}, return_document=ReturnDocument.AFTER)
        if not updated or updated.get("available") is True:
            raise ValueError("BOOK_NOT_AVAILABLE")
        borrow_date = datetime.now(timezone.utc)
        due_date = borrow_date + timedelta(days=7)
        doc = {
            "id": str(uuid4()),
            "student_id": student["id"],
            "book_id": book["id"],
            "borrow_date": ISO(borrow_date),
            "due_date": ISO(due_date),
            "returned": False,
        }
        await self.borrows.insert_one(doc)
        return doc

    async def return_book(self, book_code: str) -> Dict[str, Any]:
        book = await self.get_book_by_code(book_code)
        borrow = await self.borrows.find_one({"book_id": book["id"], "returned": False})
        if not borrow:
            raise ValueError("NO_ACTIVE_BORROW")
        now = datetime.now(timezone.utc)
        returned = await self.borrows.find_one_and_update({"id": borrow["id"]}, {"$set": {"returned": True, "return_date": ISO(now)}}, return_document=ReturnDocument.AFTER)
        await self.books.update_one({"id": book["id"]}, {"$set": {"available": True}})
        try:
            borrow_dt = datetime.fromisoformat(borrow["borrow_date"])  # type: ignore
        except Exception:
            borrow_dt = now
        if (now - borrow_dt).days > 7:
            await self.students.update_one({"id": borrow["student_id"]}, {"$inc": {"warnings": 1}})
        if returned and "due_date" not in returned:
            returned["due_date"] = ISO(borrow_dt + timedelta(days=7))
        return returned

    async def list_borrows(self, active: bool, limit: int, skip: int) -> List[Dict[str, Any]]:
        query = {"returned": False} if active else {}
        cursor = self.borrows.find(query).skip(skip).limit(min(limit, 100)).sort("borrow_date", -1)
        items = []
        async for d in cursor:
            if "due_date" not in d and d.get("borrow_date"):
                try:
                    bd = datetime.fromisoformat(d["borrow_date"])  # type: ignore
                    d["due_date"] = ISO(bd + timedelta(days=7))
                except Exception:
                    pass
            items.append(d)
        return items


class SQLiteRepo(AbstractRepo):
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.dirname(__file__)
        self.students_path = os.path.join(self.base_dir, "students.db")
        self.library_path = os.path.join(self.base_dir, "library.db")
        self._students = None
        self._library = None

    async def init(self):
        self._students = await aiosqlite.connect(self.students_path)
        self._library = await aiosqlite.connect(self.library_path)
        await self._students.execute("PRAGMA foreign_keys = ON;")
        await self._library.execute("PRAGMA foreign_keys = ON;")
        # Create schemas (subset compatible with frontend)
        await self._students.execute(
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
        await self._library.execute(
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
        await self._library.execute(
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
        await self._students.commit()
        await self._library.commit()

    # Helper methods
    async def _fetchone(self, conn: aiosqlite.Connection, q: str, params: tuple) -> Optional[aiosqlite.Row]:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(q, params) as cur:
            return await cur.fetchone()

    async def _fetchall(self, conn: aiosqlite.Connection, q: str, params: tuple = ()) -> List[Dict[str, Any]]:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(q, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    # Students
    async def create_student(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        doc = {
            **payload,
            "id": str(uuid4()),
            "warnings": 0,
            "created_at": ISO(datetime.now(timezone.utc)),
        }
        try:
            await self._students.execute(
                "INSERT INTO students (id,name,admission_number,class_name,contact,section,warnings,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    doc["id"], doc["name"], doc["admission_number"], doc.get("class_name"), doc.get("contact"), doc.get("section"), doc["warnings"], doc["created_at"],
                ),
            )
            await self._students.commit()
        except Exception as e:
            if "UNIQUE" in str(e):
                raise ValueError("ADMISSION_DUPLICATE")
            raise
        return doc

    async def list_students(self, q: Optional[str], limit: int, skip: int) -> List[Dict[str, Any]]:
        if q:
            q_like = f"%{q}%"
            return await self._fetchall(
                self._students,
                "SELECT * FROM students WHERE name LIKE ? OR admission_number LIKE ? OR class_name LIKE ? ORDER BY name LIMIT ? OFFSET ?",
                (q_like, q_like, q_like, min(limit, 100), skip),
            )
        return await self._fetchall(
            self._students, "SELECT * FROM students ORDER BY name LIMIT ? OFFSET ?", (min(limit, 100), skip)
        )

    async def get_student(self, student_id: str) -> Dict[str, Any]:
        row = await self._fetchone(self._students, "SELECT * FROM students WHERE id=?", (student_id,))
        if not row:
            raise KeyError("NOT_FOUND")
        return dict(row)

    async def update_student(self, student_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Build dynamic update
        fields = []
        values = []
        for k, v in payload.items():
            fields.append(f"{k}=?")
            values.append(v)
        values.append(student_id)
        try:
            await self._students.execute(f"UPDATE students SET {', '.join(fields)} WHERE id=?", tuple(values))
            await self._students.commit()
        except Exception as e:
            if "UNIQUE" in str(e):
                raise ValueError("ADMISSION_DUPLICATE")
            raise
        return await self.get_student(student_id)

    async def delete_student(self, student_id: str) -> bool:
        # Check active borrow
        active = await self._fetchone(self._library, "SELECT 1 FROM borrows WHERE student_id=? AND returned=0", (student_id,))
        if active:
            raise ValueError("STUDENT_ACTIVE_BORROW")
        cur = await self._students.execute("DELETE FROM students WHERE id=?", (student_id,))
        await self._students.commit()
        if cur.rowcount == 0:
            raise KeyError("NOT_FOUND")
        return True

    async def suggest_students(self, q: Optional[str]) -> List[Dict[str, Any]]:
        return await self.list_students(q, 10, 0)

    # Books
    async def create_book(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        doc = {
            **payload,
            "id": str(uuid4()),
            "available": True,
            "created_at": ISO(datetime.now(timezone.utc)),
        }
        try:
            await self._library.execute(
                "INSERT INTO books (id,title,author,sbin,stamp,available,created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    doc["id"], doc["title"], doc.get("author"), doc.get("sbin"), doc.get("stamp"), 1 if doc["available"] else 0, doc["created_at"],
                ),
            )
            await self._library.commit()
        except Exception as e:
            if "UNIQUE" in str(e):
                raise ValueError("BOOK_DUPLICATE_CODE")
            raise
        return doc

    async def list_books(self, q: Optional[str], limit: int, skip: int) -> List[Dict[str, Any]]:
        if q:
            q_like = f"%{q}%"
            rows = await self._fetchall(
                self._library,
                "SELECT * FROM books WHERE title LIKE ? OR author LIKE ? OR sbin LIKE ? OR stamp LIKE ? ORDER BY title LIMIT ? OFFSET ?",
                (q_like, q_like, q_like, q_like, min(limit, 100), skip),
            )
        else:
            rows = await self._fetchall(
                self._library, "SELECT * FROM books ORDER BY title LIMIT ? OFFSET ?", (min(limit, 100), skip)
            )
        for r in rows:
            r["available"] = bool(r.get("available", 1))
        return rows

    async def get_book(self, book_id: str) -> Dict[str, Any]:
        row = await self._fetchone(self._library, "SELECT * FROM books WHERE id=?", (book_id,))
        if not row:
            raise KeyError("NOT_FOUND")
        r = dict(row)
        r["available"] = bool(r.get("available", 1))
        return r

    async def get_book_by_code(self, code: str) -> Dict[str, Any]:
        row = await self._fetchone(self._library, "SELECT * FROM books WHERE sbin=? OR stamp=?", (code, code))
        if not row:
            raise KeyError("NOT_FOUND")
        r = dict(row)
        r["available"] = bool(r.get("available", 1))
        return r

    async def update_book(self, book_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        fields = []
        values = []
        for k, v in payload.items():
            if k == "available":
                v = 1 if v else 0
            fields.append(f"{k}=?")
            values.append(v)
        values.append(book_id)
        try:
            await self._library.execute(f"UPDATE books SET {', '.join(fields)} WHERE id=?", tuple(values))
            await self._library.commit()
        except Exception as e:
            if "UNIQUE" in str(e):
                raise ValueError("BOOK_DUPLICATE_CODE")
            raise
        return await self.get_book(book_id)

    async def delete_book(self, book_id: str) -> bool:
        active = await self._fetchone(self._library, "SELECT 1 FROM borrows WHERE book_id=? AND returned=0", (book_id,))
        if active:
            raise ValueError("BOOK_ACTIVE_BORROW")
        cur = await self._library.execute("DELETE FROM books WHERE id=?", (book_id,))
        await self._library.commit()
        if cur.rowcount == 0:
            raise KeyError("NOT_FOUND")
        return True

    async def suggest_books(self, q: Optional[str]) -> List[Dict[str, Any]]:
        return await self.list_books(q, 10, 0)

    # Borrow
    async def borrow_book(self, student_id: str, book_code: str) -> Dict[str, Any]:
        # Validate
        student = await self.get_student(student_id)
        book = await self.get_book_by_code(book_code)
        async with self._library.execute("SELECT available FROM books WHERE id=?", (book["id"],)) as cur:
            row = await cur.fetchone()
            if not row or row[0] == 0:
                raise ValueError("BOOK_NOT_AVAILABLE")
        # Transaction
        async with self._library.execute("UPDATE books SET available=0 WHERE id=? AND available=1", (book["id"],)) as cur:
            if cur.rowcount == 0:
                raise ValueError("BOOK_NOT_AVAILABLE")
        borrow_date = datetime.now(timezone.utc)
        due_date = borrow_date + timedelta(days=7)
        doc = {
            "id": str(uuid4()),
            "student_id": student["id"],
            "book_id": book["id"],
            "borrow_date": ISO(borrow_date),
            "due_date": ISO(due_date),
            "returned": False,
        }
        await self._library.execute(
            "INSERT INTO borrows (id,student_id,book_id,borrow_date,due_date,returned) VALUES (?,?,?,?,?,0)",
            (doc["id"], doc["student_id"], doc["book_id"], doc["borrow_date"], doc["due_date"]),
        )
        await self._library.commit()
        return doc

    async def return_book(self, book_code: str) -> Dict[str, Any]:
        book = await self.get_book_by_code(book_code)
        row = await self._fetchone(self._library, "SELECT * FROM borrows WHERE book_id=? AND returned=0", (book["id"],))
        if not row:
            raise ValueError("NO_ACTIVE_BORROW")
        borrow = dict(row)
        now = datetime.now(timezone.utc)
        await self._library.execute("UPDATE borrows SET returned=1, return_date=? WHERE id=?", (ISO(now), borrow["id"]))
        await self._library.execute("UPDATE books SET available=1 WHERE id=?", (book["id"],))
        # Late warnings
        try:
            borrow_dt = datetime.fromisoformat(borrow["borrow_date"])  # type: ignore
        except Exception:
            borrow_dt = now
        if (now - borrow_dt).days > 7:
            await self._students.execute("UPDATE students SET warnings=warnings+1 WHERE id=?", (borrow["student_id"],))
            await self._students.commit()
        await self._library.commit()
        if not borrow.get("due_date"):
            borrow["due_date"] = ISO(borrow_dt + timedelta(days=7))
        borrow["returned"] = True
        borrow["return_date"] = ISO(now)
        return borrow

    async def list_borrows(self, active: bool, limit: int, skip: int) -> List[Dict[str, Any]]:
        if active:
            rows = await self._fetchall(self._library, "SELECT * FROM borrows WHERE returned=0 ORDER BY borrow_date DESC LIMIT ? OFFSET ?", (min(limit,100), skip))
        else:
            rows = await self._fetchall(self._library, "SELECT * FROM borrows ORDER BY borrow_date DESC LIMIT ? OFFSET ?", (min(limit,100), skip))
        for r in rows:
            if not r.get("due_date") and r.get("borrow_date"):
                try:
                    bd = datetime.fromisoformat(r["borrow_date"])  # type: ignore
                    r["due_date"] = ISO(bd + timedelta(days=7))
                except Exception:
                    pass
        return rows