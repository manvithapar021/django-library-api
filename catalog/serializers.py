"""Serializers for the library API."""

from rest_framework import serializers

from .models import Book, Loan, Member


class BookSerializer(serializers.ModelSerializer):
    is_available = serializers.ReadOnlyField()

    class Meta:
        model = Book
        fields = [
            "id",
            "title",
            "author",
            "isbn",
            "total_copies",
            "available_copies",
            "is_available",
        ]


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ["id", "name", "email", "joined_date"]


class LoanSerializer(serializers.ModelSerializer):
    book_title = serializers.ReadOnlyField(source="book.title")
    member_name = serializers.ReadOnlyField(source="member.name")
    is_overdue = serializers.ReadOnlyField()
    overdue_days = serializers.ReadOnlyField()

    class Meta:
        model = Loan
        fields = [
            "id",
            "member",
            "member_name",
            "book",
            "book_title",
            "borrowed_date",
            "due_date",
            "returned_date",
            "fine",
            "is_overdue",
            "overdue_days",
        ]
        read_only_fields = ["borrowed_date", "due_date", "returned_date", "fine"]


class BorrowSerializer(serializers.Serializer):
    """Input for POST /api/loans/borrow/ — just the member and the book."""

    member = serializers.PrimaryKeyRelatedField(queryset=Member.objects.all())
    book = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all())
