"""API views: viewsets for books/members/loans plus borrow/return/stats.

Reads are open; every write needs a token (see README for how to get
one). Borrow and return are explicit actions on the Loan viewset so the
copy-count and fine rules in the models are always applied.
"""

from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Book, Loan, Member
from .serializers import (
    BookSerializer,
    BorrowSerializer,
    LoanSerializer,
    MemberSerializer,
)


class BookViewSet(viewsets.ModelViewSet):
    """Books. Filter with ?author=..., ?available=true, or ?search=..."""

    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        author = self.request.query_params.get("author")
        if author:
            qs = qs.filter(author__icontains=author)
        available = self.request.query_params.get("available")
        if available == "true":
            qs = qs.filter(available_copies__gt=0)
        elif available == "false":
            qs = qs.filter(available_copies=0)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(author__icontains=search))
        return qs


class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class LoanViewSet(viewsets.ModelViewSet):
    """Loans. ?overdue=true lists unreturned loans past their due date."""

    queryset = Loan.objects.select_related("member", "book").all()
    serializer_class = LoanSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        overdue = self.request.query_params.get("overdue")
        if overdue == "true":
            qs = qs.filter(returned_date__isnull=True, due_date__lt=timezone.now())
        elif overdue == "false":
            qs = qs.filter(Q(returned_date__isnull=False) | Q(due_date__gte=timezone.now()))
        member = self.request.query_params.get("member")
        if member:
            qs = qs.filter(member_id=member)
        return qs

    def create(self, request, *args, **kwargs):
        """Creating a loan directly is not allowed — use borrow instead,
        so the availability check and copy count are never skipped."""
        return Response(
            {"detail": "Use POST /api/loans/borrow/ to borrow a book."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=False, methods=["post"], url_path="borrow")
    def borrow(self, request):
        serializer = BorrowSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = serializer.validated_data["member"]
        book = serializer.validated_data["book"]
        if not book.is_available():
            return Response(
                {"detail": f"No copies of '{book.title}' are available right now."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        book.available_copies -= 1
        book.save()
        loan = Loan.objects.create(member=member, book=book)
        return Response(LoanSerializer(loan).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="return")
    def return_loan(self, request, pk=None):
        loan = self.get_object()
        if loan.returned_date:
            return Response(
                {"detail": "This loan has already been returned."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        fine = loan.return_book()
        data = LoanSerializer(loan).data
        data["fine_charged"] = fine
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="overdue")
    def overdue(self, request):
        loans = self.get_queryset().filter(
            returned_date__isnull=True, due_date__lt=timezone.now()
        )
        return Response(LoanSerializer(loans, many=True).data)


class StatsViewSet(viewsets.ViewSet):
    """GET /api/stats/ — one-line summary of the library."""

    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def list(self, request):
        now = timezone.now()
        return Response(
            {
                "total_books": Book.objects.count(),
                "total_copies": sum(b.total_copies for b in Book.objects.all()),
                "copies_available": sum(b.available_copies for b in Book.objects.all()),
                "total_members": Member.objects.count(),
                "books_on_loan": Loan.objects.filter(returned_date__isnull=True).count(),
                "overdue_loans": Loan.objects.filter(
                    returned_date__isnull=True, due_date__lt=now
                ).count(),
                "total_fines_collected": sum(l.fine for l in Loan.objects.all()),
            }
        )
