#!/usr/bin/env python3
"""
Final edge case testing for BiblioFlow API
"""

import requests
import json
from datetime import datetime

BASE_URL = "https://85959c47-17a3-48f6-99ae-9ff711e8710f.preview.emergentagent.com/api"

def test_edge_cases():
    session = requests.Session()
    
    print("=== EDGE CASE TESTING ===")
    
    # Test 1: Health endpoint
    print("\n1. Testing Health Endpoint:")
    response = session.get(f"{BASE_URL}/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    
    # Test 2: Book creation without SBIN or Stamp
    print("\n2. Testing Book Creation without SBIN/Stamp:")
    response = session.post(f"{BASE_URL}/books", json={
        "title": "Test Book",
        "author": "Test Author"
    })
    print(f"   Status: {response.status_code} (Expected: 400)")
    print(f"   Response: {response.json()}")
    
    # Test 3: Get book by code (existing book)
    print("\n3. Testing Get Book by Code:")
    # First get existing books
    books_response = session.get(f"{BASE_URL}/books")
    books = books_response.json()
    if books:
        book = books[0]
        code = book.get('sbin') or book.get('stamp')
        if code:
            response = session.get(f"{BASE_URL}/books/by-code/{code}")
            print(f"   Status: {response.status_code}")
            print(f"   Found book: {response.json()['title']}")
    
    # Test 4: Borrow unavailable book
    print("\n4. Testing Borrow Unavailable Book:")
    # Get a student and book
    students = session.get(f"{BASE_URL}/students").json()
    books = session.get(f"{BASE_URL}/books").json()
    
    if students and books:
        student = students[0]
        book = books[0]
        book_code = book.get('sbin') or book.get('stamp')
        
        # First borrow
        borrow_response = session.post(f"{BASE_URL}/borrow", json={
            "student_id": student['id'],
            "book_code": book_code
        })
        print(f"   First borrow status: {borrow_response.status_code}")
        
        # Try to borrow again (should fail)
        second_borrow = session.post(f"{BASE_URL}/borrow", json={
            "student_id": student['id'],
            "book_code": book_code
        })
        print(f"   Second borrow status: {second_borrow.status_code} (Expected: 400)")
        print(f"   Response: {second_borrow.json()}")
        
        # Test 5: Return non-borrowed book
        print("\n5. Testing Return Non-borrowed Book:")
        # First return the book
        return_response = session.post(f"{BASE_URL}/return", json={
            "book_code": book_code
        })
        print(f"   First return status: {return_response.status_code}")
        
        # Try to return again (should fail)
        second_return = session.post(f"{BASE_URL}/return", json={
            "book_code": book_code
        })
        print(f"   Second return status: {second_return.status_code} (Expected: 400)")
        print(f"   Response: {second_return.json()}")
    
    # Test 6: Active borrows
    print("\n6. Testing Active Borrows:")
    response = session.get(f"{BASE_URL}/borrows?active=true")
    print(f"   Status: {response.status_code}")
    print(f"   Active borrows count: {len(response.json())}")
    
    print("\n=== EDGE CASE TESTING COMPLETE ===")

if __name__ == "__main__":
    test_edge_cases()
