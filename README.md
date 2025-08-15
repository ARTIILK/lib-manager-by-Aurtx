Aurtx BiblioFlow
Aurtx BiblioFlow is a cross-platform Python GUI application built with Tkinter for managing a school library's book lending system. It provides an intuitive interface for borrowing and returning books, managing book inventory, and tracking student records. The application is designed to run seamlessly on both Windows and Linux without modification.
Features

Borrow Book: Search students and books with real-time suggestions using admission numbers or book codes (SBIN or Stamp). Supports student registration and automatic warning system for overdue books (>7 days).
Return Book: Search and return books by code, updating availability and tracking late returns with automated warning updates.
Manage Books: Add, edit, or delete books with validation for duplicate SBIN or Stamp codes.
Manage Students: Add, edit, or delete student records, including warning counts for overdue returns.
Database: Uses SQLite with separate databases (students.db and library.db) for robust data management.
Theming: Consistent UI with a light teal background (#EDF7F6), dark blue-grey elements (#2E4756), and hover effects (#3A5A6B) using Segoe UI font.
Security: Employs parameterized SQL queries to prevent SQL injection.
Portability: Uses relative paths for cross-platform compatibility and graceful error handling for invalid inputs.

Tech Stack

Language: Python 3.x
GUI Framework: Tkinter (standard library)
Database: SQLite (standard library)
Dependencies: None (uses Python standard library)

Project Structure
textAurtx_BiblioFlow/
├── main.py               # Application entry point and UI setup
├── db_utils.py           # Database initialization and utility functions
├── borrow_page.py        # Borrow Book page logic
├── return_page.py        # Return Book page logic
├── manage_books.py       # Manage Books page logic
├── manage_students.py    # Manage Students page logic
├── students.db           # SQLite database for students (created at runtime)
└── library.db            # SQLite database for books and borrow records (created at runtime)
Getting Started
Prerequisites

Python 3.x installed (no external dependencies required).

Installation

Clone the repository:
bashgit clone https://github.com/ARTIILK/lib-manager-by-Aurtx.git

Navigate to the project directory:
bashcd Aurtx_BiblioFlow

Run the application:
bashpython main.py


The application will create students.db and library.db automatically in the project directory upon first run.
Usage

Navigate between tabs to borrow/return books or manage books/students.
Enter valid admission numbers (6 characters) and book codes for operations.
Use the refresh button to update book and student lists.
Errors (e.g., duplicate codes, invalid inputs) are handled with user-friendly messages.

Contributing
Contributions are welcome! Please fork the repository, create a feature branch, and submit a pull request. Ensure code follows PEP 8 guidelines and includes appropriate error handling.
