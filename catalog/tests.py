"""Tests for the Django Library API.

Covers: creating books/members, borrowing, out-of-stock refusal,
returning with an overdue fine, the overdue list, the stats endpoint,
and unauthenticated writes being rejected.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from catalog.models import Book, Loan, Member


class LibraryApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="librarian", password="testpass123")
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.anon = APIClient()

        self.book = Book.objects.create(
            title="Wings of Fire",
            author="A. P. J. Abdul Kalam",
            isbn="9788173711466",
            total_copies=2,
            available_copies=2,
        )
        self.member = Member.objects.create(name="Asha", email="asha@example.com")

    # -- create book / member -------------------------------------------------

    def test_create_book(self):
        response = self.client.post(
            "/api/books/",
            {
                "title": "The Guide",
                "author": "R. K. Narayan",
                "isbn": "9780143063062",
                "total_copies": 3,
                "available_copies": 3,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Book.objects.count(), 2)
        self.assertEqual(response.data["title"], "The Guide")

    def test_create_member(self):
        response = self.client.post(
            "/api/members/",
            {"name": "Ravi", "email": "ravi@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Member.objects.count(), 2)

    def test_duplicate_isbn_rejected(self):
        response = self.client.post(
            "/api/books/",
            {
                "title": "Copy",
                "author": "Someone",
                "isbn": "9788173711466",  # same ISBN as setUp book
                "total_copies": 1,
                "available_copies": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # -- borrow / return ------------------------------------------------------

    def test_borrow_success_decrements_available_copies(self):
        response = self.client.post(
            "/api/loans/borrow/",
            {"member": self.member.id, "book": self.book.id},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)
        loan = Loan.objects.get(id=response.data["id"])
        # Due date is 14 days after borrowing.
        self.assertEqual(
            loan.due_date.date(),
            (loan.borrowed_date + timedelta(days=14)).date(),
        )
        self.assertIsNone(loan.returned_date)

    def test_borrow_refused_when_out_of_stock(self):
        self.book.available_copies = 0
        self.book.save()
        response = self.client.post(
            "/api/loans/borrow/",
            {"member": self.member.id, "book": self.book.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Loan.objects.count(), 0)

    def test_borrow_second_copy_then_refused(self):
        # Two copies: two borrows succeed, the third is refused.
        for _ in range(2):
            response = self.client.post(
                "/api/loans/borrow/",
                {"member": self.member.id, "book": self.book.id},
                format="json",
            )
            self.assertEqual(response.status_code, 201)
        response = self.client.post(
            "/api/loans/borrow/",
            {"member": self.member.id, "book": self.book.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_return_on_time_no_fine(self):
        borrow = self.client.post(
            "/api/loans/borrow/",
            {"member": self.member.id, "book": self.book.id},
            format="json",
        )
        loan_id = borrow.data["id"]
        response = self.client.post(f"/api/loans/{loan_id}/return/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["fine"], 0)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)

    def test_return_overdue_fine_computed(self):
        borrow = self.client.post(
            "/api/loans/borrow/",
            {"member": self.member.id, "book": self.book.id},
            format="json",
        )
        loan = Loan.objects.get(id=borrow.data["id"])
        # Pretend the book was borrowed 20 days ago: due 6 days ago.
        loan.borrowed_date = timezone.now() - timedelta(days=20)
        loan.due_date = timezone.now() - timedelta(days=6)
        loan.save()
        response = self.client.post(f"/api/loans/{loan.id}/return/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        # 6 days overdue x Rs 10 = Rs 60.
        self.assertEqual(response.data["fine"], 60)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)

    def test_return_twice_rejected(self):
        borrow = self.client.post(
            "/api/loans/borrow/",
            {"member": self.member.id, "book": self.book.id},
            format="json",
        )
        loan_id = borrow.data["id"]
        self.assertEqual(
            self.client.post(f"/api/loans/{loan_id}/return/", {}, format="json").status_code,
            200,
        )
        response = self.client.post(f"/api/loans/{loan_id}/return/", {}, format="json")
        self.assertEqual(response.status_code, 400)

    # -- filtering / overdue / stats ------------------------------------------

    def test_overdue_list(self):
        borrow = self.client.post(
            "/api/loans/borrow/",
            {"member": self.member.id, "book": self.book.id},
            format="json",
        )
        loan = Loan.objects.get(id=borrow.data["id"])
        loan.due_date = timezone.now() - timedelta(days=3)
        loan.save()
        response = self.client.get("/api/loans/overdue/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], loan.id)

        response = self.client.get("/api/loans/?overdue=true")
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_books_by_author_and_availability(self):
        response = self.client.get("/api/books/?author=kalam")
        self.assertEqual(len(response.data["results"]), 1)
        response = self.client.get("/api/books/?available=false")
        self.assertEqual(len(response.data["results"]), 0)
        self.book.available_copies = 0
        self.book.save()
        response = self.client.get("/api/books/?available=false")
        self.assertEqual(len(response.data["results"]), 1)

    def test_stats_endpoint(self):
        self.client.post(
            "/api/loans/borrow/",
            {"member": self.member.id, "book": self.book.id},
            format="json",
        )
        response = self.client.get("/api/stats/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_books"], 1)
        self.assertEqual(response.data["total_members"], 1)
        self.assertEqual(response.data["books_on_loan"], 1)
        self.assertEqual(response.data["copies_available"], 1)
        self.assertEqual(response.data["overdue_loans"], 0)

    # -- auth ------------------------------------------------------------------

    def test_unauthenticated_write_rejected(self):
        response = self.anon.post(
            "/api/books/",
            {
                "title": "Nope",
                "author": "Nobody",
                "isbn": "9780000000001",
                "total_copies": 1,
                "available_copies": 1,
            },
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))

    def test_unauthenticated_read_allowed(self):
        response = self.anon.get("/api/books/")
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_borrow_rejected(self):
        response = self.anon.post(
            "/api/loans/borrow/",
            {"member": self.member.id, "book": self.book.id},
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))
