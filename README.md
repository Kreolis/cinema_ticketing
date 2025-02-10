# Cinema Ticketing System

This is a **Django-based event ticketing system** that allows users to view events, select tickets, and make payments using several different payment gateways. 
The project tracks available seats for each event, handles ticket purchases, and integrates with `django-payments` for seamless payment processing.

### 🚀 Features

- **Event Management**: Create, update, and display events with customizable seat limits and price classes.
- **Ticketing**: Dynamically assign unique seat numbers to tickets and track their availability.
- **Payments**: Secure Stripe integration for handling payments via `django-payments`.
- **UUIDs for Tickets**: Non-obvious unique ticket identifiers for security.
- **Admin Dashboard**: Group tickets by event and manage them in the Django Admin panel.

### 🧰 Tech Stack

- **Backend**: Django 4.x
- **Frontend**: HTML, CSS (basic templates)
- **Payment Integration**: Stripe via `django-payments`
- **Database**: SQLite (default, configurable for other DBs)
- **Human Identification**: ReCAPTCHA via `django-reCAPTCHA`

---

## 🛠️ Installation
### 1. Set Up a Virtual Environment
```bash
python -m venv event_venv
source event_venv/bin/activate  # On Windows: event_venv\Scripts\activate
```

Use for example (direnv)[https://direnv.net/] for automatic environment activation.

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
```bash
cd code
```

Create a `.env` file in the project root and add the following environment variables:

```plaintext
DJANGO_SECRET_KEY = YourDjangoSecretKey

STRIPE_PUBLIC_KEY = YourStripePublicKey
STRIPE_SECRET_KEY = YourStripeSecretKey

RECAPTCHA_PUBLIC_KEY = 'YourMyRecaptchaKey'
RECAPTCHA_PRIVATE_KEY = 'YourRecaptchaPrivateKey'
```

> Replace `YourDjangoSecretKey` with a secret key for Django and `YourStripePublicKey` / `YourStripeSecretKey` with your Stripe API keys.
> For ReCAPTCHA support add `YourMyRecaptchaKey` / `YourRecaptchaPrivateKey`. 

### 5. Apply Migrations
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py create_groups
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


### 🏢 Deployment with Nginx

To deploy this project with Nginx, follow these steps:

#### 1. Set Up Gunicorn
Install Gunicorn:
```bash
pip install gunicorn
```

Run Gunicorn to serve the application:
```bash
gunicorn cinema_tickets.wsgi --bind 0.0.0.0:8880
```

Gunicorn (short for "Green Unicorn") is a Python WSGI HTTP server designed to serve Python web applications, such as those built with Django or Flask. It acts as a middle layer between the web application and the web server (e.g., Nginx).

#### 2. Install and Configure Nginx
Install Nginx:
```bash
sudo apt update
sudo apt install nginx
```

Edit the Nginx configuration file for your site:
```bash
sudo nano /etc/nginx/sites-available/cinema_ticketing
```
Add the following configuration:
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    location /static/ {
        root /path/to/your/project;
    }

    location / {
        proxy_pass http://127.0.0.1:8880;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```
Replace `/path/to/your/project` with the actual path to your Django project and `yourdomain.com` with your domain name.

#### 3. Obtain an SSL Certificate
Install Certbot for Nginx:
```bash
sudo apt install certbot python3-certbot-nginx
```

Obtain and configure the SSL certificate:
```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Certbot will automatically configure your Nginx to redirect HTTP traffic to HTTPS.

#### 4. Enable the Site and Restart Nginx
Link the configuration file and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/cinema_ticketing /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

#### 5. Test the Deployment
Visit your server's IP address or domain in your browser to ensure the application is running correctly.

---


## 🛠️ Troubleshooting

### Common Issues
- **Stripe Keys Not Working**: Ensure they are correctly set in the `.env` file.
- **Migrations Fail**: Delete the `db.sqlite3` file and the `migrations` folder in your app, then re-run:
  ```bash
  python manage.py makemigrations
  python manage.py migrate
  ```
- **Database Tables are missing**: Create migrations explicitly for the app:
  ```bash
  python manage.py makemigrations events
  python manage.py migrate events
  ```

---

## 💡 Contributing

We welcome contributions to this project! To contribute:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Submit a pull request with a detailed description.

### 📝 To-Do List

Version 2:

- [ ] Add user authentication for ticket buyers.
- [ ] Add support for refunds or cancellations.
- [ ] global event picture generation from name
- [ ] custom event picture per event
- [ ] language toggle with redirect to current page
- [ ] Order ticket count shown in menu
- [ ] Use shorter ids for urls and names
- [ ] location and price import


Version 1:

- [ ] make setting upload with csv
- [ ] fix issue of tickets that are not sold and not accociated with an order when session is closed (session checker)
- [ ] pay ticket in advance payment option

Nice to have:

- [ ] location based ticket manager
- [ ] admin stays logged in forever

### 👨‍💼 Main Contributors

- **Kreolis** - Lead Developer ([GitHub](https://github.com/kreolis))

### 🙇 Buy Me a Coffee
If you found this project helpful, consider supporting us:
[Buy Me a Coffee](https://www.buymeacoffee.com/kreolis)

---

## Contact
For any questions or issues, please email: `info@kreolis.net`.
🙇 Buy Me a Coffee


---

## ⚠️ License

This project is licensed under the [GNU General Public License v3.0](LICENSE). Feel free to use and modify it as needed.

**GNU GPLv3**

Permissions of this strong copyleft license are conditioned on making available complete source code of licensed works and modifications, which include larger works using a licensed work, under the same license. Copyright and license notices must be preserved. Contributors provide an express grant of patent rights. 
Closed code distributions are not allowed with this license.
