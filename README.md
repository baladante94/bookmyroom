# Book My Room

A full-featured hotel room booking and management app built on **Frappe v16 / ERPNext v16**.

---

## Features

### Hotel & Room Setup
- **Hotel** master with star rating, contact info, check-in/check-out times, tax rate, cancellation policy, and description.
- **Room Type** master with bed type, max occupancy, description, and a linked Billing Item for invoicing.
- **Room** master with floor, capacity, bed type, view type, smoking preference, housekeeping status, and a many-to-many amenities table.
- **Hotel Amenity** master for categorised amenities (In-Room, Property, Services, Dining).
- **Meal Plan** master with included meals (breakfast/lunch/dinner) and extra rate per person.

### Pricing
- **Rate Plan** – seasonal and special pricing per hotel / room type with a validity window. The reservation form auto-fetches the applicable rate on check-in date.

### Room Reservation (front-desk workflow)
- Reservation header captures hotel, customer, company, check-in / check-out, adults, children, meal plan, booking source, special requests, advance amount, and discount.
- **Room Reservation Item** child table: room, room type, rate, and amount per room.
- Automatic calculation of:
  - Total nights (from date diff)
  - Room charges per row
  - Meal plan charges (rate × persons × nights)
  - Discount amount
  - Tax amount (fetched from Hotel tax rate)
  - Grand total and balance due
- **Overlap validation** – blocks booking the same room twice for overlapping dates using `frappe.qb`.
- **Capacity warning** – non-blocking alert when guest count exceeds room capacity.
- Status workflow: `Draft → Booked → Checked In → Checked Out` (and `No Show` / `Cancelled`).
- Action buttons on the submitted form:
  - **Check In** – marks rooms Occupied.
  - **Check Out** – marks rooms Dirty, creates Housekeeping Log tasks.
  - **No Show** – frees rooms, records cancellation date.
  - **Post Service Charge** – opens a dialog to add in-stay charges to a Guest Folio (visible when Checked In).
  - **Room Invoice** – generates a draft Sales Invoice for room charges only.
  - **Room + Folio Invoice** – generates a combined draft Sales Invoice with room charges + all open folio charges (button shows the folio count and total; only visible when Open folios exist).

### Guest Folio (in-stay charges)
- Tracks individual service charges posted during a guest's stay (room service, minibar, spa, laundry, etc.).
- Linked to a Room Reservation, hotel, room, customer, and company.
- **Guest Folio Item** child table: service, description, quantity, rate, amount.
- Status: `Open` → `Settled` (driven by Sales Invoice lifecycle, not manual submission).
- Direct invoicing: **Create Sales Invoice** button on the folio form.
- Folio status is set to **Settled** automatically when the linked Sales Invoice is **submitted**.
- Folio status reverts to **Open** automatically when the Sales Invoice is **cancelled**.

### Housekeeping
- **Housekeeping Log** tracks cleaning tasks per room (Daily Service, Check-Out Clean, Deep Clean, Inspection).
- Status: `Pending → In Progress → Completed → Skipped`.
- Updating the log status automatically syncs `Room.housekeeping_status` (Completed → Clean).

### Billing & Invoicing
- Custom fields added to **Sales Invoice** (header) and **Sales Invoice Item** (row) via `after_install` / `after_migrate` hooks:
  - **Sales Invoice** → `bmr_reservation` (Room Reservation link), `bmr_guest_folio` (Guest Folio link)
  - **Sales Invoice Item** → `bmr_guest_folio` (row-level folio reference), `bmr_reservation` (row-level reservation reference)
- Row-level folio tracking: every item row that originates from a folio carries the folio's name, enabling the system to settle exactly the right folios on invoice submission.
- **Duplicate invoice prevention**: attempting to create a second invoice when a submitted invoice already exists for the reservation raises a clear error.
- Combined invoice flow: room charges + all Open folio charges in one invoice; folios settle on invoice submit and reopen on cancel.

### Scheduled Tasks (daily)
- `send_checkin_reminders` – emails upcoming check-in customers the day before arrival.
- `auto_generate_housekeeping_tasks` – creates Daily Service housekeeping logs for all currently Occupied rooms.

### Workspace Sidebar
- Custom **Book My Room** workspace sidebar with organised sections:
  - **Front Desk**: Room Reservation, Guest Folio, Housekeeping Log
  - **Masters**: Hotel, Room, Room Type, Meal Plan, Hotel Amenity, Hotel Service
  - **Pricing**: Rate Plan

---

## Module & DocType Overview

| DocType | Type | Description |
|---|---|---|
| Hotel | Master | Hotel property configuration |
| Room Type | Master | Room category (Standard, Deluxe, Suite…) |
| Room | Master | Individual bookable room |
| Hotel Amenity | Master | Amenity catalogue |
| Room Amenity | Child Table | Links amenities to rooms |
| Meal Plan | Master | Meal package with per-person rate |
| Hotel Service | Master | Billable in-stay service |
| Rate Plan | Master | Time-bound pricing overrides |
| Room Reservation | Transaction | Main booking document |
| Room Reservation Item | Child Table | Rooms within a reservation |
| Guest Folio | Transaction (Submittable) | In-stay charge tracker |
| Guest Folio Item | Child Table | Individual service charges |
| Housekeeping Log | Transaction | Room cleaning task |

---

## Installation

Requires a working **Frappe v16 / ERPNext v16** bench.

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench --site <your-site> install-app bookmyroom
bench --site <your-site> migrate
```

The `after_install` / `after_migrate` hooks automatically apply all custom fields to Sales Invoice.

---

## Contributing

This app uses `pre-commit` for code formatting and linting. Install and enable it:

```bash
cd apps/bookmyroom
pre-commit install
```

Configured tools: **ruff**, **eslint**, **prettier**, **pyupgrade**.

---

## License

MIT
