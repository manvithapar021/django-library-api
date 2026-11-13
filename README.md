# Django Library API

A small library management REST API built with Django and Django REST
Framework. It covers the core of what a college or neighbourhood library
actually needs: a catalogue of books, members, borrowing with a 14-day
loan period, returns with overdue fines, and a summary of what is on loan.

## Why this project exists

Most "library API" tutorials stop at CRUD. The interesting part of a
library is the rules: a book cannot be borrowed when no copies are left,
returning a book restores the copy count, and a late return costs a fine.
This project puts those rules in the models so they hold no matter
whether a loan is created through the API, the Django admin or the shell.

## What it does

- **Books** — title, author, unique ISBN, total and available copies.
  List with filters: `?author=...`, `?available=true|false`, `?search=...`.
- **Members** — name, unique email, join date.
- **Borrow** — `POST /api/loans/borrow/` with a member and a book.
  Refused with a 400 when no copies are available. Borrowing sets the
  due date 14 days out and decrements the available copy count.
- **Return** — `POST /api/loans/{id}/return/`. Restores the copy and
  computes an overdue fine of **Rs 10 per day late** (recorded on the
  loan; nothing is charged). Returning twice is rejected.
- **Overdue loans** — `GET /api/loans/overdue/` or `GET /api/loans/?overdue=true`.
- **Stats** — `GET /api/stats/`: total books and copies, copies
  available, total members, books on loan, overdue loans, total fines.
- **Django admin** — all three models registered with search and filters.
- **Browsable API** — every endpoint works in the browser at `/api/`.

## Endpoints

| Method | URL | Auth | Description |
| ------ | --- | ---- | ----------- |
| GET | `/api/books/` | — | List books (filter: `author`, `available`, `search`) |
| POST | `/api/books/` | Token | Add a book |
| GET | `/api/books/{id}/` | — | One book |
| PUT / PATCH / DELETE | `/api/books/{id}/` | Token | Update / delete a book |
| GET | `/api/members/` | — | List members |
| POST | `/api/members/` | Token | Add a member |
| GET | `/api/members/{id}/` | — | One member |
| GET | `/api/loans/` | — | List loans (`?overdue=true`, `?member=id`) |
| POST | `/api/loans/borrow/` | Token | Borrow a book |
| POST | `/api/loans/{id}/return/` | Token | Return a book, fine computed |
| GET | `/api/loans/overdue/` | — | Unreturned loans past their due date |
| GET | `/api/stats/` | — | Library summary |
| POST | `/api/token/` | — | Get a token (username + password) |
| — | `/admin/` | Session | Django admin |

Reads are open. Every write (POST/PUT/PATCH/DELETE, borrow, return)
needs a token. Directly creating a loan with `POST /api/loans/` is
deliberately rejected — borrow is the only way to create one, so the
availability check can never be skipped.

## How auth works

Token authentication (DRF `authtoken`). Create a user, then request a
token:

```bash
python manage.py createsuperuser
curl -X POST http://127.0.0.1:8000/api/token/ \
  -d "username=admin&password=your-password"
# {"token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"}
```

Then send the token on write requests:

```bash
curl http://127.0.0.1:8000/api/books/ \
  -H "Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b" \
  -H "Content-Type: application/json" \
  -d '{"title": "Wings of Fire", "author": "A. P. J. Abdul Kalam",
       "isbn": "9788173711466", "total_copies": 2, "available_copies": 2}'
```

## How to run locally

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser # for the admin and for a token
python manage.py runserver
# API root: http://127.0.0.1:8000/api/
# Admin:    http://127.0.0.1:8000/admin/
```

## How to run the tests

```bash
python manage.py test
```

The suite (15 tests) uses DRF's `APIClient` and covers: creating books
and members, duplicate ISBN rejection, borrow success, borrow refused
when out of stock, borrowing the last copy, on-time return with no fine,
overdue return with the fine computed (6 days late = Rs 60), returning
twice, the overdue list, filtering by author and availability, the stats
endpoint, and unauthenticated writes being rejected.

## How to explain this in an interview

"I built a library API in Django with Django REST Framework. Books,
members and loans are the three models, and the borrowing rules live in
the models so they can't be skipped: borrow checks that a copy is
available and decrements the count, return restores it and computes a
Rs 10 per day overdue fine. Reads are open but writes need a token,
and creating a loan directly is blocked — borrow is the only path, so
the availability check always runs. There is a stats endpoint for books
on loan and overdue counts, and the admin is set up for all three
models. I tested the rules with DRF's test client, including the
out-of-stock refusal and the fine calculation."

## Honest limitations

- **SQLite, dev only.** The default database is fine for local use; a
  real deployment would need PostgreSQL and proper settings (the secret
  key in `settings.py` is the Django dev placeholder).
- **Token auth, not JWT.** DRF authtoken is simple and fits this app,
  but tokens never expire and there is no refresh flow.
- **Fines are computed, not charged.** The fine is a number on the loan;
  there is no payment integration and no reminder emails for overdue
  books.
- **No concurrency guard.** Two simultaneous borrows of the last copy
  could both pass the check; a production version would lock the row
  or use a database constraint.
- **Basic pagination.** List endpoints paginate at 20 items per page
  with no tuning or sorting options beyond the filters listed above.
