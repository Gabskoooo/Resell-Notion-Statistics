DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS users;

-- Table pour les utilisateurs
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    username TEXT,
    avatar_url TEXT,
    is_admin INTEGER DEFAULT 0,
    discord_id TEXT UNIQUE,
    key_status TEXT DEFAULT 'inactive' NOT NULL CHECK(key_status IN ('active', 'inactive'))
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    sku TEXT NOT NULL, -- LE MOT-CLÉ UNIQUE A ÉTÉ SUPPRIMÉ
    name TEXT NOT NULL,
    size TEXT,
    purchase_price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    price REAL,
    description TEXT,
    image_url TEXT,
    date_added TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER, -- Reste pour le lien vers le produit
    item_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    sale_price REAL NOT NULL,
    purchase_price_at_sale REAL, -- NOUVEAU : Prix d'achat du produit au moment de la vente
    sale_date TEXT NOT NULL,
    notes TEXT,
    sale_channel TEXT, -- NOUVEAU : Canal de vente
    shipping_cost REAL DEFAULT 0.0, -- AJOUTÉ : Frais de port
    fees REAL DEFAULT 0.0,          -- AJOUTÉ : Frais de plateforme/commission
    profit REAL DEFAULT 0.0,        -- AJOUTÉ : Bénéfice calculé
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE SET NULL
);


-- Ajoutez des index pour de meilleures performances sur les clés étrangères
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_discord_id ON users (discord_id);
CREATE INDEX IF NOT EXISTS idx_products_user_id ON products (user_id);
CREATE INDEX IF NOT EXISTS idx_sales_user_id ON sales (user_id);
CREATE INDEX IF NOT EXISTS idx_sales_product_id ON sales (product_id);