import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError

# FastAPI app
app = FastAPI(title="BiblioFlow Web API", openapi_url="/api/openapi.json", docs_url="/api/docs")

# CORS (allow all origins by default for MVP; can be tightened later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB setup
MONGO_URL = os.environ.get("MONGO_URL")
if not MONGO_URL:
    raise RuntimeError("MONGO_URL environment variable is required")

client = AsyncIOMotorClient(MONGO_URL)
try:
    db = client.get_default_database()
except Exception:
    db = None

if db is None:
    # Fallback to a default database name if not supplied in URL
    # NOTE: It's recommended to include the DB name in MONGO_URL
    db = client["biblioflow"]

students_col = db["students"]
books_col = db["books"]
borrows_col = db["borrows"]

# Pydantic models
class StudentIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    admission_number: str = Field(..., min_length=1, max_length=50)
    class_name: Optional[str] = Field(default=None, max_length=50)

class StudentOut(StudentIn):
    id: str
    warnings: int = 0

class BookIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    author: Optional[str] = Field(default=None, max_length=200)
    sbin: Optional[str] = Field(default=None, max_length=100)
    stamp: Optional[str] = Field(default=None, max_length=100)

class BookOut(BookIn):
    id: str
    available: bool = True

class BorrowCreate(BaseModel):
    student_id: str
    book_code: str

class ReturnCreate(BaseModel):
    book_code: str

class BorrowOut(BaseModel):
    id: str
    student_id: str
    book_id: str
    borrow_date: str
    return_date: Optional[str] = None
    returned: bool
    due_date: Optional[str] = None

# Utils

def to_student(doc: Dict[str, Any]) -> StudentOut:
    return StudentOut(
        id=doc["id"],
        name=doc["name"],
        admission_number=doc["admission_number"],
        class_name=doc.get("class_name"),
        warnings=doc.get("warnings", 0),
    )


def to_book(doc: Dict[str, Any]) -> BookOut:
    return BookOut(
        id=doc["id"],
        title=doc["title"],
        author=doc.get("author"),
        sbin=doc.get("sbin"),
        stamp=doc.get("stamp"),
        available=doc.get("available", True),
    )


def to_borrow(doc: Dict[str, Any]) -> BorrowOut:
    return BorrowOut(
        id=doc["id"],
        student_id=doc["student_id"],
        book_id=doc["book_id"],
        borrow_date=doc["borrow_date"],
        return_date=doc.get("return_date"),
        returned=doc.get("returned", False),
        due_date=doc.get("due_date"),
    )


@app.on_event("startup")
async def on_startup():
    # Create indexes
    await students_col.create_index("id", unique=True)
    await students_col.create_index("admission_number", unique=True)
    await books_col.create_index("id", unique=True)
    # Unique sparse indexes for either code
    await books_col.create_index("sbin", unique=True, sparse=True)
    await books_col.create_index("stamp", unique=True, sparse=True)
    await borrows_col.create_index("id", unique=True)
    await borrows_col.create_index([("book_id", 1), ("returned", 1)])
    await borrows_col.create_index([("student_id", 1), ("returned", 1)])


# Health
@app.get("/api/health")
async def health():
    return {"ok": True, "service": "biblioflow"}


