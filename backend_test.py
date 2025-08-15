#!/usr/bin/env python3
"""
BiblioFlow Backend API Test Suite
Tests all CRUD operations and edge cases for the library management system.
"""

import requests
import json
import sys
from datetime import datetime, timedelta
import time

# Base URL from frontend env
BASE_URL = "/api"  # This will be mapped to the correct external URL

class BiblioFlowTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.test_data = {
            'students': [],
            'books': [],
            'borrows': []
        }
        self.results = {
            'passed': 0,
            'failed': 0,
            'errors': []
        }

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def assert_response(self, response, expected_status, test_name):
        """Assert response status and log results"""
        try:
            if response.status_code == expected_status:
                self.log(f"✅ {test_name} - Status: {response.status_code}")
                self.results['passed'] += 1
                return True
            else:
                self.log(f"❌ {test_name} - Expected: {expected_status}, Got: {response.status_code}", "ERROR")
                self.log(f"Response: {response.text}", "ERROR")
                self.results['failed'] += 1
                self.results['errors'].append(f"{test_name}: Expected {expected_status}, got {response.status_code}")
                return False
        except Exception as e:
            self.log(f"❌ {test_name} - Exception: {str(e)}", "ERROR")
            self.results['failed'] += 1
            self.results['errors'].append(f"{test_name}: Exception - {str(e)}")
            return False

    def test_health_endpoint(self):
        """Test GET /api/health"""
        self.log("Testing Health Endpoint...")
        try:
            response = self.session.get(f"{self.base_url}/health")
            if self.assert_response(response, 200, "Health Check"):
                data = response.json()
                if data.get('ok') is True:
                    self.log("✅ Health endpoint returns correct format")
                else:
                    self.log("❌ Health endpoint missing 'ok: true'", "ERROR")
                    self.results['errors'].append("Health endpoint missing 'ok: true'")
        except Exception as e:
            self.log(f"❌ Health endpoint failed: {str(e)}", "ERROR")
            self.results['errors'].append(f"Health endpoint: {str(e)}")

    def test_students_crud(self):
        """Test Students CRUD operations"""
        self.log("Testing Students CRUD...")
        
        # Test CREATE student
        student_data = {
            "name": "Alice Johnson",
            "admission_number": "STU2024001",
            "class_name": "Grade 10A"
        }
        
        try:
            response = self.session.post(f"{self.base_url}/students", json=student_data)
            if self.assert_response(response, 201, "Create Student"):
                student = response.json()
                self.test_data['students'].append(student)
                self.log(f"Created student with ID: {student['id']}")
                
                # Verify required fields
                if all(key in student for key in ['id', 'name', 'admission_number']):
                    self.log("✅ Student creation returns all required fields")
                else:
                    self.log("❌ Student creation missing required fields", "ERROR")
        except Exception as e:
            self.log(f"❌ Create student failed: {str(e)}", "ERROR")

        # Test duplicate admission number
        try:
            response = self.session.post(f"{self.base_url}/students", json=student_data)
            self.assert_response(response, 400, "Duplicate Admission Number")
        except Exception as e:
            self.log(f"❌ Duplicate admission test failed: {str(e)}", "ERROR")

        # Test GET students (list)
        try:
            response = self.session.get(f"{self.base_url}/students")
            if self.assert_response(response, 200, "List Students"):
                students = response.json()
                if isinstance(students, list) and len(students) > 0:
                    self.log(f"✅ Retrieved {len(students)} students")
                else:
                    self.log("❌ Students list is empty or invalid format", "ERROR")
        except Exception as e:
            self.log(f"❌ List students failed: {str(e)}", "ERROR")

        # Test search students
        try:
            response = self.session.get(f"{self.base_url}/students?q=Alice")
            if self.assert_response(response, 200, "Search Students"):
                students = response.json()
                if len(students) > 0 and "Alice" in students[0]['name']:
                    self.log("✅ Student search working correctly")
                else:
                    self.log("❌ Student search not working", "ERROR")
        except Exception as e:
            self.log(f"❌ Search students failed: {str(e)}", "ERROR")

        # Test UPDATE student
        if self.test_data['students']:
            student_id = self.test_data['students'][0]['id']
            update_data = {
                "name": "Alice Johnson Updated",
                "admission_number": "STU2024001",
                "class_name": "Grade 11A"
            }
            try:
                response = self.session.put(f"{self.base_url}/students/{student_id}", json=update_data)
                if self.assert_response(response, 200, "Update Student"):
                    updated_student = response.json()
                    if updated_student['name'] == "Alice Johnson Updated":
                        self.log("✅ Student update working correctly")
                    else:
                        self.log("❌ Student update not reflecting changes", "ERROR")
            except Exception as e:
                self.log(f"❌ Update student failed: {str(e)}", "ERROR")

    def test_books_crud(self):
        """Test Books CRUD operations"""
        self.log("Testing Books CRUD...")
        
        # Test CREATE book with SBIN
        book_data = {
            "title": "Python Programming Fundamentals",
            "author": "John Smith",
            "sbin": "SBIN123456"
        }
        
        try:
            response = self.session.post(f"{self.base_url}/books", json=book_data)
            if self.assert_response(response, 201, "Create Book with SBIN"):
                book = response.json()
                self.test_data['books'].append(book)
                self.log(f"Created book with ID: {book['id']}")
        except Exception as e:
            self.log(f"❌ Create book failed: {str(e)}", "ERROR")

        # Test CREATE book with Stamp
        book_data2 = {
            "title": "Advanced Mathematics",
            "author": "Jane Doe",
            "stamp": "STAMP789"
        }
        
        try:
            response = self.session.post(f"{self.base_url}/books", json=book_data2)
            if self.assert_response(response, 201, "Create Book with Stamp"):
                book = response.json()
                self.test_data['books'].append(book)
        except Exception as e:
            self.log(f"❌ Create book with stamp failed: {str(e)}", "ERROR")

        # Test CREATE book without SBIN or Stamp (should fail)
        invalid_book = {
            "title": "Invalid Book",
            "author": "No Code"
        }
        
        try:
            response = self.session.post(f"{self.base_url}/books", json=invalid_book)
            self.assert_response(response, 400, "Create Book without SBIN/Stamp")
        except Exception as e:
            self.log(f"❌ Invalid book test failed: {str(e)}", "ERROR")

        # Test duplicate SBIN
        try:
            response = self.session.post(f"{self.base_url}/books", json=book_data)
            self.assert_response(response, 400, "Duplicate SBIN")
        except Exception as e:
            self.log(f"❌ Duplicate SBIN test failed: {str(e)}", "ERROR")

        # Test GET books (list)
        try:
            response = self.session.get(f"{self.base_url}/books")
            if self.assert_response(response, 200, "List Books"):
                books = response.json()
                if isinstance(books, list) and len(books) > 0:
                    self.log(f"✅ Retrieved {len(books)} books")
                else:
                    self.log("❌ Books list is empty or invalid format", "ERROR")
        except Exception as e:
            self.log(f"❌ List books failed: {str(e)}", "ERROR")

        # Test GET book by code
        if self.test_data['books']:
            book = self.test_data['books'][0]
            code = book.get('sbin') or book.get('stamp')
            if code:
                try:
                    response = self.session.get(f"{self.base_url}/books/by-code/{code}")
                    if self.assert_response(response, 200, "Get Book by Code"):
                        retrieved_book = response.json()
                        if retrieved_book['id'] == book['id']:
                            self.log("✅ Get book by code working correctly")
                        else:
                            self.log("❌ Get book by code returned wrong book", "ERROR")
                except Exception as e:
                    self.log(f"❌ Get book by code failed: {str(e)}", "ERROR")

    def test_borrow_return_flow(self):
        """Test Borrow and Return operations"""
        self.log("Testing Borrow/Return Flow...")
        
        if not self.test_data['students'] or not self.test_data['books']:
            self.log("❌ Cannot test borrow/return - missing students or books", "ERROR")
            return

        student = self.test_data['students'][0]
        book = self.test_data['books'][0]
        book_code = book.get('sbin') or book.get('stamp')

        # Test BORROW
        borrow_data = {
            "student_id": student['id'],
            "book_code": book_code
        }
        
        try:
            response = self.session.post(f"{self.base_url}/borrow", json=borrow_data)
            if self.assert_response(response, 201, "Borrow Book"):
                borrow = response.json()
                self.test_data['borrows'].append(borrow)
                self.log(f"Created borrow with ID: {borrow['id']}")
                
                # Verify borrow fields
                required_fields = ['id', 'student_id', 'book_id', 'borrow_date', 'returned']
                if all(field in borrow for field in required_fields):
                    self.log("✅ Borrow creation returns all required fields")
                else:
                    self.log("❌ Borrow creation missing required fields", "ERROR")
        except Exception as e:
            self.log(f"❌ Borrow book failed: {str(e)}", "ERROR")

        # Test borrow unavailable book (should fail)
        try:
            response = self.session.post(f"{self.base_url}/borrow", json=borrow_data)
            self.assert_response(response, 400, "Borrow Unavailable Book")
        except Exception as e:
            self.log(f"❌ Borrow unavailable book test failed: {str(e)}", "ERROR")

        # Test GET active borrows
        try:
            response = self.session.get(f"{self.base_url}/borrows?active=true")
            if self.assert_response(response, 200, "Get Active Borrows"):
                borrows = response.json()
                if isinstance(borrows, list) and len(borrows) > 0:
                    self.log(f"✅ Retrieved {len(borrows)} active borrows")
                    # Check if our borrow is in the list
                    if any(b['id'] == self.test_data['borrows'][0]['id'] for b in borrows):
                        self.log("✅ Active borrow found in list")
                    else:
                        self.log("❌ Active borrow not found in list", "ERROR")
                else:
                    self.log("❌ Active borrows list is empty", "ERROR")
        except Exception as e:
            self.log(f"❌ Get active borrows failed: {str(e)}", "ERROR")

        # Test RETURN
        return_data = {
            "book_code": book_code
        }
        
        try:
            response = self.session.post(f"{self.base_url}/return", json=return_data)
            if self.assert_response(response, 200, "Return Book"):
                returned_borrow = response.json()
                if returned_borrow.get('returned') is True:
                    self.log("✅ Book return working correctly")
                else:
                    self.log("❌ Book return not marking as returned", "ERROR")
        except Exception as e:
            self.log(f"❌ Return book failed: {str(e)}", "ERROR")

        # Test return non-borrowed book (should fail)
        try:
            response = self.session.post(f"{self.base_url}/return", json=return_data)
            self.assert_response(response, 400, "Return Non-borrowed Book")
        except Exception as e:
            self.log(f"❌ Return non-borrowed book test failed: {str(e)}", "ERROR")

    def test_delete_operations(self):
        """Test DELETE operations with constraints"""
        self.log("Testing Delete Operations...")
        
        # Test delete book (should work now that it's returned)
        if self.test_data['books']:
            book_id = self.test_data['books'][0]['id']
            try:
                response = self.session.delete(f"{self.base_url}/books/{book_id}")
                self.assert_response(response, 200, "Delete Book")
            except Exception as e:
                self.log(f"❌ Delete book failed: {str(e)}", "ERROR")

        # Test delete student (should work now that borrow is returned)
        if self.test_data['students']:
            student_id = self.test_data['students'][0]['id']
            try:
                response = self.session.delete(f"{self.base_url}/students/{student_id}")
                self.assert_response(response, 200, "Delete Student")
            except Exception as e:
                self.log(f"❌ Delete student failed: {str(e)}", "ERROR")

    def run_all_tests(self):
        """Run all test suites"""
        self.log("Starting BiblioFlow Backend API Tests...")
        self.log("=" * 50)
        
        # Test in logical order
        self.test_health_endpoint()
        self.test_students_crud()
        self.test_books_crud()
        self.test_borrow_return_flow()
        self.test_delete_operations()
        
        # Print summary
        self.log("=" * 50)
        self.log("TEST SUMMARY")
        self.log(f"✅ Passed: {self.results['passed']}")
        self.log(f"❌ Failed: {self.results['failed']}")
        
        if self.results['errors']:
            self.log("\nERRORS ENCOUNTERED:")
            for error in self.results['errors']:
                self.log(f"  - {error}")
        
        return self.results['failed'] == 0

if __name__ == "__main__":
    tester = BiblioFlowTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)