# Cinema Ticketing System

This is a **Django-based event ticketing system** that allows users to view events, select tickets, and make payments using several different payment gateways. 
The project tracks available seats for each event, handles ticket purchases, and integrates with `django-payments` for seamless payment processing.

## 🚀 Features

- **Event Management**: Create, update, and display events with customizable seat limits and price classes.
- **Ticketing**: Dynamically assign unique seat numbers to tickets and track their availability.
- **Payments**: Secure Stripe integration for handling payments via `django-payments`.
- **UUIDs for Tickets**: Non-obvious unique ticket identifiers for security.
- **Admin Dashboard**: Group tickets by event and manage them in the Django Admin panel.

## 🧰 Tech Stack

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

Use for example [direnv](https://direnv.net/) for automatic environment activation.
Here is an example `.envrc` file for this project:

```bash
source bin/activate

set -a && . cinema_ticketing/code/cinema_tickets/.env && set +a

export FLOWER_BASIC_AUTH="${FLOWER_USERNAME}:${FLOWER_PASSWORD}"
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

Install rabbitmq:

```bash
sudo apt-get install rabbitmq-server
yay -S rabbitmq
```

After that start and enable the rabbitmq server:

```bash
sudo systemctl start rabbitmq
sudo systemctl enable rabbitmq
```

Dont forget to setup rabbitmq and create a user for it:

```bash
sudo rabbitmqctl add_user yourusername yourpassword
sudo rabbitmqctl add_vhost yourvhost
sudo rabbitmqctl set_user_tags yourusername yourtag
sudo rabbitmqctl set_permissions -p myvhost yourusername ".*" ".*" ".*"
```

Please also follow the instructions in the [Celery documentation](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/rabbitmq.html#broker-rabbitmq) to set up RabbitMQ with Django.

### 4. Set Up the `.env` File

```bash
cd code
```

Create a `.env` file in the `code/cinema_tickets` folder by copying the `template.env` and add at least replace `YourDjangoSecretKey` with a secret key for Django.

To be able to send emails add

```bash
  EMAIL_HOST=localhost
  EMAIL_PORT=587
  EMAIL_USE_TLS=True
  EMAIL_HOST_USER=your-email@example.com
  EMAIL_HOST_PASSWORD=your-email-password
  DEFAULT_FROM_EMAIL=your-email@example.com
```

If you want to use the Stripe payment gateway, add your Stripe keys:

```bash
  USE_STRIPE=True
  STRIPE_SECRET_KEY=your-stripe-secret-key
  STRIPE_PUBLIC_KEY=your-stripe-public-key
  STRIPE_WEBHOOK_SECRET=whsec_test_secret
```

For ReCAPTCHA support add `YourMyRecaptchaKey` / `YourRecaptchaPrivateKey`. 

If you want to use a postgres database set `USE_POSTGRES` to `True` and add the following variables:

```bash
  POSTGRES_DB=your-db-name
  POSTGRES_USER=your-db-user
  POSTGRES_PASSWORD=your-db-password
  POSTGRES_HOST=your-db-host
  POSTGRES_PORT=your-db-port
```

Depening on your setup you might also want to change the `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` variables to match your RabbitMQ configuration.

```bash
  CELERY_BROKER_URL='amqp://yourusername:yourpassword@localhost:5672/yourvhost'
  CELERY_RESULT_BACKEND='django-db'
```

Additionally, add flower credentials for monitoring celery tasks:

```bash
  FLOWER_USERNAME='your-flower-username'
  FLOWER_PASSWORD='your-flower-password'
```

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

For periodic tasks, run the Celery worker in a separate terminal:

```bash
celery -A cinema_tickets worker --loglevel=info
```

Make sure that RabbitMQ is running before starting the Celery worker.

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

#### Set Up uWSGI

Install [uWSGI](https://wiki.archlinux.org/title/UWSGI) and create a folder named `vassals` under `/etc/uwsgi`.
Create a file called `cinema_ticketing.ini` inside the `vassals` folder.

```ini
[uwsgi]
project = cinema_ticketing
uid = www-data # or nginx (the user that governs your websites)
base = /path/to/your/cinema_ticketing_folder

chdir = %(base)/%(project)
home = %(base)/event_venv
module = %(project).wsgi:application

master = true
processes = 5

socket = /run/uwsgi/%(project).sock
chown-socket = www-data:www-data # or nginx (the user that governs your websites)
chmod-socket = 660
vacuum = true

daemonize = /var/log/uwsgi/%(project).log
```

Enable and start the uWSGI emperor service to start serving the side.

```bash
systemctl enable emperor.uwsgi.service
systemctl start emperor.uwsgi.service
```

#### Manage Translation and Static

If you want to translate your application to a different language or want to modify the strings used in this website you have to generate a new translation locale with rosetta. Run this in your `cinema_ticketing` application folder.

```bash
django-admin makemessages -l <language_code>
```

Do not forget to compile your translations:

```bash
python manage.py compilemessages
```

Make sure to collect your static files like .css so that your website is properly styled. Run this in your `cinema_ticketing` application folder.

```bash
python manage.py collectstatic
```

#### Configure Nginx

Install Nginx and create a new configuration file for your project in `/etc/nginx/sites-available/` named `cinema_ticketing`.

```nginx
server {
    listen 80;
    server_name your_domain_or_IP;

    location = /favicon.ico { access_log off; log_not_found off; }
    location /static/ {
        root /path/to/your/cinema_ticketing_folder;
    }

    location / {
        include         uwsgi_params;
        uwsgi_pass      unix:/run/uwsgi/cinema_ticketing.sock;
    }

    error_log /var/log/nginx/cinema_ticketing_error.log;
    access_log /var/log/nginx/cinema_ticketing_access.log;
}
```

To add flower support add the following to your nginx configuration:

```nginx
    location /flower/ {
        proxy_pass http://127.0.0.1:5555/;
    }
```

Enable the configuration by creating a symbolic link to it in the `/etc/nginx/sites-enabled/` directory.

```bash
sudo ln -s /etc/nginx/sites-available/cinema_ticketing /etc/nginx/sites-enabled
```

Test the Nginx configuration and restart the service.

```bash
sudo nginx -t
sudo systemctl restart nginx
```

### Configure Celery and RabbitMQ

Make sure RabbitMQ is installed and running on your server. You can check its status with:

```bash
sudo systemctl status rabbitmq-server
```

Run Celery worker in the background to handle asynchronous tasks with periodic tasks enabled:

```bash
celery -A cinema_tickets worker --beat --loglevel=info --detach
```

To easy opartions and enable automatic restarts of the celery worker you can use the management command provided in this project. Run this in your `cinema_ticketing` application folder.

```bash
python manage.py celery
```

This will automatically run the server and the celery worker with the correct log level based on the `DEBUG` setting in your `.env` file. It will also kill any existing celery processes before starting new ones.

You can check the celery status with flower. Start flower in the background in a separate terminal:

```bash
celery -A cinema_tickets flower --port=5555
```

#### Test the Deployment

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

- **Branding object makemigrations OperationalError**: Make sure the branding object is_active is set to FALSE and try again

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
- [ ] make setting upload with csv
- [ ] Branding Logo
- [ ] Branding Page Name

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

### GNU GPLv3

Permissions of this strong copyleft license are conditioned on making available complete source code of licensed works and modifications, which include larger works using a licensed work, under the same license. Copyright and license notices must be preserved. Contributors provide an express grant of patent rights. 
Closed code distributions are not allowed with this license.
