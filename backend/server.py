import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from db import MongoRepo, SQLiteRepo, AbstractRepo

# FastAPI app
app = FastAPI(title="BiblioFlow Web API", openapi_url="/api/openapi.json", docs_url="/api/docs")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Choose DB backend: prefer Mongo if MONGO_URL is set, otherwise use SQLite files
MONGO_URL = os.environ.get("MONGO_URL", "").strip()
repo: AbstractRepo
if MONGO_URL:
    repo = MongoRepo(MONGO_URL)
else:
    repo = SQLiteRepo()

# Pydantic models
class StudentIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    admission_number: str = Field(..., min_length=6, max_length=6)
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


@app.on_event("startup")
async def on_startup():
    await repo.init()


# Health
@app.get("/api/health")
async def health():
    return {"ok": True, "service": "biblioflow", "db": repo.__class__.__name__}


# Students CRUD
@app.post("/api/students", response_model=StudentOut)
async def create_student(student: StudentIn):
    # admission_number length is enforced by Pydantic (6 chars)
    try:
        doc = await repo.create_student(student.model_dump())
    except ValueError as e:
        if str(e) == "ADMISSION_DUPLICATE":
            raise HTTPException(status_code=400, detail="Admission number already exists")
        raise
    return doc  # type: ignore


@app.get("/api/students", response_model=List[StudentOut])
async def list_students(q: Optional[str] = None, limit: int = 50, skip: int = 0):
    return await repo.list_students(q, limit, skip)  # type: ignore


@app.get("/api/students/{student_id}", response_model=StudentOut)
async def get_student(student_id: str):
    try:
        return await repo.get_student(student_id)  # type: ignore
    except KeyError:
        raise HTTPException(status_code=404, detail="Student not found")


@app.put("/api/students/{student_id}", response_model=StudentOut)
async def update_student(student_id: str, payload: StudentIn):
    try:
        return await repo.update_student(student_id, payload.model_dump())  # type: ignore
    except KeyError:
        raise HTTPException(status_code=404, detail="Student not found")
    except ValueError as e:
        if str(e) == "ADMISSION_DUPLICATE":
            raise HTTPException(status_code=400, detail="Admission number already exists")
        raise


@app.delete("/api/students/{student_id}")
async def delete_student(student_id: str):
    try:
        await repo.delete_student(student_id)
        return {"deleted": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Student not found")
    except ValueError as e:
        if str(e) == "STUDENT_ACTIVE_BORROW":
            raise HTTPException(status_code=400, detail="Student has active borrow")
        raise


# Books CRUD
@app.post("/api/books", response_model=BookOut)
async def create_book(book: BookIn):
    if not book.sbin and not book.stamp:
        raise HTTPException(status_code=400, detail="Provide at least SBIN or Stamp code")
    try:
        return await repo.create_book(book.model_dump())  # type: ignore
    except ValueError as e:
        if str(e) == "BOOK_DUPLICATE_CODE":
            raise HTTPException(status_code=400, detail="Duplicate SBIN or Stamp code")
        raise


@app.get("/api/books", response_model=List[BookOut])
async def list_books(q: Optional[str] = None, limit: int = 50, skip: int = 0):
    return await repo.list_books(q, limit, skip)  # type: ignore


@app.get("/api/books/{book_id}", response_model=BookOut)
async def get_book(book_id: str):
    try:
        return await repo.get_book(book_id)  # type: ignore
    except KeyError:
        raise HTTPException(status_code=404, detail="Book not found")


@app.get("/api/books/by-code/{code}", response_model=BookOut)
async def get_book_by_code(code: str):
    try:
        return await repo.get_book_by_code(code)  # type: ignore
    except KeyError:
        raise HTTPException(status_code=404, detail="Book not found")


@app.put("/api/books/{book_id}", response_model=BookOut)
async def update_book(book_id: str, payload: BookIn):
    try:
        return await repo.update_book(book_id, payload.model_dump())  # type: ignore
    except KeyError:
        raise HTTPException(status_code=404, detail="Book not found")
    except ValueError as e:
        if str(e) == "BOOK_DUPLICATE_CODE":
            raise HTTPException(status_code=400, detail="Duplicate SBIN or Stamp code")
        raise


@app.delete("/api/books/{book_id}")
async def delete_book(book_id: str):
    try:
        await repo.delete_book(book_id)
        return {"deleted": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Book not found")
    except ValueError as e:
        if str(e) == "BOOK_ACTIVE_BORROW":
            raise HTTPException(status_code=400, detail="Book is currently borrowed")
        raise


# Borrow / Return
@app.post("/api/borrow", response_model=BorrowOut)
async def borrow_book(payload: BorrowCreate):
    try:
        return await repo.borrow_book(payload.student_id, payload.book_code)  # type: ignore
    except KeyError as e:
        if str(e) == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="Student or Book not found")
        raise
    except ValueError as e:
        if str(e) == "BOOK_NOT_AVAILABLE":
            raise HTTPException(status_code=400, detail="Book is not available")
        raise


@app.post("/api/return", response_model=BorrowOut)
async def return_book(payload: ReturnCreate):
    try:
        return await repo.return_book(payload.book_code)  # type: ignore
    except ValueError as e:
        if str(e) == "NO_ACTIVE_BORROW":
            raise HTTPException(status_code=400, detail="No active borrow for this book")
        raise
    except KeyError:
        raise HTTPException(status_code=404, detail="Book not found")


@app.get("/api/borrows", response_model=List[BorrowOut])
async def list_borrows(active: bool = True, limit: int = 50, skip: int = 0):
    return await repo.list_borrows(active, limit, skip)  # type: ignore


# Suggestions
@app.get("/api/suggest/students", response_model=List[StudentOut])
async def suggest_students(q: str = Query("", min_length=0)):
    return await repo.suggest_students(q)  # type: ignore


@app.get("/api/suggest/books", response_model=List[BookOut])
async def suggest_books(q: str = Query("", min_length=0)):
    return await repo.suggest_books(q)  # type: ignore