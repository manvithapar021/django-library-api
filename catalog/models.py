"""Models for the library catalogue: books, members and loans.

Borrowing rules live here so they are the same whether a loan is created
through the API, the admin or the shell:
- a book can only be borrowed while at least one copy is available;
- borrowing decrements ``available_copies``;
- returning restores the copy and computes an overdue fine of Rs 10 per
  day past the due date (the fine is recorded, never charged).
"""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

LOAN_PERIOD_DAYS = 14
FINE_PER_DAY = 10  # rupees per overdue day


class Book(models.Model):
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    isbn = models.CharField(max_length=17, unique=True, help_text="ISBN-10 or ISBN-13")
    total_copies = models.PositiveIntegerField(default=1)
    available_copies = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return f"{self.title} by {self.author}"

    def clean(self):
        if self.available_copies > self.total_copies:
            raise ValidationError("available_copies cannot exceed total_copies.")

    def is_available(self):
        return self.available_copies > 0


class Member(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    joined_date = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} <{self.email}>"


class Loan(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="loans")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="loans")
    borrowed_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField()
    returned_date = models.DateTimeField(null=True, blank=True)
    fine = models.PositiveIntegerField(default=0, help_text="Overdue fine in rupees, computed on return")

    class Meta:
        ordering = ["-borrowed_date"]

    def __str__(self):
        status = "returned" if self.returned_date else "on loan"
        return f"{self.book.title} -> {self.member.name} ({status})"

    def save(self, *args, **kwargs):
        if not self.due_date:
            # 14 days after the borrow moment; borrowed_date is set by
            # auto_now_add just before the first save, so fall back to now.
            base = self.borrowed_date or timezone.now()
            self.due_date = base + timedelta(days=LOAN_PERIOD_DAYS)
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        if self.returned_date:
            return False
        return timezone.now() > self.due_date

    @property
    def overdue_days(self):
        """Whole days past the due date (0 if not overdue)."""
        end = self.returned_date or timezone.now()
        days = (end - self.due_date).days
        return max(days, 0)

    def compute_fine(self):
        """Rs 10 per overdue day. A loan returned on time has no fine."""
        return self.overdue_days * FINE_PER_DAY

    def return_book(self):
        """Mark returned, compute the fine, and restore the book copy."""
        if self.returned_date:
            raise ValidationError("This loan has already been returned.")
        self.returned_date = timezone.now()
        self.fine = self.compute_fine()
        self.save()
        self.book.available_copies += 1
        self.book.save()
        return self.fine
