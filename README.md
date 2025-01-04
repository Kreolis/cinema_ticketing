# Cinema Ticketing System

This is a **Django-based event ticketing system** that allows users to view events, select tickets, and make payments using several different payment gateways. 
The project tracks available seats for each event, handles ticket purchases, and integrates with `django-payments` for seamless payment processing.

---

## 🚀 Features

- **Event Management**: Create, update, and display events with customizable seat limits and price classes.
- **Ticketing**: Dynamically assign unique seat numbers to tickets and track their availability.
- **Payments**: Secure Stripe integration for handling payments via `django-payments`.
- **UUIDs for Tickets**: Non-obvious unique ticket identifiers for security.
- **Admin Dashboard**: Group tickets by event and manage them in the Django Admin panel.

---

## 🛠️ Installation
### 1. Set Up a Virtual Environment
```bash
python -m venv event_venv
source event_venv/bin/activate  # On Windows: event_venv\Scripts\activate
```

### 2. Clone the Repository
```bash
cd event_venv
git clone https://github.com/Kreolis/cinema_ticketing
cd cinema_ticketing
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set Up the `.env` File
Create a `.env` file in the project root and add the following environment variables:

```plaintext
DJANGO_SECRET_KEY=your_django_secret_key

STRIPE_SECRET_KEY=sk_test_your_secret_key
STRIPE_PUBLIC_KEY=pk_test_your_publishable_key
```

> Replace `your_django_secret_key` with a secret key for Django and `your_secret_key` / `your_publishable_key` with your Stripe API keys.

### 5. Apply Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Run the Development Server
```bash
python manage.py runserver
```

---

## 📄 Usage

### Accessing the Site
- Open your browser and navigate to `http://127.0.0.1:8000/`.
- View the list of upcoming events on the homepage.
- Click an event to select tickets and proceed to payment.

### Admin Panel
- Navigate to `http://127.0.0.1:8000/admin/` to manage events, tickets, and payments.
- Create a superuser with:
  ```bash
  python manage.py createsuperuser
  ```

### Payment Flow
1. Select tickets for an event.
2. Enter payment details on the checkout page.
3. On successful payment, you will be redirected to a confirmation page.

---

## 🧰 Tech Stack

- **Backend**: Django 4.x
- **Frontend**: HTML, CSS (basic templates)
- **Payment Integration**: Stripe via `django-payments`
- **Database**: SQLite (default, configurable for other DBs)

---

## 📝 To-Do List

- [ ] Add user authentication for ticket buyers.
- [ ] QR code generation for tickets
- [ ] PDF generation of tickets and invoice
- [ ] Implement email notifications for ticket purchases.
- [ ] Implement QR code scanner for ticket checking
- [ ] Add support for refunds or cancellations.

---

## 💡 Contributing

We welcome contributions to this project! To contribute:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Submit a pull request with a detailed description.

---

## ⚠️ License

This project is licensed under the [GNU General Public License v3.0](LICENSE). Feel free to use and modify it as needed.

**GNU GPLv3**

Permissions of this strong copyleft license are conditioned on making available complete source code of licensed works and modifications, which include larger works using a licensed work, under the same license. Copyright and license notices must be preserved. Contributors provide an express grant of patent rights. 
Closed code distributions are not allowed with this license.

---

## 🛠️ Troubleshooting

### Common Issues
- **Stripe Keys Not Working**: Ensure they are correctly set in the `.env` file.
- **Migrations Fail**: Delete the `db.sqlite3` file and the `migrations` folder in your app, then re-run:
  ```bash
  python manage.py makemigrations
  python manage.py migrate
  ```

### Contact
For any questions or issues, please email: `info@kreolis.net`.
