from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg
import hashlib
import secrets
from datetime import datetime
from functools import wraps
import requests
from bleach import clean
from dotenv import load_dotenv
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# โหลด environment variables
load_dotenv()

# PostgreSQL configuration
DB_CONFIG = {
    'dbname': 'chainlogger_db',
    'user': 'chainlogger_user',
    'password': os.getenv('DB_PASSWORD', 'Chainlogger@2025'),
    'host': 'localhost',
    'port': '5432'
}


# Binance API URL
BINANCE_API_URL = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

class Blockchain:
    def __init__(self, wallet_address=None, private_key=None):
        self.wallet_address = wallet_address
        self.private_key = private_key
        self.chain = []
        self.reward_amount = 10
        self.create_table()
        self.load_blocks_from_db()
        if not self.chain:
            self.create_genesis_block()

    def create_table(self):
        conn = psycopg.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                puk_balance REAL DEFAULT 0.0,
                is_admin BOOLEAN DEFAULT FALSE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blocks (
                id SERIAL PRIMARY KEY,
                "index" INTEGER UNIQUE NOT NULL,
                message TEXT NOT NULL,
                hash TEXT NOT NULL,
                previous_hash TEXT NOT NULL DEFAULT '0',
                timestamp TIMESTAMP NOT NULL,
                owner_id INTEGER REFERENCES users(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                from_address TEXT NOT NULL,
                to_address TEXT NOT NULL,
                amount REAL NOT NULL,
                block_index INTEGER
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                id SERIAL PRIMARY KEY,
                wallet_address TEXT UNIQUE NOT NULL,
                private_key TEXT NOT NULL,
                balance REAL DEFAULT 0.0,
                user_id INTEGER REFERENCES users(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS block_ownership_history (
                id SERIAL PRIMARY KEY,
                block_index INTEGER NOT NULL REFERENCES blocks("index"),
                previous_owner_id INTEGER REFERENCES users(id),
                new_owner_id INTEGER REFERENCES users(id),
                timestamp TIMESTAMP NOT NULL,
                price REAL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                user_id INTEGER REFERENCES users(id),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id SERIAL PRIMARY KEY,
                post_id INTEGER REFERENCES posts(id),
                user_id INTEGER REFERENCES users(id),
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            ALTER TABLE blocks 
            ADD COLUMN IF NOT EXISTS previous_hash TEXT NOT NULL DEFAULT '0'
        ''')
        cursor.execute('''
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE
        ''')
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_admin = TRUE')
        admin_count = cursor.fetchone()[0]
        if admin_count == 0:
            admin_username = os.getenv('ADMIN_USERNAME', 'admin_user')
            admin_password = os.getenv('ADMIN_PASSWORD')
            if not admin_password:
                print("Warning: ADMIN_PASSWORD not set in .env file. Please use /register_admin to create an admin.")
            else:
                hashed_password = hashlib.sha256(admin_password.encode()).hexdigest()
                try:
                    cursor.execute('''
                        INSERT INTO users (username, password, puk_balance, is_admin)
                        VALUES (%s, %s, %s, %s) RETURNING id
                    ''', (admin_username, hashed_password, 0.0, True))
                    admin_user_id = cursor.fetchone()[0]
                    wallet_address = secrets.token_hex(16)
                    private_key = secrets.token_hex(32)
                    cursor.execute('''
                        INSERT INTO wallets (wallet_address, private_key, balance, user_id)
                        VALUES (%s, %s, %s, %s)
                    ''', (wallet_address, private_key, 0.0, admin_user_id))
                    print(f"Created default admin user: {admin_username}. Use /register_admin or .env password to log in.")
                except psycopg2.IntegrityError:
                    print(f"Admin user {admin_username} already exists.")
        
        conn.commit()
        conn.close()
        print("Database tables created")

    def create_genesis_block(self):
        genesis_message = "Genesis Block - Initializing Blockchain"
        genesis_hash = "Genesis"
        genesis_previous_hash = "0" * 64
        genesis_block = {
            "index": 0,
            "message": genesis_message,
            "transactions": [],
            "hash": genesis_hash,
            "previous_hash": genesis_previous_hash,
            "owner_id": None,
            "timestamp": datetime.now().isoformat()
        }
        self.chain.append(genesis_block)
        self.save_block_to_db(0, genesis_message, genesis_hash, genesis_previous_hash, [], None)

    def load_blocks_from_db(self):
        self.chain = []
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT "index", message, hash, previous_hash, timestamp, owner_id FROM blocks')
        for row in cursor.fetchall():
            block = {
                "index": row[0],
                "message": row[1],
                "hash": row[2],
                "previous_hash": row[3],
                "timestamp": row[4],
                "owner_id": row[5],
                "transactions": []
            }
            cursor.execute('SELECT from_address, to_address, amount FROM transactions WHERE block_index = %s', (row[0],))
            block["transactions"] = [{"from_address": tx[0], "to_address": tx[1], "amount": tx[2]} for tx in cursor.fetchall()]
            self.chain.append(block)
        conn.close()

    def add_block(self, message, transactions=None):
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT MAX("index") FROM blocks')
        max_index = cursor.fetchone()[0]
        new_index = 0 if max_index is None else max_index + 1
        
        previous_hash = self.chain[-1]["hash"] if self.chain else "0" * 64
        new_hash = hashlib.sha256(f"{previous_hash}{new_index}{message}".encode('utf-8')).hexdigest()
        block_transactions = transactions if transactions else []
        
        new_block = {
            "index": new_index,
            "message": message,
            "transactions": block_transactions,
            "hash": new_hash,
            "previous_hash": previous_hash,
            "owner_id": session.get('user_id'),
            "timestamp": datetime.now().isoformat()
        }
        
        self.chain.append(new_block)
        self.save_block_to_db(new_index, message, new_hash, previous_hash, block_transactions, session.get('user_id'))
        self.give_reward()
        conn.close()

    def save_block_to_db(self, index, message, block_hash, previous_hash, transactions, owner_id):
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO blocks ("index", message, hash, previous_hash, timestamp, owner_id) VALUES (%s, %s, %s, %s, %s, %s)',
                       (index, message, block_hash, previous_hash, datetime.now().isoformat(), owner_id))
        for tx in transactions:
            cursor.execute('INSERT INTO transactions (from_address, to_address, amount, block_index) VALUES (%s, %s, %s, %s)',
                           (tx["from_address"], tx["to_address"], tx["amount"], index))
        conn.commit()
        conn.close()
        
    def update_block_message(self, index, new_message):
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        previous_hash = self.chain[index]["previous_hash"] if index < len(self.chain) else "0" * 64
        new_hash = hashlib.sha256(f"{previous_hash}{index}{new_message}".encode('utf-8')).hexdigest()
        cursor.execute('UPDATE blocks SET message = %s, hash = %s, timestamp = %s WHERE "index" = %s',
                       (new_message, new_hash, datetime.now().isoformat(), index))
        conn.commit()
        conn.close()
        for block in self.chain:
            if block["index"] == index:
                block["message"] = new_message
                block["hash"] = new_hash
                block["timestamp"] = datetime.now().isoformat()
                break

    def give_reward(self):
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO transactions (from_address, to_address, amount) VALUES (%s, %s, %s)',
                       ("system", self.wallet_address, self.reward_amount))
        cursor.execute('UPDATE users SET puk_balance = puk_balance + %s WHERE id = (SELECT user_id FROM wallets WHERE wallet_address = %s)',
                       (self.reward_amount, self.wallet_address))
        conn.commit()
        conn.close()

    def view_transactions(self):
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT id, timestamp, from_address, to_address, amount, block_index FROM transactions')
        transactions = [{"id": t[0], "timestamp": t[1], "from": t[2], "to": t[3], "amount": t[4], "block_index": t[5]} for t in cursor.fetchall()]
        conn.close()
        return transactions

    def calculate_balance(self):
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT SUM(amount) FROM transactions WHERE to_address = %s', (self.wallet_address,))
        incoming = cursor.fetchone()[0] or 0
        cursor.execute('SELECT SUM(amount) FROM transactions WHERE from_address = %s', (self.wallet_address,))
        outgoing = cursor.fetchone()[0] or 0
        conn.close()
        return incoming - outgoing

    def transfer_coins(self, to_address, amount):
        balance = self.calculate_balance()
        if balance < amount:
            return False, "Insufficient balance"
        if amount <= 0:
            return False, "Amount must be greater than 0"
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT wallet_address FROM wallets WHERE wallet_address = %s', (to_address,))
        if not cursor.fetchone():
            conn.close()
            return False, "Recipient address does not exist"
        cursor.execute('INSERT INTO transactions (from_address, to_address, amount) VALUES (%s, %s, %s)',
                       (self.wallet_address, to_address, amount))
        conn.commit()
        conn.close()
        return True, "Transfer successful"

blockchain = Blockchain()

# ฟังก์ชันช่วยเหลือ
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'danger')
            return redirect(url_for('login'))
        if not session.get('is_admin', False):
            flash('Admin access required.', 'danger')
            return redirect(url_for('blockchain_info'))
        return f(*args, **kwargs)
    return decorated_function

def get_username():
    if 'user_id' in session:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT username FROM users WHERE id = %s', (session['user_id'],))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "Unknown"
    return None

def is_admin():
    return session.get('is_admin', False)

def get_blockchain():
    if 'user_id' in session:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT wallet_address, private_key FROM wallets WHERE user_id = %s', (session['user_id'],))
        wallet = cursor.fetchone()
        conn.close()
        if wallet:
            return Blockchain(wallet[0], wallet[1])
    return blockchain

def get_puk_balance():
    if 'user_id' in session:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT puk_balance FROM users WHERE id = %s', (session['user_id'],))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0.0
    return 0.0
# ลงทะเบียนฟังก์ชันใน Jinja environment
app.jinja_env.globals.update(get_username=get_username, is_admin=is_admin)

# Routes
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username, password, puk_balance, is_admin) VALUES (%s, %s, %s, %s) RETURNING id',
                           (username, hashed_password, 0.0, False))
            user_id = cursor.fetchone()[0]
            wallet_address = secrets.token_hex(16)
            private_key = secrets.token_hex(32)
            cursor.execute('INSERT INTO wallets (wallet_address, private_key, balance, user_id) VALUES (%s, %s, %s, %s)',
                           (wallet_address, private_key, 0.0, user_id))
            conn.commit()
            conn.close()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            flash('Username already exists.', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT id, is_admin FROM users WHERE username = %s AND password = %s', (username, hashed_password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            session['is_admin'] = user[1]
            flash('Logged in successfully!', 'success')
            return redirect(url_for('blockchain_info'))
        else:
            flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/register_admin', methods=['GET', 'POST'])
def register_admin():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_admin = TRUE')
    admin_count = cursor.fetchone()[0]
    conn.close()
    
    if admin_count > 0 and not session.get('is_admin', False):
        flash('Only existing admins can register new admins.', 'danger')
        return redirect(url_for('blockchain_info'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username, password, puk_balance, is_admin) VALUES (%s, %s, %s, %s) RETURNING id',
                           (username, hashed_password, 0.0, True))
            user_id = cursor.fetchone()[0]
            wallet_address = secrets.token_hex(16)
            private_key = secrets.token_hex(32)
            cursor.execute('INSERT INTO wallets (wallet_address, private_key, balance, user_id) VALUES (%s, %s, %s, %s)',
                           (wallet_address, private_key, 0.0, user_id))
            conn.commit()
            conn.close()
            flash('Forged a new Crypto Samurai Admin! Please log in.', 'success')
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            flash('Username already exists.', 'danger')
    return render_template('register_admin.html')

@app.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, p.title, p.content, p.timestamp, u.username 
        FROM posts p 
        LEFT JOIN users u ON p.user_id = u.id 
        ORDER BY p.timestamp DESC
    ''')
    posts = [
        {"id": row[0], "title": row[1], "content": row[2], "timestamp": row[3], "username": row[4] or "None"}
        for row in cursor.fetchall()
    ]
    cursor.execute('''
        SELECT c.id, c.post_id, c.content, c.timestamp, u.username, p.title
        FROM comments c 
        LEFT JOIN users u ON c.user_id = u.id 
        LEFT JOIN posts p ON c.post_id = p.id 
        ORDER BY c.timestamp DESC
    ''')
    comments = [
        {"id": row[0], "post_id": row[1], "content": row[2], "timestamp": row[3], "username": row[4] or "None", "post_title": row[5] or "Unknown"}
        for row in cursor.fetchall()
    ]
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM transactions')
    total_transactions = cursor.fetchone()[0]
    conn.close()
    return render_template('admin_dashboard.html', posts=posts, comments=comments, total_users=total_users, total_transactions=total_transactions)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_admin', None)
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/board/delete_post/<int:post_id>', methods=['POST'])
@admin_required
def delete_post(post_id):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM posts WHERE id = %s', (post_id,))
    if not cursor.fetchone():
        conn.close()
        flash('Post not found.', 'danger')
        return redirect(url_for('board'))
    cursor.execute('DELETE FROM comments WHERE post_id = %s', (post_id,))
    cursor.execute('DELETE FROM posts WHERE id = %s', (post_id,))
    conn.commit()
    conn.close()
    flash('Post and its comments slashed from the Dojo!', 'success')
    return redirect(url_for('board'))

@app.route('/board/delete_comment/<int:comment_id>', methods=['POST'])
@admin_required
def delete_comment(comment_id):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute('SELECT id, post_id FROM comments WHERE id = %s', (comment_id,))
    comment = cursor.fetchone()
    if not comment:
        conn.close()
        flash('Comment not found.', 'danger')
        return redirect(url_for('board'))
    post_id = comment[1]
    cursor.execute('DELETE FROM comments WHERE id = %s', (comment_id,))
    conn.commit()
    conn.close()
    flash('Comment slashed from the Dojo!', 'success')
    return redirect(url_for('post_details', post_id=post_id))

# ... (ส่วนที่เหลือของโค้ดเหมือนเดิม)

@app.route('/blockchain', methods=['GET'])
@login_required
def blockchain_info():
    blockchain = get_blockchain()
    blockchain.load_blocks_from_db()
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    page = request.args.get('page', 1, type=int)
    per_page = 10
    if page < 1:
        page = 1
    offset = (page - 1) * per_page
    sort_by = request.args.get('sort_by', 'index')
    sort_order = request.args.get('sort_order', 'asc')
    valid_sort_columns = {'index': 'b."index"', 'owner': 'u.username'}
    sort_column = valid_sort_columns.get(sort_by, 'b."index"')
    valid_sort_orders = ['asc', 'desc']
    sort_order = sort_order if sort_order in valid_sort_orders else 'asc'
    query = '''
        SELECT b."index", b.message, b.hash, u.username 
        FROM blocks b 
        LEFT JOIN users u ON b.owner_id = u.id 
        ORDER BY {} {}
        LIMIT %s OFFSET %s
    '''.format(sort_column, sort_order.upper())
    cursor.execute(query, (per_page, offset))
    blocks = [{"index": row[0], "message": row[1], "hash": row[2], "owner": row[3] or "None"} for row in cursor.fetchall()]
    cursor.execute('SELECT COUNT(*) FROM blocks')
    total_blocks = cursor.fetchone()[0]
    total_pages = (total_blocks + per_page - 1) // per_page
    if page > total_pages and total_blocks > 0:
        page = total_pages
    conn.close()
    return render_template(
        'blockchain.html',
        blocks=blocks,
        page=page,
        total_pages=total_pages,
        sort_by=sort_by,
        sort_order=sort_order,
        total_blocks=total_blocks
    )
# Sanitize ฟังก์ชันสำหรับป้องกัน XSS
def sanitize_text(text):
    allowed_tags = ['b', 'i', 'u', 'strong', 'em']
    return clean(text, tags=allowed_tags, strip=True)

@app.route('/board', methods=['GET'])
@login_required
def board():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # รับค่าพารามิเตอร์สำหรับการแบ่งหน้า
    page = request.args.get('page', 1, type=int)
    per_page = 10
    if page < 1:
        page = 1
    offset = (page - 1) * per_page

    # ดึงกระทู้
    query = '''
        SELECT p.id, p.title, p.content, p.timestamp, u.username 
        FROM posts p 
        LEFT JOIN users u ON p.user_id = u.id 
        ORDER BY p.timestamp DESC 
        LIMIT %s OFFSET %s
    '''
    cursor.execute(query, (per_page, offset))
    posts = [
        {"id": row[0], "title": row[1], "content": row[2], "timestamp": row[3], "username": row[4] or "None"}
        for row in cursor.fetchall()
    ]

    # คำนวณจำนวนหน้าทั้งหมด
    cursor.execute('SELECT COUNT(*) FROM posts')
    total_posts = cursor.fetchone()[0]
    total_pages = (total_posts + per_page - 1) // per_page

    if page > total_pages and total_posts > 0:
        page = total_pages

    conn.close()
    return render_template('board.html', posts=posts, page=page, total_pages=total_pages, total_posts=total_posts)

@app.route('/board/new', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        if not title or not content:
            flash('Title and content are required.')
            return redirect(url_for('new_post'))
        
        sanitized_title = sanitize_text(title)
        sanitized_content = sanitize_text(content)
        
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO posts (title, content, user_id) VALUES (%s, %s, %s)',
            (sanitized_title, sanitized_content, session['user_id'])
        )
        conn.commit()
        conn.close()
        flash('Post created successfully!')
        return redirect(url_for('board'))
    
    return render_template('new_post.html')

@app.route('/board/<int:post_id>', methods=['GET', 'POST'])
@login_required
def post_details(post_id):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # ดึงข้อมูลกระทู้
    cursor.execute(
        'SELECT p.id, p.title, p.content, p.timestamp, u.username '
        'FROM posts p LEFT JOIN users u ON p.user_id = u.id '
        'WHERE p.id = %s',
        (post_id,)
    )
    post_data = cursor.fetchone()
    if not post_data:
        conn.close()
        flash('Post not found.')
        return redirect(url_for('board'))
    
    post = {
        "id": post_data[0],
        "title": post_data[1],
        "content": post_data[2],
        "timestamp": post_data[3],
        "username": post_data[4] or "None"
    }
    
    # ดึงความคิดเห็น
    cursor.execute(
        'SELECT c.id, c.content, c.timestamp, u.username '
        'FROM comments c LEFT JOIN users u ON c.user_id = u.id '
        'WHERE c.post_id = %s ORDER BY c.timestamp ASC',
        (post_id,)
    )
    comments = [
        {"id": row[0], "content": row[1], "timestamp": row[2], "username": row[3] or "None"}
        for row in cursor.fetchall()
    ]
    
    # จัดการการเพิ่มความคิดเห็น
    if request.method == 'POST':
        content = request.form['content']
        if not content:
            flash('Comment content is required.')
        else:
            sanitized_content = sanitize_text(content)
            cursor.execute(
                'INSERT INTO comments (post_id, user_id, content) VALUES (%s, %s, %s)',
                (post_id, session['user_id'], sanitized_content)
            )
            conn.commit()
            flash('Comment added successfully!')
            return redirect(url_for('post_details', post_id=post_id))
    
    conn.close()
    return render_template('post_details.html', post=post, comments=comments)


@app.route('/block/<int:block_index>')
@login_required
def block_details(block_index):
    blockchain = get_blockchain()
    blockchain.load_blocks_from_db()
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute('SELECT b."index", b.message, b.hash, b.previous_hash, b.timestamp, u.username, b.owner_id FROM blocks b LEFT JOIN users u ON b.owner_id = u.id WHERE b."index" = %s', (block_index,))
    block_data = cursor.fetchone()
    if block_data:
        block = {
            "index": block_data[0],
            "message": block_data[1],
            "hash": block_data[2],
            "previous_hash": block_data[3],
            "timestamp": block_data[4],
            "owner": block_data[5] or "None",
            "owner_id": block_data[6],
            "transactions": []
        }
        cursor.execute('SELECT from_address, to_address, amount FROM transactions WHERE block_index = %s', (block_index,))
        block["transactions"] = [{"from_address": tx[0], "to_address": tx[1], "amount": tx[2]} for tx in cursor.fetchall()]
        cursor.execute('SELECT u1.username, u2.username, h.timestamp, h.price FROM block_ownership_history h LEFT JOIN users u1 ON h.previous_owner_id = u1.id LEFT JOIN users u2 ON h.new_owner_id = u2.id WHERE h.block_index = %s', (block_index,))
        ownership_history = [{"previous_owner": row[0] or "None", "new_owner": row[1] or "None", "timestamp": row[2], "price": row[3]} for row in cursor.fetchall()]
        conn.close()
        is_owner = block["owner_id"] == session['user_id']
        return render_template('block_details.html', block=block, ownership_history=ownership_history, is_owner=is_owner)
    conn.close()
    flash('Block not found.')
    return redirect(url_for('blockchain_info'))

@app.route('/edit_block/<int:block_index>', methods=['GET', 'POST'])
@login_required
def edit_block(block_index):
    blockchain = get_blockchain()
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute('SELECT message, owner_id FROM blocks WHERE "index" = %s', (block_index,))
    block = cursor.fetchone()
    
    if not block:
        conn.close()
        flash('Block not found.')
        return redirect(url_for('blockchain_info'))
        
    current_message, owner_id = block
    if owner_id != session['user_id']:
        conn.close()
        flash('You can only edit blocks you own.')
        return redirect(url_for('block_details', block_index=block_index))

    if request.method == 'POST':
        new_message = request.form['new_message']
        if not new_message:
            flash('Please enter a new message.')
            conn.close()
            return redirect(url_for('edit_block', block_index=block_index))
            
        blockchain.update_block_message(block_index, new_message)
        conn.close()
        flash(f'Successfully updated message for block #{block_index}')
        return redirect(url_for('block_details', block_index=block_index))
        
    conn.close()
    return render_template('edit_block.html', block_index=block_index, current_message=current_message)

@app.route('/wallet')
@login_required
def wallet_details():
    blockchain = get_blockchain()
    puk_balance = get_puk_balance()
    wallet_address = None
    private_key = None
    balance = 0.0
    if 'user_id' in session:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT wallet_address, private_key FROM wallets WHERE user_id = %s', (session['user_id'],))
        wallet = cursor.fetchone()
        conn.close()
        if wallet:
            wallet_address, private_key = wallet
            balance = blockchain.calculate_balance()
    transactions = blockchain.view_transactions()
    return render_template('wallet.html', wallet_address=wallet_address, private_key=private_key, balance=balance, puk_balance=puk_balance, transactions=transactions)

@app.route('/timecapsule', methods=['GET', 'POST'])
@login_required
def time_capsule():
    blockchain = get_blockchain()
    if request.method == 'POST':
        message = request.form['message']
        if message:
            blockchain.add_block(message)
            return redirect(url_for('blockchain_info'))
    return render_template('timecapsule.html')

@app.route('/transactions')
@login_required
def transactions():
    blockchain = get_blockchain()
    transactions = blockchain.view_transactions()
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT SUM(amount) FROM transactions WHERE from_address = %s', ('system',))
    total_coins = cursor.fetchone()[0] or 0
    conn.close()
    return render_template('transactions.html', transactions=transactions, total_users=total_users, total_coins=total_coins)

@app.route('/details')
@login_required
def details():
    return render_template('details.html')

@app.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    blockchain = get_blockchain()
    if request.method == 'POST':
        to_address = request.form['to_address']
        try:
            amount = float(request.form['amount'])
            success, message = blockchain.transfer_coins(to_address, amount)
            if success:
                flash(message)
                return redirect(url_for('wallet_details'))
            else:
                flash(message)
        except ValueError:
            flash("Amount must be a valid number")
    balance = blockchain.calculate_balance()
    return render_template('transfer.html', balance=balance)

@app.route('/trade', methods=['GET', 'POST'])
@login_required
def trade():
    blockchain = get_blockchain()
    puk_balance = get_puk_balance()
    puk_price = update_puk_price()
    btc_price = float(requests.get(BINANCE_API_URL).json()['price'])

    if request.method == 'POST':
        action = request.form['action']
        percentage = float(request.form['percentage']) / 100
        amount_puk = puk_balance * percentage

        if action == 'buy':
            cost_usdt = amount_puk * puk_price
            if cost_usdt > puk_balance * puk_price:
                flash('Insufficient PUK balance')
            else:
                conn = psycopg2.connect(**DB_CONFIG)
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET puk_balance = puk_balance - %s WHERE id = %s', (amount_puk, session['user_id']))
                cursor.execute('INSERT INTO transactions (from_address, to_address, amount) VALUES (%s, %s, %s)', (blockchain.wallet_address, "system", amount_puk))
                conn.commit()
                conn.close()
                flash(f'Bought {amount_puk:.2f} PUK worth of BTC')

        elif action == 'sell':
            if amount_puk > puk_balance:
                flash('Insufficient PUK balance')
            else:
                conn = psycopg2.connect(**DB_CONFIG)
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET puk_balance = puk_balance + %s WHERE id = %s', (amount_puk, session['user_id']))
                cursor.execute('INSERT INTO transactions (from_address, to_address, amount) VALUES (%s, %s, %s)', ("system", blockchain.wallet_address, amount_puk))
                conn.commit()
                conn.close()
                flash(f'Sold {amount_puk:.2f} PUK')

        puk_balance = get_puk_balance()
        if puk_balance <= 0:
            flash('Your account has been liquidated!')
            return redirect(url_for('logout'))

    return render_template('trade.html', puk_balance=puk_balance, puk_price=puk_price, btc_price=btc_price)

@app.route('/trade_puk', methods=['GET', 'POST'])
@login_required
def trade_puk():
    blockchain = get_blockchain()
    puk_balance = get_puk_balance()
    puk_price = update_puk_price()

    if request.method == 'POST':
        action = request.form['action']
        percentage = float(request.form['percentage']) / 100
        
        if action == 'buy':
            cost_usdt = puk_balance * percentage
            amount_puk_to_buy = cost_usdt / puk_price
            
            if cost_usdt > puk_balance:
                flash('Insufficient PUK balance to buy.')
            else:
                conn = psycopg2.connect(**DB_CONFIG)
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET puk_balance = puk_balance - %s WHERE id = %s', 
                               (cost_usdt, session['user_id']))
                cursor.execute('INSERT INTO transactions (from_address, to_address, amount) VALUES (%s, %s, %s)', 
                               (blockchain.wallet_address, "system", amount_puk_to_buy))
                conn.commit()
                conn.close()
                flash(f'Bought {amount_puk_to_buy:.2f} PUK for {cost_usdt:.2f} USDT')

        elif action == 'sell':
            current_puk_amount = puk_balance / puk_price
            amount_puk_to_sell = current_puk_amount * percentage
            
            if amount_puk_to_sell > current_puk_amount:
                flash('Insufficient PUK balance to sell.')
            else:
                proceeds_usdt = amount_puk_to_sell * puk_price
                if proceeds_usdt > 1e18:
                    flash('Sell amount exceeds maximum allowed value.')
                else:
                    conn = psycopg2.connect(**DB_CONFIG)
                    cursor = conn.cursor()
                    cursor.execute('UPDATE users SET puk_balance = puk_balance + %s WHERE id = %s', 
                                  (proceeds_usdt, session['user_id']))
                    cursor.execute('INSERT INTO transactions (from_address, to_address, amount) VALUES (%s, %s, %s)', 
                                  ("system", blockchain.wallet_address, amount_puk_to_sell))
                    conn.commit()
                    conn.close()
                    flash(f'Sold {amount_puk_to_sell:.2f} PUK for {proceeds_usdt:.2f} USDT')

        puk_balance = get_puk_balance()
        if puk_balance < 0:
            flash('Your account balance cannot go negative!')
            return redirect(url_for('logout'))

    return render_template('trade_puk.html', puk_balance=puk_balance, puk_price=puk_price)

@app.route('/api/klines/<timeframe>')
def get_klines(timeframe):
    intervals = {'1m': '1m', '5m': '5m', '30m': '30m', '1h': '1h', '4h': '4h', '8h': '8h', '1w': '1w'}
    params = {'symbol': 'BTCUSDT', 'interval': intervals.get(timeframe, '1h'), 'limit': 100}
    response = requests.get(BINANCE_KLINES_URL, params=params)
    return jsonify(response.json())

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5111, debug=True)
