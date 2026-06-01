"""Seed data for the default datasources.

Populates aurora-sqlite with transactional e-commerce data and
aurora-duckdb with analytical web-events data, so users have
realistic datasets to query immediately after startup.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aurora_serve.datasource.service import DatasourceService

logger = logging.getLogger(__name__)

# ── SQLite E-commerce Dataset ──────────────────────────────────────
_SQLITE_SEED_SQL = """\
-- ── Schema ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS departments (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    location    TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS employees (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT UNIQUE,
    department_id INTEGER REFERENCES departments(id),
    title         TEXT,
    salary        REAL,
    hire_date     TEXT
);

CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    price       REAL,
    stock       INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS customers (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT UNIQUE,
    city       TEXT,
    country    TEXT DEFAULT 'US',
    joined_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    status      TEXT DEFAULT 'pending',
    total       REAL DEFAULT 0,
    ordered_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS order_items (
    id         INTEGER PRIMARY KEY,
    order_id   INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity   INTEGER DEFAULT 1,
    unit_price REAL
);

-- ── Departments ─────────────────────────────────────────────────

INSERT INTO departments (id, name, location) VALUES
    (1, 'Engineering',  'San Francisco'),
    (2, 'Marketing',    'New York'),
    (3, 'Sales',        'Chicago'),
    (4, 'Design',       'San Francisco'),
    (5, 'Operations',   'Austin');

-- ── Employees ───────────────────────────────────────────────────

INSERT INTO employees (id, name, email, department_id, title, salary, hire_date) VALUES
    (1,  'Alice Chen',      'alice@aurora.io',    1, 'Staff Engineer',     185000, '2021-03-15'),
    (2,  'Bob Martinez',    'bob@aurora.io',      1, 'Senior Engineer',    155000, '2022-01-10'),
    (3,  'Carol Wang',      'carol@aurora.io',    1, 'Engineer',           125000, '2023-06-01'),
    (4,  'David Kim',       'david@aurora.io',    2, 'Marketing Lead',     135000, '2021-08-20'),
    (5,  'Eva Johnson',     'eva@aurora.io',      2, 'Content Strategist',  95000, '2023-02-14'),
    (6,  'Frank Liu',       'frank@aurora.io',    3, 'Sales Director',     165000, '2020-11-05'),
    (7,  'Grace Park',      'grace@aurora.io',    3, 'Account Executive',  105000, '2022-09-12'),
    (8,  'Henry Zhang',     'henry@aurora.io',    3, 'Account Executive',  100000, '2023-04-18'),
    (9,  'Iris Nakamura',   'iris@aurora.io',     4, 'Design Lead',        140000, '2021-05-22'),
    (10, 'Jack O''Brien',   'jack@aurora.io',     4, 'Product Designer',   115000, '2022-07-30'),
    (11, 'Karen Singh',     'karen@aurora.io',    5, 'Ops Manager',        130000, '2021-01-08'),
    (12, 'Leo Rossi',       'leo@aurora.io',      5, 'DevOps Engineer',    145000, '2022-03-25'),
    (13, 'Mia Thompson',    'mia@aurora.io',      1, 'Junior Engineer',     95000, '2024-01-15'),
    (14, 'Noah Davis',      'noah@aurora.io',     2, 'Growth Analyst',     110000, '2023-10-01'),
    (15, 'Olivia Brown',    'olivia@aurora.io',   4, 'UX Researcher',      120000, '2023-08-12');

-- ── Categories ──────────────────────────────────────────────────

INSERT INTO categories (id, name, slug) VALUES
    (1, 'Electronics',  'electronics'),
    (2, 'Home & Garden','home-garden'),
    (3, 'Books',        'books'),
    (4, 'Apparel',      'apparel');

-- ── Products ────────────────────────────────────────────────────

INSERT INTO products (id, name, category_id, price, stock) VALUES
    (1,  'Wireless Keyboard',     1,  79.99,  120),
    (2,  'USB-C Hub',             1,  49.99,  200),
    (3,  'Noise-Cancelling Headphones', 1, 249.99, 45),
    (4,  'Mechanical Pencil',     3,   8.99,  500),
    (5,  'Standing Desk Mat',     2,  39.99,   80),
    (6,  'LED Desk Lamp',         2,  59.99,  150),
    (7,  'TypeScript Handbook',   3,  34.99,  300),
    (8,  'Design Systems Book',   3,  44.99,  180),
    (9,  'Merino Wool Sweater',   4, 129.99,   60),
    (10, 'Canvas Tote Bag',       4,  24.99,  400),
    (11, '4K Monitor',            1, 449.99,   30),
    (12, 'Ergonomic Chair',       2, 599.99,   25);

-- ── Customers ───────────────────────────────────────────────────

INSERT INTO customers (id, name, email, city, country) VALUES
    (1, 'Sarah Connor',     'sarah@example.com',    'Los Angeles',  'US'),
    (2, 'James Wilson',     'james@example.com',    'London',       'UK'),
    (3, 'Yuki Tanaka',      'yuki@example.com',     'Tokyo',        'JP'),
    (4, 'Maria Garcia',     'maria@example.com',    'Barcelona',    'ES'),
    (5, 'Ahmed Hassan',     'ahmed@example.com',    'Dubai',        'AE'),
    (6, 'Priya Sharma',     'priya@example.com',    'Mumbai',       'IN'),
    (7, 'Tom Anderson',     'tom@example.com',      'Sydney',       'AU'),
    (8, 'Lin Wei',          'lin@example.com',      'Shanghai',     'CN');

-- ── Orders ──────────────────────────────────────────────────────

INSERT INTO orders (id, customer_id, status, total, ordered_at) VALUES
    (1,  1, 'completed',   129.98, '2024-11-01 09:15:00'),
    (2,  1, 'completed',   249.99, '2024-11-15 14:30:00'),
    (3,  2, 'completed',    84.98, '2024-11-03 11:00:00'),
    (4,  2, 'shipped',     449.99, '2024-12-01 08:45:00'),
    (5,  3, 'completed',   164.97, '2024-11-10 16:20:00'),
    (6,  3, 'pending',      59.99, '2024-12-10 10:00:00'),
    (7,  4, 'completed',   129.99, '2024-11-20 13:15:00'),
    (8,  4, 'shipped',      49.99, '2024-12-05 09:30:00'),
    (9,  5, 'completed',   599.99, '2024-11-25 17:00:00'),
    (10, 5, 'pending',     114.98, '2024-12-12 12:00:00'),
    (11, 6, 'completed',    79.98, '2024-11-08 10:30:00'),
    (12, 6, 'completed',   209.98, '2024-12-02 15:45:00'),
    (13, 7, 'shipped',     449.99, '2024-12-08 08:00:00'),
    (14, 7, 'completed',    34.99, '2024-11-18 11:30:00'),
    (15, 8, 'completed',   164.97, '2024-11-22 14:00:00'),
    (16, 8, 'pending',     599.99, '2024-12-15 09:00:00'),
    (17, 1, 'shipped',      79.99, '2024-12-18 16:30:00'),
    (18, 3, 'completed',    44.99, '2024-12-20 10:15:00'),
    (19, 5, 'pending',     129.99, '2025-01-02 08:00:00'),
    (20, 6, 'completed',    24.99, '2024-12-22 13:45:00');

-- ── Order Items ─────────────────────────────────────────────────

INSERT INTO order_items (id, order_id, product_id, quantity, unit_price) VALUES
    (1,   1,  1,  1,  79.99),
    (2,   1,  2,  1,  49.99),
    (3,   2,  3,  1, 249.99),
    (4,   3,  2,  1,  49.99),
    (5,   3,  7,  1,  34.99),
    (6,   4, 11,  1, 449.99),
    (7,   5,  5,  1,  39.99),
    (8,   5,  1,  1,  79.99),
    (9,   5,  6,  1,  59.99),
    (10,  6,  6,  1,  59.99),
    (11,  7,  9,  1, 129.99),
    (12,  8,  2,  1,  49.99),
    (13,  9, 12,  1, 599.99),
    (14, 10,  4,  3,   8.99),
    (15, 10,  1,  1,  79.99),
    (16, 11,  1,  1,  79.99),
    (17, 12,  3,  1, 249.99),
    (18, 12, 10,  2,  24.99),
    (19, 13, 11,  1, 449.99),
    (20, 14,  7,  1,  34.99),
    (21, 15,  5,  1,  39.99),
    (22, 15,  1,  1,  79.99),
    (23, 15,  8,  1,  44.99),
    (24, 16, 12,  1, 599.99),
    (25, 17,  1,  1,  79.99),
    (26, 18,  8,  1,  44.99),
    (27, 19,  9,  1, 129.99),
    (28, 20, 10,  1,  24.99);
"""

# ── DuckDB Web Analytics Dataset ───────────────────────────────────
_DUCKDB_SEED_SQL = """\
-- ── Schema ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    email       VARCHAR UNIQUE,
    country     VARCHAR,
    plan        VARCHAR,
    signup_date DATE
);

CREATE TABLE IF NOT EXISTS sessions (
    id          VARCHAR PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id),
    started_at  TIMESTAMP,
    ended_at    TIMESTAMP,
    duration_s  INTEGER,
    device      VARCHAR,
    browser     VARCHAR
);