# Students CRUD
@app.post("/api/students", response_model=StudentOut)
async def create_student(student: StudentIn):
    doc = student.model_dump()
    doc.update({
        "id": str(uuid4()),
        "warnings": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        await students_col.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Admission number already exists")
    return to_student(doc)


@app.get("/api/students", response_model=List[StudentOut])
async def list_students(q: Optional[str] = None, limit: int = 50, skip: int = 0):
    query: Dict[str, Any] = {}
    if q:
        query = {
            "$or": [
                {"name": {"$regex": q, "$options": "i"}},
                {"admission_number": {"$regex": q, "$options": "i"}},
                {"class_name": {"$regex": q, "$options": "i"}},
            ]
        }
    cursor = students_col.find(query).skip(skip).limit(min(limit, 100)).sort("name")
    items = [to_student(d) async for d in cursor]
    return items


@app.get("/api/students/{student_id}", response_model=StudentOut)
async def get_student(student_id: str):
    doc = await students_col.find_one({"id": student_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Student not found")
    return to_student(doc)


@app.put("/api/students/{student_id}", response_model=StudentOut)
async def update_student(student_id: str, payload: StudentIn):
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        res = await students_col.find_one_and_update(
            {"id": student_id},
            {"$set": update},
            return_document=True,
        )
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Admission number already exists")
    if not res:
        raise HTTPException(status_code=404, detail="Student not found")
    return to_student(res)


@app.delete("/api/students/{student_id}")
async def delete_student(student_id: str):
    # Prevent deletion if student has active borrow
    active = await borrows_col.find_one({"student_id": student_id, "returned": False})
    if active:
        raise HTTPException(status_code=400, detail="Student has active borrow")
    res = await students_col.delete_one({"id": student_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"deleted": True}


# Books CRUD
@app.post("/api/books", response_model=BookOut)
async def create_book(book: BookIn):
    if not book.sbin and not book.stamp:
        raise HTTPException(status_code=400, detail="Provide at least SBIN or Stamp code")
    doc = book.model_dump()
    doc.update({
        "id": str(uuid4()),
        "available": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        await books_col.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Duplicate SBIN or Stamp code")
    return to_book(doc)


@app.get("/api/books", response_model=List[BookOut])
async def list_books(q: Optional[str] = None, limit: int = 50, skip: int = 0):
    query: Dict[str, Any] = {}
    if q:
        query = {
            "$or": [
                {"title": {"$regex": q, "$options": "i"}},
                {"author": {"$regex": q, "$options": "i"}},
                {"sbin": {"$regex": q, "$options": "i"}},
                {"stamp": {"$regex": q, "$options": "i"}},
            ]
        }
    cursor = books_col.find(query).skip(skip).limit(min(limit, 100)).sort("title")
    items = [to_book(d) async for d in cursor]
    return items


@app.get("/api/books/{book_id}", response_model=BookOut)
async def get_book(book_id: str):
    doc = await books_col.find_one({"id": book_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Book not found")
    return to_book(doc)


@app.get("/api/books/by-code/{code}", response_model=BookOut)
async def get_book_by_code(code: str):
    doc = await books_col.find_one({"$or": [{"sbin": code}, {"stamp": code}]})
    if not doc:
        raise HTTPException(status_code=404, detail="Book not found")
    return to_book(doc)


@app.put("/api/books/{book_id}", response_model=BookOut)
async def update_book(book_id: str, payload: BookIn):
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        res = await books_col.find_one_and_update(
            {"id": book_id}, {"$set": update}, return_document=True
        )
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Duplicate SBIN or Stamp code")
    if not res:
        raise HTTPException(status_code=404, detail="Book not found")
    return to_book(res)


@app.delete("/api/books/{book_id}")
async def delete_book(book_id: str):
    active = await borrows_col.find_one({"book_id": book_id, "returned": False})
    if active:
        raise HTTPException(status_code=400, detail="Book is currently borrowed")
    res = await books_col.delete_one({"id": book_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"deleted": True}


# Borrow / Return
@app.post("/api/borrow", response_model=BorrowOut)
async def borrow_book(payload: BorrowCreate):
    student = await students_col.find_one({"id": payload.student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    book = await books_col.find_one({"$or": [{"sbin": payload.book_code}, {"stamp": payload.book_code}]})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if not book.get("available", True):
        raise HTTPException(status_code=400, detail="Book is not available")

    borrow_date = datetime.now(timezone.utc)
    due_date = borrow_date + timedelta(days=7)
    borrow_doc = {
        "id": str(uuid4()),
        "student_id": student["id"],
        "book_id": book["id"],
        "borrow_date": borrow_date.isoformat(),
        "due_date": due_date.isoformat(),
        "returned": False,
    }

    # Perform atomically: set book unavailable and insert borrow
    async with await client.start_session() as s:
        async with s.start_transaction():
            await books_col.update_one({"id": book["id"], "available": True}, {"$set": {"available": False}})
            await borrows_col.insert_one(borrow_doc)

    return to_borrow(borrow_doc)


@app.post("/api/return", response_model=BorrowOut)
async def return_book(payload: ReturnCreate):
    book = await books_col.find_one({"$or": [{"sbin": payload.book_code}, {"stamp": payload.book_code}]})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    borrow = await borrows_col.find_one({"book_id": book["id"], "returned": False})
    if not borrow:
        raise HTTPException(status_code=400, detail="No active borrow for this book")

    now = datetime.now(timezone.utc)
    return_date = now.isoformat()
    returned_borrow = await borrows_col.find_one_and_update(
        {"id": borrow["id"]},
        {"$set": {"returned": True, "return_date": return_date}},
        return_document=True,
    )
    await books_col.update_one({"id": book["id"]}, {"$set": {"available": True}})

    # Update warnings if late
    try:
        borrow_dt = datetime.fromisoformat(borrow["borrow_date"])
    except Exception:
        borrow_dt = now
    days = (now - borrow_dt).days
    if days > 7:
        await students_col.update_one({"id": borrow["student_id"]}, {"$inc": {"warnings": 1}})

    # Merge due_date if exists
    if "due_date" not in returned_borrow:
        returned_borrow["due_date"] = (borrow_dt + timedelta(days=7)).isoformat()

    return to_borrow(returned_borrow)


@app.get("/api/borrows", response_model=List[BorrowOut])
async def list_borrows(active: bool = True, limit: int = 50, skip: int = 0):
    query = {"returned": False} if active else {}
    cursor = borrows_col.find(query).skip(skip).limit(min(limit, 100)).sort("borrow_date", -1)
    items = []
    async for d in cursor:
        if "due_date" not in d and d.get("borrow_date"):
            try:
                bd = datetime.fromisoformat(d["borrow_date"])
                d["due_date"] = (bd + timedelta(days=7)).isoformat()
            except Exception:
                pass
        items.append(to_borrow(d))
    return items


# Suggestions
@app.get("/api/suggest/students", response_model=List[StudentOut])
async def suggest_students(q: str = Query("", min_length=0)): 
    query: Dict[str, Any] = {}
    if q:
        query = {
            "$or": [
                {"name": {"$regex": q, "$options": "i"}},
                {"admission_number": {"$regex": q, "$options": "i"}},
            ]
        }
    cursor = students_col.find(query).limit(10).sort("name")
    return [to_student(d) async for d in cursor]


@app.get("/api/suggest/books", response_model=List[BookOut])
async def suggest_books(q: str = Query("", min_length=0)):
    query: Dict[str, Any] = {}
    if q:
        query = {
            "$or": [
                {"title": {"$regex": q, "$options": "i"}},
                {"sbin": {"$regex": q, "$options": "i"}},
                {"stamp": {"$regex": q, "$options": "i"}},
            ]
        }
    cursor = books_col.find(query).limit(10).sort("title")
    return [to_book(d) async for d in cursor]