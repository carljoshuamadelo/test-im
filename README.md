# RING RING!

A Lost & Found web application built with Werkzeug, Jinja2, and MySQL (XAMPP).

## Prerequisites

- **Python 3.8+**
- **XAMPP** (Apache + MySQL running)

## Setup Instructions

### 1. Clone the repository

```powershell
git clone <your-repo-url>
cd test-im
```

### 2. Create a virtual environment and install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate
pip install werkzeug jinja2 mysql-connector-python
```

### 3. Set up the database in XAMPP

1. Open **XAMPP Control Panel** and start **Apache** and **MySQL**.
2. Open **http://localhost/phpmyadmin** in your browser.
3. Click the **SQL** tab and run the following queries:

```sql
CREATE DATABASE lost_and_found_dbms;

USE lost_and_found_dbms;

CREATE TABLE admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE items (
    id VARCHAR(8) PRIMARY KEY,
    type ENUM('lost', 'found') NOT NULL,
    publish_status ENUM('pending', 'published', 'claimed', 'archived') DEFAULT 'pending',
    title VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    date VARCHAR(50) NOT NULL,
    location VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    contact VARCHAR(255) NOT NULL,
    image VARCHAR(255) DEFAULT NULL,
    reported_at DATE NOT NULL
);

CREATE TABLE claims (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_id VARCHAR(8) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    contact VARCHAR(255) NOT NULL,
    proof TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

INSERT INTO admins (username, password) VALUES ('admin', 'admin123');
```

### 4. Start the development server

```powershell
python app.py
```

### 5. Open the app

Go to **http://localhost:5000** in your browser.

## Admin Login

- **Username:** `admin`
- **Password:** `admin123`

Access the admin dashboard via the **Admin Login** button in the navigation bar.

username: admin
password: admin123