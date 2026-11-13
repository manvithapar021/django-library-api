"""Admin registration for the library catalogue."""

from django.contrib import admin

from .models import Book, Loan, Member


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "isbn", "total_copies", "available_copies")
    list_filter = ("author",)
    search_fields = ("title", "author", "isbn")


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "joined_date")
    search_fields = ("name", "email")


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = (
        "book",
        "member",
        "borrowed_date",
        "due_date",
        "returned_date",
        "fine",
    )
    list_filter = ("returned_date",)
    search_fields = ("book__title", "member__name")
