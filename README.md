# 🌍 TravelBookingApp

**TravelBookingApp** is a Django-based Course & Travel Management system.  
It supports multiple roles where travelers post trips, customers book space, and admins manage approvals, cancellations, refunds, and commissions.  
It also offers real-time chat, location tracking, order tracking, and automated CRUD generation for rapid development.

---

## ✨ Features

- **Multi-role System** — Traveler, Customer, Admin
- **Travel Plan Posting** — Travelers post trips with routes, dates, and available space
- **Booking System** — Customers can book traveler space
- **Payment Processing** — Secure booking payments
- **Location Tracking** — Real-time traveler location tracking
- **Order Tracking** — Track delivery and booking progress
- **Approval System** — Travelers or customers can approve/reject/cancel orders
- **Admin Oversight** — Admin approves cancellations, manages refunds, and tracks commissions
- **Commission Management** — Admin collects 10% from both parties per order
- **Real-Time Chat** — One-to-one messaging using WebSockets
- **CRUD Generator** — Auto-generates model, serializer, views, URLs, and admin

---

## 🏗 Architecture

| Service    | Description               | Port |
| ---------- | ------------------------- | ---- |
| Django     | Main backend API          | 8000 |
| PostgreSQL | Database                  | 5432 |
| Redis      | Cache & Message Broker    | 6379 |
| Celery     | Background Tasks          | —    |
| WebSockets | Real-time chat & tracking | —    |

---

## 🚀 Quick Start

### Option 1 — Docker (Recommended)

```bash
git clone https://github.com/yourusername/travelbookingapp.git
cd travelbookingapp

cp .env.example .env

docker-compose up --build

docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```


Access:
Backend API: http://localhost:8000
Admin Panel: http://localhost:8000/admin

Option 2 — Local Development

```
    python -m venv venv
    source venv/bin/activate    # Mac/Linux
    venv\Scripts\activate      # Windows
    
    pip install -r requirements.txt
    
    python manage.py migrate
    python manage.py runserver

```

⚡ CRUD Generator

Generate complete CRUD applications instantly:
````
    python manage.py create_crud_app <app_name> --model <ModelName>
````
Auto-generates: Model, Serializer, ViewSet, URLs, Admin, Tests


🛠 Common Commands

```
# Docker commands
docker-compose logs -f
docker-compose down
docker-compose exec web python manage.py shell

# Django commands
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# Database
docker-compose exec db pg_dump -U myuser mydb > backup.sql

```

💡 Author

Made with ❤️ by Md Merazul Islam

⭐ Star this repo if it helped you!


If you want, I can now also make a **nice diagram of the workflow** showing:  
Traveler → Booking → Approval → Delivery → Commission → Chat.  

That will make this README **way more professional** and easier for others to understand.  

Do you want me to do that?