CREATE TABLE IF NOT EXISTS events (
    id           BIGINT PRIMARY KEY,
    session_id   VARCHAR REFERENCES sessions(id),
    user_id      INTEGER REFERENCES users(id),
    event_name   VARCHAR,
    page_url     VARCHAR,
    occurred_at  TIMESTAMP,
    properties   VARCHAR
);

CREATE TABLE IF NOT EXISTS page_views (
    id           BIGINT PRIMARY KEY,
    session_id   VARCHAR REFERENCES sessions(id),
    user_id      INTEGER REFERENCES users(id),
    url          VARCHAR,
    title        VARCHAR,
    referrer     VARCHAR,
    duration_s   INTEGER,
    viewed_at    TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversions (
    id           BIGINT PRIMARY KEY,
    user_id      INTEGER REFERENCES users(id),
    funnel_stage VARCHAR,
    completed_at TIMESTAMP,
    revenue      DOUBLE
);

-- ── Users (30 analytics users) ─────────────────────────────────

INSERT INTO users (id, email, country, plan, signup_date) VALUES
    (1,  'alice@gmail.com',    'US', 'free',     '2024-01-05'),
    (2,  'bob@yahoo.com',      'UK', 'pro',      '2024-01-12'),
    (3,  'carol@outlook.com',  'US', 'free',     '2024-02-03'),
    (4,  'dave@gmail.com',     'DE', 'enterprise','2024-02-18'),
    (5,  'eve@proton.me',      'FR', 'pro',      '2024-03-01'),
    (6,  'frank@gmail.com',    'US', 'free',     '2024-03-15'),
    (7,  'grace@yahoo.com',    'JP', 'pro',      '2024-03-22'),
    (8,  'henry@gmail.com',    'US', 'free',     '2024-04-02'),
    (9,  'iris@outlook.com',   'UK', 'enterprise','2024-04-18'),
    (10, 'jack@gmail.com',     'CA', 'pro',      '2024-05-01'),
    (11, 'kate@yahoo.com',     'US', 'free',     '2024-05-10'),
    (12, 'leo@gmail.com',      'AU', 'pro',      '2024-05-25'),
    (13, 'mia@proton.me',      'US', 'free',     '2024-06-05'),
    (14, 'noah@gmail.com',     'DE', 'enterprise','2024-06-20'),
    (15, 'olivia@yahoo.com',   'UK', 'pro',      '2024-07-01'),
    (16, 'paul@gmail.com',     'US', 'free',     '2024-07-15'),
    (17, 'quinn@outlook.com',  'FR', 'pro',      '2024-08-01'),
    (18, 'rachel@gmail.com',   'US', 'free',     '2024-08-12'),
    (19, 'sam@yahoo.com',      'JP', 'enterprise','2024-08-25'),
    (20, 'tina@gmail.com',     'CA', 'pro',      '2024-09-05'),
    (21, 'uma@proton.me',      'US', 'free',     '2024-09-18'),
    (22, 'victor@gmail.com',   'UK', 'pro',      '2024-10-01'),
    (23, 'wendy@yahoo.com',    'US', 'free',     '2024-10-15'),
    (24, 'xander@gmail.com',   'DE', 'enterprise','2024-10-28'),
    (25, 'yara@outlook.com',   'FR', 'pro',      '2024-11-05'),
    (26, 'zach@gmail.com',     'US', 'free',     '2024-11-18'),
    (27, 'amy@yahoo.com',      'AU', 'pro',      '2024-12-01'),
    (28, 'ben@gmail.com',      'US', 'free',     '2024-12-10'),
    (29, 'cathy@proton.me',    'UK', 'enterprise','2024-12-20'),
    (30, 'derek@gmail.com',    'US', 'pro',      '2025-01-02');

-- ── Sessions (60 sessions) ─────────────────────────────────────

INSERT INTO sessions (id, user_id, started_at, ended_at, duration_s, device, browser) VALUES
    ('s001', 1,  '2025-01-05 09:15:00', '2025-01-05 09:45:00', 1800, 'desktop', 'Chrome'),
    ('s002', 1,  '2025-01-06 14:20:00', '2025-01-06 14:50:00', 1800, 'mobile',  'Safari'),
    ('s003', 2,  '2025-01-05 10:00:00', '2025-01-05 11:30:00', 5400, 'desktop', 'Firefox'),
    ('s004', 3,  '2025-01-06 08:30:00', '2025-01-06 08:45:00',  900, 'mobile',  'Chrome'),
    ('s005', 4,  '2025-01-05 16:00:00', '2025-01-05 17:00:00', 3600, 'desktop', 'Chrome'),
    ('s006', 5,  '2025-01-07 11:00:00', '2025-01-07 11:20:00', 1200, 'tablet',  'Safari'),
    ('s007', 6,  '2025-01-08 09:00:00', '2025-01-08 09:10:00',  600, 'desktop', 'Chrome'),
    ('s008', 7,  '2025-01-08 13:00:00', '2025-01-08 14:30:00', 5400, 'desktop', 'Firefox'),
    ('s009', 8,  '2025-01-09 10:15:00', '2025-01-09 10:30:00',  900, 'mobile',  'Chrome'),
    ('s010', 9,  '2025-01-10 15:00:00', '2025-01-10 16:00:00', 3600, 'desktop', 'Chrome'),
    ('s011', 10, '2025-01-11 09:30:00', '2025-01-11 10:00:00', 1800, 'desktop', 'Safari'),
    ('s012', 11, '2025-01-12 14:00:00', '2025-01-12 14:20:00', 1200, 'mobile',  'Chrome'),
    ('s013', 12, '2025-01-13 08:00:00', '2025-01-13 09:30:00', 5400, 'desktop', 'Firefox'),
    ('s014', 13, '2025-01-14 11:00:00', '2025-01-14 11:15:00',  900, 'mobile',  'Safari'),
    ('s015', 14, '2025-01-15 16:30:00', '2025-01-15 17:30:00', 3600, 'desktop', 'Chrome'),
    ('s016', 15, '2025-01-16 10:00:00', '2025-01-16 10:45:00', 2700, 'tablet',  'Chrome'),
    ('s017', 16, '2025-01-17 09:00:00', '2025-01-17 09:20:00', 1200, 'desktop', 'Firefox'),
    ('s018', 17, '2025-01-18 13:30:00', '2025-01-18 14:00:00', 1800, 'desktop', 'Chrome'),
    ('s019', 18, '2025-01-19 08:45:00', '2025-01-19 09:00:00',  900, 'mobile',  'Chrome'),
    ('s020', 19, '2025-01-20 15:00:00', '2025-01-20 16:30:00', 5400, 'desktop', 'Safari'),
    ('s021', 20, '2025-01-21 10:30:00', '2025-01-21 11:00:00', 1800, 'desktop', 'Chrome'),
    ('s022', 21, '2025-01-22 14:15:00', '2025-01-22 14:30:00',  900, 'mobile',  'Safari'),
    ('s023', 22, '2025-01-23 09:00:00', '2025-01-23 10:30:00', 5400, 'desktop', 'Firefox'),
    ('s024', 23, '2025-01-24 11:30:00', '2025-01-24 12:00:00', 1800, 'desktop', 'Chrome'),
    ('s025', 24, '2025-01-25 16:00:00', '2025-01-25 17:00:00', 3600, 'desktop', 'Chrome'),
    ('s026', 25, '2025-01-26 08:00:00', '2025-01-26 08:30:00', 1800, 'tablet',  'Safari'),
    ('s027', 26, '2025-01-27 13:00:00', '2025-01-27 13:15:00',  900, 'mobile',  'Chrome'),
    ('s028', 27, '2025-01-28 10:00:00', '2025-01-28 11:30:00', 5400, 'desktop', 'Firefox'),
    ('s029', 28, '2025-01-29 09:30:00', '2025-01-29 09:45:00',  900, 'desktop', 'Chrome'),
    ('s030', 29, '2025-01-30 15:30:00', '2025-01-30 16:30:00', 3600, 'desktop', 'Chrome'),
    ('s031', 1,  '2025-02-01 09:00:00', '2025-02-01 09:30:00', 1800, 'desktop', 'Chrome'),
    ('s032', 2,  '2025-02-02 14:00:00', '2025-02-02 15:00:00', 3600, 'desktop', 'Firefox'),
    ('s033', 3,  '2025-02-03 10:15:00', '2025-02-03 10:30:00',  900, 'mobile',  'Chrome'),
    ('s034', 5,  '2025-02-04 11:00:00', '2025-02-04 12:00:00', 3600, 'desktop', 'Safari'),
    ('s035', 7,  '2025-02-05 08:30:00', '2025-02-05 09:30:00', 3600, 'desktop', 'Chrome'),
    ('s036', 9,  '2025-02-06 16:00:00', '2025-02-06 16:45:00', 2700, 'desktop', 'Firefox'),
    ('s037', 10, '2025-02-07 09:00:00', '2025-02-07 09:20:00', 1200, 'mobile',  'Safari'),
    ('s038', 12, '2025-02-08 13:00:00', '2025-02-08 14:30:00', 5400, 'desktop', 'Chrome'),
    ('s039', 14, '2025-02-09 10:00:00', '2025-02-09 10:30:00', 1800, 'desktop', 'Firefox'),
    ('s040', 15, '2025-02-10 15:30:00', '2025-02-10 16:00:00', 1800, 'tablet',  'Chrome'),
    ('s041', 17, '2025-02-11 08:00:00', '2025-02-11 08:30:00', 1800, 'desktop', 'Chrome'),
    ('s042', 19, '2025-02-12 11:00:00', '2025-02-12 12:30:00', 5400, 'desktop', 'Safari'),
    ('s043', 20, '2025-02-13 14:15:00', '2025-02-13 14:45:00', 1800, 'desktop', 'Chrome'),
    ('s044', 22, '2025-02-14 09:30:00', '2025-02-14 10:00:00', 1800, 'desktop', 'Firefox'),
    ('s045', 24, '2025-02-15 16:00:00', '2025-02-15 17:00:00', 3600, 'desktop', 'Chrome'),
    ('s046', 25, '2025-02-16 10:00:00', '2025-02-16 10:30:00', 1800, 'tablet',  'Safari'),
    ('s047', 27, '2025-02-17 13:30:00', '2025-02-17 14:00:00', 1800, 'desktop', 'Chrome'),
    ('s048', 29, '2025-02-18 08:45:00', '2025-02-18 09:30:00', 2700, 'desktop', 'Firefox'),
    ('s049', 30, '2025-02-19 11:00:00', '2025-02-19 11:30:00', 1800, 'desktop', 'Chrome'),
    ('s050', 1,  '2025-02-20 09:00:00', '2025-02-20 09:45:00', 2700, 'desktop', 'Chrome'),
    ('s051', 4,  '2025-02-21 14:30:00', '2025-02-21 15:30:00', 3600, 'desktop', 'Firefox'),
    ('s052', 8,  '2025-02-22 10:00:00', '2025-02-22 10:20:00', 1200, 'mobile',  'Chrome'),
    ('s053', 11, '2025-02-23 16:00:00', '2025-02-23 16:30:00', 1800, 'desktop', 'Safari'),
    ('s054', 16, '2025-02-24 08:30:00', '2025-02-24 09:00:00', 1800, 'desktop', 'Chrome'),
    ('s055', 18, '2025-02-25 13:00:00', '2025-02-25 14:00:00', 3600, 'desktop', 'Firefox'),
    ('s056', 21, '2025-02-26 11:00:00', '2025-02-26 11:30:00', 1800, 'mobile',  'Chrome'),
    ('s057', 23, '2025-02-27 09:15:00', '2025-02-27 09:45:00', 1800, 'desktop', 'Safari'),
    ('s058', 26, '2025-02-28 15:00:00', '2025-02-28 15:30:00', 1800, 'desktop', 'Chrome'),
    ('s059', 28, '2025-03-01 10:30:00', '2025-03-01 11:00:00', 1800, 'desktop', 'Firefox'),
    ('s060', 30, '2025-03-02 14:00:00', '2025-03-02 15:00:00', 3600, 'desktop', 'Chrome');

-- ── Events (150 events) ────────────────────────────────────────

INSERT INTO events (id, session_id, user_id, event_name, page_url, occurred_at, properties) VALUES
    (1,  's001', 1,  'page_view',     '/home',            '2025-01-05 09:15:00', '{"source":"google"}'),
    (2,  's001', 1,  'click',         '/features',        '2025-01-05 09:20:00', '{"button":"learn_more"}'),
    (3,  's001', 1,  'page_view',     '/pricing',         '2025-01-05 09:25:00', '{}'),
    (4,  's002', 1,  'page_view',     '/home',            '2025-01-06 14:20:00', '{"source":"direct"}'),
    (5,  's002', 1,  'signup_start',  '/signup',          '2025-01-06 14:30:00', '{}'),
    (6,  's002', 1,  'signup_complete','/signup/confirm',  '2025-01-06 14:45:00', '{"plan":"free"}'),
    (7,  's003', 2,  'page_view',     '/home',            '2025-01-05 10:00:00', '{"source":"twitter"}'),
    (8,  's003', 2,  'click',         '/demo',            '2025-01-05 10:15:00', '{"button":"watch_demo"}'),
    (9,  's003', 2,  'page_view',     '/demo',            '2025-01-05 10:20:00', '{}'),
    (10, 's003', 2,  'signup_start',  '/signup',          '2025-01-05 11:00:00', '{}'),
    (11, 's003', 2,  'signup_complete','/signup/confirm',  '2025-01-05 11:25:00', '{"plan":"pro"}'),
    (12, 's004', 3,  'page_view',     '/home',            '2025-01-06 08:30:00', '{"source":"google"}'),
    (13, 's004', 3,  'page_view',     '/blog',            '2025-01-06 08:35:00', '{}'),
    (14, 's005', 4,  'page_view',     '/home',            '2025-01-05 16:00:00', '{"source":"linkedin"}'),
    (15, 's005', 4,  'click',         '/enterprise',      '2025-01-05 16:10:00', '{"button":"contact_sales"}'),
    (16, 's005', 4,  'page_view',     '/enterprise',      '2025-01-05 16:15:00', '{}'),
    (17, 's005', 4,  'form_submit',   '/enterprise/contact','2025-01-05 16:45:00','{"company_size":"500+"}'),
    (18, 's006', 5,  'page_view',     '/home',            '2025-01-07 11:00:00', '{"source":"google"}'),
    (19, 's006', 5,  'page_view',     '/pricing',         '2025-01-07 11:05:00', '{}'),
    (20, 's006', 5,  'signup_start',  '/signup',          '2025-01-07 11:10:00', '{}'),
    (21, 's006', 5,  'signup_complete','/signup/confirm',  '2025-01-07 11:18:00', '{"plan":"pro"}'),
    (22, 's007', 6,  'page_view',     '/home',            '2025-01-08 09:00:00', '{"source":"direct"}'),
    (23, 's008', 7,  'page_view',     '/home',            '2025-01-08 13:00:00', '{"source":"google"}'),
    (24, 's008', 7,  'click',         '/features',        '2025-01-08 13:10:00', '{"button":"explore"}'),
    (25, 's008', 7,  'page_view',     '/features',        '2025-01-08 13:15:00', '{}'),
    (26, 's008', 7,  'signup_start',  '/signup',          '2025-01-08 14:00:00', '{}'),
    (27, 's008', 7,  'signup_complete','/signup/confirm',  '2025-01-08 14:25:00', '{"plan":"pro"}'),
    (28, 's009', 8,  'page_view',     '/home',            '2025-01-09 10:15:00', '{"source":"google"}'),
    (29, 's009', 8,  'page_view',     '/blog/post-1',     '2025-01-09 10:20:00', '{}'),
    (30, 's010', 9,  'page_view',     '/home',            '2025-01-10 15:00:00', '{"source":"linkedin"}'),
    (31, 's010', 9,  'click',         '/enterprise',      '2025-01-10 15:10:00', '{"button":"contact_sales"}'),
    (32, 's010', 9,  'page_view',     '/enterprise',      '2025-01-10 15:15:00', '{}'),
    (33, 's010', 9,  'form_submit',   '/enterprise/contact','2025-01-10 15:45:00','{"company_size":"100-500"}'),
    (34, 's011', 10, 'page_view',     '/home',            '2025-01-11 09:30:00', '{"source":"google"}'),
    (35, 's011', 10, 'click',         '/pricing',         '2025-01-11 09:40:00', '{"button":"compare_plans"}'),
    (36, 's011', 10, 'page_view',     '/pricing',         '2025-01-11 09:45:00', '{}'),
    (37, 's011', 10, 'signup_start',  '/signup',          '2025-01-11 09:50:00', '{}'),
    (38, 's011', 10, 'signup_complete','/signup/confirm',  '2025-01-11 09:58:00', '{"plan":"pro"}'),
    (39, 's012', 11, 'page_view',     '/home',            '2025-01-12 14:00:00', '{"source":"direct"}'),
    (40, 's012', 11, 'page_view',     '/about',           '2025-01-12 14:10:00', '{}'),
    (41, 's013', 12, 'page_view',     '/home',            '2025-01-13 08:00:00', '{"source":"google"}'),
    (42, 's013', 12, 'click',         '/demo',            '2025-01-13 08:15:00', '{"button":"watch_demo"}'),
    (43, 's013', 12, 'page_view',     '/demo',            '2025-01-13 08:20:00', '{}'),
    (44, 's013', 12, 'signup_start',  '/signup',          '2025-01-13 09:00:00', '{}'),
    (45, 's013', 12, 'signup_complete','/signup/confirm',  '2025-01-13 09:25:00', '{"plan":"pro"}'),
    (46, 's014', 13, 'page_view',     '/home',            '2025-01-14 11:00:00', '{"source":"twitter"}'),
    (47, 's014', 13, 'page_view',     '/blog/post-2',     '2025-01-14 11:05:00', '{}'),
    (48, 's015', 14, 'page_view',     '/home',            '2025-01-15 16:30:00', '{"source":"linkedin"}'),
    (49, 's015', 14, 'click',         '/enterprise',      '2025-01-15 16:40:00', '{"button":"contact_sales"}'),
    (50, 's015', 14, 'form_submit',   '/enterprise/contact','2025-01-15 17:15:00','{"company_size":"500+"}'),
    (51, 's016', 15, 'page_view',     '/home',            '2025-01-16 10:00:00', '{"source":"google"}'),
    (52, 's016', 15, 'click',         '/features',        '2025-01-16 10:10:00', '{"button":"learn_more"}'),
    (53, 's016', 15, 'signup_start',  '/signup',          '2025-01-16 10:30:00', '{}'),
    (54, 's016', 15, 'signup_complete','/signup/confirm',  '2025-01-16 10:42:00', '{"plan":"pro"}'),
    (55, 's017', 16, 'page_view',     '/home',            '2025-01-17 09:00:00', '{"source":"direct"}'),
    (56, 's017', 16, 'page_view',     '/pricing',         '2025-01-17 09:10:00', '{}'),
    (57, 's018', 17, 'page_view',     '/home',            '2025-01-18 13:30:00', '{"source":"google"}'),
    (58, 's018', 17, 'click',         '/demo',            '2025-01-18 13:40:00', '{"button":"watch_demo"}'),
    (59, 's018', 17, 'signup_start',  '/signup',          '2025-01-18 13:50:00', '{}'),
    (60, 's018', 17, 'signup_complete','/signup/confirm',  '2025-01-18 13:58:00', '{"plan":"pro"}'),
    (61, 's019', 18, 'page_view',     '/home',            '2025-01-19 08:45:00', '{"source":"google"}'),
    (62, 's019', 18, 'page_view',     '/blog/post-3',     '2025-01-19 08:50:00', '{}'),
    (63, 's020', 19, 'page_view',     '/home',            '2025-01-20 15:00:00', '{"source":"linkedin"}'),
    (64, 's020', 19, 'click',         '/enterprise',      '2025-01-20 15:10:00', '{"button":"contact_sales"}'),
    (65, 's020', 19, 'form_submit',   '/enterprise/contact','2025-01-20 16:00:00','{"company_size":"100-500"}'),
    (66, 's021', 20, 'page_view',     '/home',            '2025-01-21 10:30:00', '{"source":"google"}'),
    (67, 's021', 20, 'click',         '/pricing',         '2025-01-21 10:40:00', '{"button":"compare_plans"}'),
    (68, 's021', 20, 'signup_start',  '/signup',          '2025-01-21 10:50:00', '{}'),
    (69, 's021', 20, 'signup_complete','/signup/confirm',  '2025-01-21 10:58:00', '{"plan":"pro"}'),
    (70, 's022', 21, 'page_view',     '/home',            '2025-01-22 14:15:00', '{"source":"direct"}'),
    (71, 's023', 22, 'page_view',     '/home',            '2025-01-23 09:00:00', '{"source":"google"}'),
    (72, 's023', 22, 'click',         '/features',        '2025-01-23 09:15:00', '{"button":"explore"}'),
    (73, 's023', 22, 'signup_start',  '/signup',          '2025-01-23 10:00:00', '{}'),
    (74, 's023', 22, 'signup_complete','/signup/confirm',  '2025-01-23 10:25:00', '{"plan":"pro"}'),
    (75, 's024', 23, 'page_view',     '/home',            '2025-01-24 11:30:00', '{"source":"twitter"}'),
    (76, 's024', 23, 'page_view',     '/about',           '2025-01-24 11:40:00', '{}'),
    (77, 's025', 24, 'page_view',     '/home',            '2025-01-25 16:00:00', '{"source":"linkedin"}'),
    (78, 's025', 24, 'click',         '/enterprise',      '2025-01-25 16:10:00', '{"button":"contact_sales"}'),
    (79, 's025', 24, 'form_submit',   '/enterprise/contact','2025-01-25 16:45:00','{"company_size":"500+"}'),
    (80, 's026', 25, 'page_view',     '/home',            '2025-01-26 08:00:00', '{"source":"google"}'),
    (81, 's026', 25, 'click',         '/pricing',         '2025-01-26 08:10:00', '{"button":"compare_plans"}'),
    (82, 's026', 25, 'signup_start',  '/signup',          '2025-01-26 08:20:00', '{}'),
    (83, 's026', 25, 'signup_complete','/signup/confirm',  '2025-01-26 08:28:00', '{"plan":"pro"}'),
    (84, 's027', 26, 'page_view',     '/home',            '2025-01-27 13:00:00', '{"source":"direct"}'),
    (85, 's028', 27, 'page_view',     '/home',            '2025-01-28 10:00:00', '{"source":"google"}'),
    (86, 's028', 27, 'click',         '/demo',            '2025-01-28 10:15:00', '{"button":"watch_demo"}'),
    (87, 's028', 27, 'signup_start',  '/signup',          '2025-01-28 11:00:00', '{}'),
    (88, 's028', 27, 'signup_complete','/signup/confirm',  '2025-01-28 11:25:00', '{"plan":"pro"}'),
    (89, 's029', 28, 'page_view',     '/home',            '2025-01-29 09:30:00', '{"source":"google"}'),
    (90, 's029', 28, 'page_view',     '/blog/post-4',     '2025-01-29 09:35:00', '{}'),
    (91, 's030', 29, 'page_view',     '/home',            '2025-01-30 15:30:00', '{"source":"linkedin"}'),
    (92, 's030', 29, 'click',         '/enterprise',      '2025-01-30 15:40:00', '{"button":"contact_sales"}'),
    (93, 's030', 29, 'form_submit',   '/enterprise/contact','2025-01-30 16:15:00','{"company_size":"100-500"}'),
    (94, 's031', 1,  'page_view',     '/dashboard',       '2025-02-01 09:00:00', '{"source":"direct"}'),
    (95, 's031', 1,  'click',         '/dashboard/settings','2025-02-01 09:10:00','{"button":"upgrade"}'),
    (96, 's032', 2,  'page_view',     '/dashboard',       '2025-02-02 14:00:00', '{"source":"direct"}'),
    (97, 's032', 2,  'click',         '/dashboard/analytics','2025-02-02 14:20:00','{}'),
    (98, 's033', 3,  'page_view',     '/home',            '2025-02-03 10:15:00', '{"source":"google"}'),
    (99, 's034', 5,  'page_view',     '/dashboard',       '2025-02-04 11:00:00', '{"source":"direct"}'),
    (100,'s034', 5,  'click',         '/dashboard/export', '2025-02-04 11:30:00','{"format":"csv"}'),
    (101,'s035', 7,  'page_view',     '/dashboard',       '2025-02-05 08:30:00', '{"source":"direct"}'),
    (102,'s035', 7,  'click',         '/dashboard/analytics','2025-02-05 08:45:00','{}'),
    (103,'s036', 9,  'page_view',     '/dashboard',       '2025-02-06 16:00:00', '{"source":"direct"}'),
    (104,'s036', 9,  'click',         '/dashboard/team',   '2025-02-06 16:15:00','{}'),
    (105,'s037', 10, 'page_view',     '/home',            '2025-02-07 09:00:00', '{"source":"google"}'),
    (106,'s038', 12, 'page_view',     '/dashboard',       '2025-02-08 13:00:00', '{"source":"direct"}'),
    (107,'s038', 12, 'click',         '/dashboard/analytics','2025-02-08 13:30:00','{}'),
    (108,'s038', 12, 'click',         '/dashboard/export', '2025-02-08 14:10:00','{"format":"pdf"}'),
    (109,'s039', 14, 'page_view',     '/dashboard',       '2025-02-09 10:00:00', '{"source":"direct"}'),
    (110,'s039', 14, 'click',         '/dashboard/settings','2025-02-09 10:15:00','{"button":"invite_team"}'),
    (111,'s040', 15, 'page_view',     '/dashboard',       '2025-02-10 15:30:00', '{"source":"direct"}'),
    (112,'s040', 15, 'click',         '/dashboard/analytics','2025-02-10 15:45:00','{}'),
    (113,'s041', 17, 'page_view',     '/dashboard',       '2025-02-11 08:00:00', '{"source":"direct"}'),
    (114,'s041', 17, 'click',         '/dashboard/export', '2025-02-11 08:15:00','{"format":"csv"}'),
    (115,'s042', 19, 'page_view',     '/dashboard',       '2025-02-12 11:00:00', '{"source":"direct"}'),
    (116,'s042', 19, 'click',         '/dashboard/team',   '2025-02-12 11:30:00','{}'),
    (117,'s043', 20, 'page_view',     '/dashboard',       '2025-02-13 14:15:00', '{"source":"direct"}'),
    (118,'s043', 20, 'click',         '/dashboard/analytics','2025-02-13 14:30:00','{}'),
    (119,'s044', 22, 'page_view',     '/dashboard',       '2025-02-14 09:30:00', '{"source":"direct"}'),
    (120,'s044', 22, 'click',         '/dashboard/settings','2025-02-14 09:45:00','{"button":"upgrade"}'),
    (121,'s045', 24, 'page_view',     '/dashboard',       '2025-02-15 16:00:00', '{"source":"direct"}'),
    (122,'s045', 24, 'click',         '/dashboard/team',   '2025-02-15 16:20:00','{}'),
    (123,'s045', 24, 'click',         '/dashboard/analytics','2025-02-15 16:40:00','{}'),
    (124,'s046', 25, 'page_view',     '/dashboard',       '2025-02-16 10:00:00', '{"source":"direct"}'),
    (125,'s046', 25, 'click',         '/dashboard/export', '2025-02-16 10:15:00','{"format":"pdf"}'),
    (126,'s047', 27, 'page_view',     '/dashboard',       '2025-02-17 13:30:00', '{"source":"direct"}'),
    (127,'s047', 27, 'click',         '/dashboard/analytics','2025-02-17 13:45:00','{}'),
    (128,'s048', 29, 'page_view',     '/dashboard',       '2025-02-18 08:45:00', '{"source":"direct"}'),
    (129,'s048', 29, 'click',         '/dashboard/team',   '2025-02-18 09:00:00','{}'),
    (130,'s048', 29, 'click',         '/dashboard/settings','2025-02-18 09:15:00','{"button":"billing"}'),
    (131,'s049', 30, 'page_view',     '/dashboard',       '2025-02-19 11:00:00', '{"source":"direct"}'),
    (132,'s049', 30, 'click',         '/dashboard/analytics','2025-02-19 11:15:00','{}'),
    (133,'s050', 1,  'page_view',     '/dashboard',       '2025-02-20 09:00:00', '{"source":"direct"}'),
    (134,'s050', 1,  'click',         '/dashboard/analytics','2025-02-20 09:20:00','{}'),
    (135,'s050', 1,  'click',         '/dashboard/export', '2025-02-20 09:35:00','{"format":"csv"}'),
    (136,'s051', 4,  'page_view',     '/dashboard',       '2025-02-21 14:30:00', '{"source":"direct"}'),
    (137,'s051', 4,  'click',         '/dashboard/team',   '2025-02-21 14:50:00','{}'),
    (138,'s051', 4,  'click',         '/dashboard/settings','2025-02-21 15:10:00','{"button":"billing"}'),
    (139,'s052', 8,  'page_view',     '/home',            '2025-02-22 10:00:00', '{"source":"google"}'),
    (140,'s053', 11, 'page_view',     '/home',            '2025-02-23 16:00:00', '{"source":"direct"}'),
    (141,'s054', 16, 'page_view',     '/home',            '2025-02-24 08:30:00', '{"source":"google"}'),
    (142,'s055', 18, 'page_view',     '/home',            '2025-02-25 13:00:00', '{"source":"twitter"}'),
    (143,'s056', 21, 'page_view',     '/home',            '2025-02-26 11:00:00', '{"source":"direct"}'),
    (144,'s057', 23, 'page_view',     '/home',            '2025-02-27 09:15:00', '{"source":"google"}'),
    (145,'s058', 26, 'page_view',     '/home',            '2025-02-28 15:00:00', '{"source":"direct"}'),
    (146,'s059', 28, 'page_view',     '/home',            '2025-03-01 10:30:00', '{"source":"google"}'),
    (147,'s060', 30, 'page_view',     '/dashboard',       '2025-03-02 14:00:00', '{"source":"direct"}'),
    (148,'s060', 30, 'click',         '/dashboard/analytics','2025-03-02 14:20:00','{}'),
    (149,'s060', 30, 'click',         '/dashboard/export', '2025-03-02 14:40:00','{"format":"pdf"}'),
    (150,'s060', 30, 'click',         '/dashboard/settings','2025-03-02 14:50:00','{"button":"upgrade"}');

-- ── Page Views (80 page views) ─────────────────────────────────

INSERT INTO page_views (id, session_id, user_id, url, title, referrer, duration_s, viewed_at) VALUES
    (1,  's001', 1,  '/home',     'Home - Aurora',     'https://google.com',   300, '2025-01-05 09:15:00'),
    (2,  's001', 1,  '/features', 'Features - Aurora', '/home',                300, '2025-01-05 09:20:00'),
    (3,  's001', 1,  '/pricing',  'Pricing - Aurora',  '/features',            300, '2025-01-05 09:25:00'),
    (4,  's003', 2,  '/home',     'Home - Aurora',     'https://twitter.com',  900, '2025-01-05 10:00:00'),
    (5,  's003', 2,  '/demo',     'Demo - Aurora',     '/home',               2700, '2025-01-05 10:15:00'),
    (6,  's005', 4,  '/home',     'Home - Aurora',     'https://linkedin.com', 600, '2025-01-05 16:00:00'),
    (7,  's005', 4,  '/enterprise','Enterprise - Aurora','/home',             1800, '2025-01-05 16:10:00'),
    (8,  's008', 7,  '/home',     'Home - Aurora',     'https://google.com',   600, '2025-01-08 13:00:00'),
    (9,  's008', 7,  '/features', 'Features - Aurora', '/home',                300, '2025-01-08 13:10:00'),
    (10, 's010', 9,  '/home',     'Home - Aurora',     'https://linkedin.com', 600, '2025-01-10 15:00:00'),
    (11, 's010', 9,  '/enterprise','Enterprise - Aurora','/home',             1800, '2025-01-10 15:10:00'),
    (12, 's011', 10, '/home',     'Home - Aurora',     'https://google.com',   600, '2025-01-11 09:30:00'),
    (13, 's011', 10, '/pricing',  'Pricing - Aurora',  '/home',                300, '2025-01-11 09:40:00'),
    (14, 's013', 12, '/home',     'Home - Aurora',     'https://google.com',   900, '2025-01-13 08:00:00'),
    (15, 's013', 12, '/demo',     'Demo - Aurora',     '/home',               2400, '2025-01-13 08:15:00'),
    (16, 's015', 14, '/home',     'Home - Aurora',     'https://linkedin.com', 600, '2025-01-15 16:30:00'),
    (17, 's015', 14, '/enterprise','Enterprise - Aurora','/home',             2100, '2025-01-15 16:40:00'),
    (18, 's016', 15, '/home',     'Home - Aurora',     'https://google.com',   600, '2025-01-16 10:00:00'),
    (19, 's016', 15, '/features', 'Features - Aurora', '/home',               1200, '2025-01-16 10:10:00'),
    (20, 's018', 17, '/home',     'Home - Aurora',     'https://google.com',   600, '2025-01-18 13:30:00'),
    (21, 's018', 17, '/demo',     'Demo - Aurora',     '/home',                600, '2025-01-18 13:40:00'),
    (22, 's020', 19, '/home',     'Home - Aurora',     'https://linkedin.com', 600, '2025-01-20 15:00:00'),
    (23, 's020', 19, '/enterprise','Enterprise - Aurora','/home',             3000, '2025-01-20 15:10:00'),
    (24, 's021', 20, '/home',     'Home - Aurora',     'https://google.com',   600, '2025-01-21 10:30:00'),
    (25, 's021', 20, '/pricing',  'Pricing - Aurora',  '/home',                600, '2025-01-21 10:40:00'),
    (26, 's023', 22, '/home',     'Home - Aurora',     'https://google.com',   900, '2025-01-23 09:00:00'),
    (27, 's023', 22, '/features', 'Features - Aurora', '/home',               2700, '2025-01-23 09:15:00'),
    (28, 's025', 24, '/home',     'Home - Aurora',     'https://linkedin.com', 600, '2025-01-25 16:00:00'),
    (29, 's025', 24, '/enterprise','Enterprise - Aurora','/home',             2100, '2025-01-25 16:10:00'),
    (30, 's026', 25, '/home',     'Home - Aurora',     'https://google.com',   600, '2025-01-26 08:00:00'),
    (31, 's026', 25, '/pricing',  'Pricing - Aurora',  '/home',                600, '2025-01-26 08:10:00'),
    (32, 's028', 27, '/home',     'Home - Aurora',     'https://google.com',   900, '2025-01-28 10:00:00'),
    (33, 's028', 27, '/demo',     'Demo - Aurora',     '/home',               2700, '2025-01-28 10:15:00'),
    (34, 's030', 29, '/home',     'Home - Aurora',     'https://linkedin.com', 600, '2025-01-30 15:30:00'),
    (35, 's030', 29, '/enterprise','Enterprise - Aurora','/home',             2100, '2025-01-30 15:40:00'),
    (36, 's031', 1,  '/dashboard','Dashboard - Aurora','',                   600, '2025-02-01 09:00:00'),
    (37, 's031', 1,  '/dashboard/settings','Settings - Aurora','/dashboard',  600, '2025-02-01 09:10:00'),
    (38, 's032', 2,  '/dashboard','Dashboard - Aurora','',                  1200, '2025-02-02 14:00:00'),
    (39, 's032', 2,  '/dashboard/analytics','Analytics - Aurora','/dashboard',1800, '2025-02-02 14:20:00'),
    (40, 's034', 5,  '/dashboard','Dashboard - Aurora','',                  1800, '2025-02-04 11:00:00'),
    (41, 's034', 5,  '/dashboard/export','Export - Aurora','/dashboard',     1800, '2025-02-04 11:30:00'),
    (42, 's035', 7,  '/dashboard','Dashboard - Aurora','',                   900, '2025-02-05 08:30:00'),
    (43, 's035', 7,  '/dashboard/analytics','Analytics - Aurora','/dashboard',2700, '2025-02-05 08:45:00'),
    (44, 's036', 9,  '/dashboard','Dashboard - Aurora','',                   900, '2025-02-06 16:00:00'),
    (45, 's036', 9,  '/dashboard/team','Team - Aurora','/dashboard',         1800, '2025-02-06 16:15:00'),
    (46, 's038', 12, '/dashboard','Dashboard - Aurora','',                  1800, '2025-02-08 13:00:00'),
    (47, 's038', 12, '/dashboard/analytics','Analytics - Aurora','/dashboard',2400, '2025-02-08 13:30:00'),
    (48, 's038', 12, '/dashboard/export','Export - Aurora','/dashboard/analytics',1200, '2025-02-08 14:10:00'),
    (49, 's039', 14, '/dashboard','Dashboard - Aurora','',                   900, '2025-02-09 10:00:00'),
    (50, 's039', 14, '/dashboard/settings','Settings - Aurora','/dashboard',  900, '2025-02-09 10:15:00'),
    (51, 's040', 15, '/dashboard','Dashboard - Aurora','',                   900, '2025-02-10 15:30:00'),
    (52, 's040', 15, '/dashboard/analytics','Analytics - Aurora','/dashboard', 900, '2025-02-10 15:45:00'),
    (53, 's041', 17, '/dashboard','Dashboard - Aurora','',                   900, '2025-02-11 08:00:00'),
    (54, 's041', 17, '/dashboard/export','Export - Aurora','/dashboard',      900, '2025-02-11 08:15:00'),
    (55, 's042', 19, '/dashboard','Dashboard - Aurora','',                  1800, '2025-02-12 11:00:00'),
    (56, 's042', 19, '/dashboard/team','Team - Aurora','/dashboard',         1800, '2025-02-12 11:30:00'),
    (57, 's043', 20, '/dashboard','Dashboard - Aurora','',                   900, '2025-02-13 14:15:00'),
    (58, 's043', 20, '/dashboard/analytics','Analytics - Aurora','/dashboard', 900, '2025-02-13 14:30:00'),
    (59, 's044', 22, '/dashboard','Dashboard - Aurora','',                   900, '2025-02-14 09:30:00'),
    (60, 's044', 22, '/dashboard/settings','Settings - Aurora','/dashboard',  900, '2025-02-14 09:45:00'),
    (61, 's045', 24, '/dashboard','Dashboard - Aurora','',                  1200, '2025-02-15 16:00:00'),
    (62, 's045', 24, '/dashboard/team','Team - Aurora','/dashboard',         1200, '2025-02-15 16:20:00'),
    (63, 's045', 24, '/dashboard/analytics','Analytics - Aurora','/dashboard',1200, '2025-02-15 16:40:00'),
    (64, 's046', 25, '/dashboard','Dashboard - Aurora','',                   900, '2025-02-16 10:00:00'),
    (65, 's046', 25, '/dashboard/export','Export - Aurora','/dashboard',      900, '2025-02-16 10:15:00'),
    (66, 's047', 27, '/dashboard','Dashboard - Aurora','',                   900, '2025-02-17 13:30:00'),
    (67, 's047', 27, '/dashboard/analytics','Analytics - Aurora','/dashboard', 900, '2025-02-17 13:45:00'),
    (68, 's048', 29, '/dashboard','Dashboard - Aurora','',                   900, '2025-02-18 08:45:00'),
    (69, 's048', 29, '/dashboard/team','Team - Aurora','/dashboard',          900, '2025-02-18 09:00:00'),
    (70, 's048', 29, '/dashboard/settings','Settings - Aurora','/dashboard',  900, '2025-02-18 09:15:00'),
    (71, 's049', 30, '/dashboard','Dashboard - Aurora','',                   900, '2025-02-19 11:00:00'),
    (72, 's049', 30, '/dashboard/analytics','Analytics - Aurora','/dashboard', 900, '2025-02-19 11:15:00'),
    (73, 's050', 1,  '/dashboard','Dashboard - Aurora','',                  1200, '2025-02-20 09:00:00'),
    (74, 's050', 1,  '/dashboard/analytics','Analytics - Aurora','/dashboard', 900, '2025-02-20 09:20:00'),
    (75, 's050', 1,  '/dashboard/export','Export - Aurora','/dashboard/analytics',900, '2025-02-20 09:35:00'),
    (76, 's060', 30, '/dashboard','Dashboard - Aurora','',                  1200, '2025-03-02 14:00:00'),
    (77, 's060', 30, '/dashboard/analytics','Analytics - Aurora','/dashboard',1200, '2025-03-02 14:20:00'),
    (78, 's060', 30, '/dashboard/export','Export - Aurora','/dashboard/analytics',600, '2025-03-02 14:40:00'),
    (79, 's060', 30, '/dashboard/settings','Settings - Aurora','/dashboard/export',600, '2025-03-02 14:50:00'),
    (80, 's060', 30, '/dashboard','Dashboard - Aurora','/dashboard/settings', 600, '2025-03-02 14:55:00');

-- ── Conversions (funnel: visit -> signup -> activate -> pay) ───

INSERT INTO conversions (id, user_id, funnel_stage, completed_at, revenue) VALUES
    (1,  1,  'visit',    '2025-01-05 09:15:00', 0),
    (2,  1,  'signup',   '2025-01-06 14:45:00', 0),
    (3,  1,  'activate', '2025-02-01 09:10:00', 0),
    (4,  2,  'visit',    '2025-01-05 10:00:00', 0),
    (5,  2,  'signup',   '2025-01-05 11:25:00', 29),
    (6,  2,  'activate', '2025-02-02 14:20:00', 29),
    (7,  3,  'visit',    '2025-01-06 08:30:00', 0),
    (8,  4,  'visit',    '2025-01-05 16:00:00', 0),
    (9,  4,  'signup',   '2025-01-05 16:45:00', 99),
    (10, 4,  'activate', '2025-02-21 14:50:00', 99),
    (11, 4,  'pay',      '2025-02-21 15:10:00', 99),
    (12, 5,  'visit',    '2025-01-07 11:00:00', 0),
    (13, 5,  'signup',   '2025-01-07 11:18:00', 29),
    (14, 5,  'activate', '2025-02-04 11:30:00', 29),
    (15, 6,  'visit',    '2025-01-08 09:00:00', 0),
    (16, 7,  'visit',    '2025-01-08 13:00:00', 0),
    (17, 7,  'signup',   '2025-01-08 14:25:00', 29),
    (18, 7,  'activate', '2025-02-05 08:45:00', 29),
    (19, 8,  'visit',    '2025-01-09 10:15:00', 0),
    (20, 9,  'visit',    '2025-01-10 15:00:00', 0),
    (21, 9,  'signup',   '2025-01-10 15:45:00', 99),
    (22, 9,  'activate', '2025-02-06 16:15:00', 99),
    (23, 10, 'visit',    '2025-01-11 09:30:00', 0),
    (24, 10, 'signup',   '2025-01-11 09:58:00', 29),
    (25, 11, 'visit',    '2025-01-12 14:00:00', 0),
    (26, 12, 'visit',    '2025-01-13 08:00:00', 0),
    (27, 12, 'signup',   '2025-01-13 09:25:00', 29),
    (28, 12, 'activate', '2025-02-08 13:30:00', 29),
    (29, 13, 'visit',    '2025-01-14 11:00:00', 0),
    (30, 14, 'visit',    '2025-01-15 16:30:00', 0),
    (31, 14, 'signup',   '2025-01-15 17:15:00', 99),
    (32, 14, 'activate', '2025-02-09 10:15:00', 99),
    (33, 14, 'pay',      '2025-02-09 10:30:00', 99),
    (34, 15, 'visit',    '2025-01-16 10:00:00', 0),
    (35, 15, 'signup',   '2025-01-16 10:42:00', 29),
    (36, 15, 'activate', '2025-02-10 15:45:00', 29),
    (37, 16, 'visit',    '2025-01-17 09:00:00', 0),
    (38, 17, 'visit',    '2025-01-18 13:30:00', 0),
    (39, 17, 'signup',   '2025-01-18 13:58:00', 29),
    (40, 17, 'activate', '2025-02-11 08:15:00', 29),
    (41, 18, 'visit',    '2025-01-19 08:45:00', 0),
    (42, 19, 'visit',    '2025-01-20 15:00:00', 0),
    (43, 19, 'signup',   '2025-01-20 16:00:00', 99),
    (44, 19, 'activate', '2025-02-12 11:30:00', 99),
    (45, 20, 'visit',    '2025-01-21 10:30:00', 0),
    (46, 20, 'signup',   '2025-01-21 10:58:00', 29),
    (47, 20, 'activate', '2025-02-13 14:30:00', 29),
    (48, 21, 'visit',    '2025-01-22 14:15:00', 0),
    (49, 22, 'visit',    '2025-01-23 09:00:00', 0),
    (50, 22, 'signup',   '2025-01-23 10:25:00', 29),
    (51, 22, 'activate', '2025-02-14 09:45:00', 29),
    (52, 23, 'visit',    '2025-01-24 11:30:00', 0),
    (53, 24, 'visit',    '2025-01-25 16:00:00', 0),
    (54, 24, 'signup',   '2025-01-25 16:45:00', 99),
    (55, 24, 'activate', '2025-02-15 16:20:00', 99),
    (56, 24, 'pay',      '2025-02-15 16:40:00', 99),
    (57, 25, 'visit',    '2025-01-26 08:00:00', 0),
    (58, 25, 'signup',   '2025-01-26 08:28:00', 29),
    (59, 25, 'activate', '2025-02-16 10:15:00', 29),
    (60, 26, 'visit',    '2025-01-27 13:00:00', 0),
    (61, 27, 'visit',    '2025-01-28 10:00:00', 0),
    (62, 27, 'signup',   '2025-01-28 11:25:00', 29),
    (63, 27, 'activate', '2025-02-17 13:45:00', 29),
    (64, 28, 'visit',    '2025-01-29 09:30:00', 0),
    (65, 29, 'visit',    '2025-01-30 15:30:00', 0),
    (66, 29, 'signup',   '2025-01-30 16:15:00', 99),
    (67, 29, 'activate', '2025-02-18 09:00:00', 99),
    (68, 29, 'pay',      '2025-02-18 09:15:00', 99),
    (69, 30, 'visit',    '2025-02-19 11:00:00', 0),
    (70, 30, 'signup',   '2025-02-19 11:30:00', 29),
    (71, 30, 'activate', '2025-03-02 14:20:00', 29);
"""

_SEED_REGISTRY: dict[str, str] = {
    "aurora-sqlite": _SQLITE_SEED_SQL,
    "aurora-duckdb": _DUCKDB_SEED_SQL,
}


def seed_default_datasource(service: "DatasourceService", name: str) -> None:
    """Populate a datasource with its registered mock data.

    Silently skips if the datasource is not registered, not in the
    seed registry, or already contains tables.
    """
    sql_template = _SEED_REGISTRY.get(name)
    if sql_template is None:
        logger.debug("Seed: no seed data registered for '%s', skipping", name)
        return

    try:
        connector = service.get_connector(name)
    except KeyError:
        logger.debug("Seed: datasource '%s' not registered, skipping", name)
        return

    tables = connector.get_table_names()
    if tables:
        logger.debug("Seed: datasource '%s' already has tables, skipping", name)
        return

    statements = []
    for block in sql_template.split(";"):
        lines = block.strip().splitlines()
        cleaned = "\n".join(line for line in lines if not line.strip().startswith("--")).strip()
        if cleaned:
            statements.append(cleaned)

    logger.info("Seed [%s] parsed %d statements", name, len(statements))
    for i, stmt in enumerate(statements, 1):
        logger.info("Seed [%s] statement %d: %s", name, i, stmt[:100].replace("\n", " "))

    created = 0
    for i, stmt in enumerate(statements, 1):
        logger.info("Seed [%s] executing statement %d/%d: %s...", name, i, len(statements), stmt[:80])
        ok, result = connector.run(stmt)
        if not ok:
            logger.warning("Seed [%s] statement %d failed: %s — %s", name, i, stmt[:80], result)
        else:
            logger.info("Seed [%s] statement %d succeeded", name, i)
            created += 1

    logger.info("Seed: executed %d/%d statements into '%s'", created, len(statements), name)
