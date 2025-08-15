#!/usr/bin/env python3
"""
Focused Backend Test for Repository Abstraction and Admission Number Length Rule
Tests specific requirements from review request.
"""

import requests
import json
import sys
from datetime import datetime
import time
import random

# Base URL from frontend env
BASE_URL = "https://85959c47-17a3-48f6-99ae-9ff711e8710f.preview.emergentagent.com/api"

class FocusedTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
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

    def test_health_with_db_info(self):
        """Test GET /api/health returns { ok: true, db: <MongoRepo or SQLiteRepo> }"""
        self.log("Testing Health Endpoint with DB Info...")
        try:
            response = self.session.get(f"{self.base_url}/health")
            if self.assert_response(response, 200, "Health Check"):
                data = response.json()
                self.log(f"Health response: {data}")
                
                # Check required fields
                if data.get('ok') is True:
                    self.log("✅ Health endpoint returns 'ok: true'")
                    self.results['passed'] += 1
                else:
                    self.log("❌ Health endpoint missing 'ok: true'", "ERROR")
                    self.results['failed'] += 1
                    self.results['errors'].append("Health endpoint missing 'ok: true'")
                
                # Check db field shows repository type
                db_type = data.get('db')
                if db_type in ['MongoRepo', 'SQLiteRepo']:
                    self.log(f"✅ Health endpoint shows DB type: {db_type}")
                    self.results['passed'] += 1
                else:
                    self.log(f"❌ Health endpoint missing or invalid 'db' field: {db_type}", "ERROR")
                    self.results['failed'] += 1
                    self.results['errors'].append(f"Health endpoint invalid 'db' field: {db_type}")
                    
        except Exception as e:
            self.log(f"❌ Health endpoint failed: {str(e)}", "ERROR")
            self.results['errors'].append(f"Health endpoint: {str(e)}")

    def test_admission_number_length_validation(self):
        """Test admission_number length validation - reject non-6 chars with 422, accept exactly 6"""
        self.log("Testing Admission Number Length Validation...")
        
        # Generate unique base for testing
        timestamp = str(int(time.time()))[-6:]  # Last 6 digits
        
        # Test 1: admission_number too short (5 chars) - should return 422
        short_student = {
            "name": "Test Student Short",
            "admission_number": "12345",  # 5 chars
            "class_name": "Grade 10"
        }
        
        try:
            response = self.session.post(f"{self.base_url}/students", json=short_student)
            self.assert_response(response, 422, "Admission Number Too Short (5 chars)")
        except Exception as e:
            self.log(f"❌ Short admission number test failed: {str(e)}", "ERROR")

        # Test 2: admission_number too long (7 chars) - should return 422
        long_student = {
            "name": "Test Student Long",
            "admission_number": "1234567",  # 7 chars
            "class_name": "Grade 10"
        }
        
        try:
            response = self.session.post(f"{self.base_url}/students", json=long_student)
            self.assert_response(response, 422, "Admission Number Too Long (7 chars)")
        except Exception as e:
            self.log(f"❌ Long admission number test failed: {str(e)}", "ERROR")

        # Test 3: admission_number exactly 6 chars - should succeed (200)
        valid_student = {
            "name": "Test Student Valid",
            "admission_number": timestamp,  # Exactly 6 chars
            "class_name": "Grade 10"
        }
        
        try:
            response = self.session.post(f"{self.base_url}/students", json=valid_student)
            if self.assert_response(response, 200, "Admission Number Exactly 6 chars"):
                student = response.json()
                self.log(f"Created student with 6-char admission number: {student['admission_number']}")
                # Store for cleanup
                self.valid_student_id = student['id']
        except Exception as e:
            self.log(f"❌ Valid admission number test failed: {str(e)}", "ERROR")

    def test_books_creation(self):
        """Test POST /api/books still works"""
        self.log("Testing Books Creation...")
        
        # Generate unique identifiers
        unique_id = str(int(time.time() * 1000)) + str(random.randint(1000, 9999))
        
        # Test book creation with SBIN
        book_data = {
            "title": f"Test Book {unique_id}",
            "author": "Test Author",
            "sbin": f"SB{unique_id}"
        }
        
        try:
            response = self.session.post(f"{self.base_url}/books", json=book_data)
            if self.assert_response(response, 200, "Create Book with SBIN"):
                book = response.json()
                self.log(f"Created book with ID: {book['id']}")
                self.test_book_id = book['id']
                self.test_book_code = book['sbin']
        except Exception as e:
            self.log(f"❌ Create book failed: {str(e)}", "ERROR")

    def test_borrow_return_flow(self):
        """Test Borrow/Return flow still works"""
        self.log("Testing Borrow/Return Flow...")
        
        # Check if we have test data from previous tests
        if not hasattr(self, 'valid_student_id') or not hasattr(self, 'test_book_code'):
            self.log("❌ Missing test data for borrow/return test", "ERROR")
            return

        # Test BORROW
        borrow_data = {
            "student_id": self.valid_student_id,
            "book_code": self.test_book_code
        }
        
        try:
            response = self.session.post(f"{self.base_url}/borrow", json=borrow_data)
            if self.assert_response(response, 200, "Borrow Book"):
                borrow = response.json()
                self.log(f"Created borrow with ID: {borrow['id']}")
        except Exception as e:
            self.log(f"❌ Borrow book failed: {str(e)}", "ERROR")
            return

        # Test RETURN
        return_data = {
            "book_code": self.test_book_code
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

    def cleanup_test_data(self):
        """Clean up test data"""
        self.log("Cleaning up test data...")
        
        # Delete test book
        if hasattr(self, 'test_book_id'):
            try:
                response = self.session.delete(f"{self.base_url}/books/{self.test_book_id}")
                if response.status_code == 200:
                    self.log("✅ Test book deleted")
            except Exception as e:
                self.log(f"Failed to delete test book: {str(e)}", "WARN")

        # Delete test student
        if hasattr(self, 'valid_student_id'):
            try:
                response = self.session.delete(f"{self.base_url}/students/{self.valid_student_id}")
                if response.status_code == 200:
                    self.log("✅ Test student deleted")
            except Exception as e:
                self.log(f"Failed to delete test student: {str(e)}", "WARN")

    def run_focused_tests(self):
        """Run focused test suite"""
        self.log("Starting Focused Backend Tests...")
        self.log("=" * 60)
        
        # Run tests in order
        self.test_health_with_db_info()
        self.test_admission_number_length_validation()
        self.test_books_creation()
        self.test_borrow_return_flow()
        
        # Cleanup
        self.cleanup_test_data()
        
        # Print summary
        self.log("=" * 60)
        self.log("FOCUSED TEST SUMMARY")
        self.log(f"✅ Passed: {self.results['passed']}")
        self.log(f"❌ Failed: {self.results['failed']}")
        
        if self.results['errors']:
            self.log("\nERRORS ENCOUNTERED:")
            for error in self.results['errors']:
                self.log(f"  - {error}")
        
        return self.results['failed'] == 0

if __name__ == "__main__":
    tester = FocusedTester()
    success = tester.run_focused_tests()
    sys.exit(0 if success else 1)