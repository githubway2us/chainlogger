import sqlite3
import hashlib
import uuid
import tkinter as tk
from tkinter import messagebox, ttk
import pyperclip  # เพิ่มไลบรารี pyperclip
from tkinter import Menu
import secrets
from blockchain import Blockchain 
from cryptography.fernet import Fernet
from datetime import datetime
import random
from tkinter import PhotoImage
import requests
from PIL import Image, ImageTk
from io import BytesIO
import datetime
import webbrowser  # เพิ่มการใช้โมดูล webbrowser เพื่อเปิด URL
import webview  # ใช้ pywebview ในการเปิดเว็บในหน้าต่างของโปรแกรมเอง

class Blockchain:
    def __init__(self, db_name, wallet_address, private_key):
        self.chain = []
        self.mempool = []  # เก็บธุรกรรมที่รอการยืนยัน
        self.wallet_address = wallet_address
        self.private_key = private_key
        self.db_name = db_name

        self.wallets = {}  # Dictionary to store wallet balances, e.g., {'address': balance}
        self.transactions = []  # List to store transactions



        self.wallet_balance = self.calculate_balance()  # คำนวณยอดเงินเมื่อเริ่มต้น
        self.reward_amount = 10  # รางวัลเมื่อปิดบล็อกสำเร็จ
        self.create_table()
        self.create_genesis_block()
        self.create_transactions_table()
        self.load_blocks_from_db()  # โหลดบล็อกจากฐานข้อมูล
        if not self.chain:  # ถ้าไม่มีบล็อกใน chain ให้สร้าง Genesis Block
            self.create_genesis_block()
                # Ensure the database is set up
        self.initialize_database()
    def initialize_database(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS blocks (
            "index" INTEGER PRIMARY KEY,
            message TEXT,
            hash TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()
        conn.close()
    def check_balance(self):
        """สมมติว่าเป็นฟังก์ชันที่ดึงยอดเงินจากฐานข้อมูลหรือระบบภายนอก"""
        return self.wallet_balance
    def calculate_balance(self):
        """คำนวณยอดเงินในกระเป๋าโดยรวมธุรกรรมทั้งหมดจากฐานข้อมูล"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT SUM(amount) FROM transactions WHERE to_address = ?
                ''', (self.wallet_address,))
                incoming_balance = cursor.fetchone()[0] or 0  # รวมยอดเงินที่ได้รับ
                cursor.execute('''
                    SELECT SUM(amount) FROM transactions WHERE from_address = ?
                ''', (self.wallet_address,))
                outgoing_balance = cursor.fetchone()[0] or 0  # รวมยอดเงินที่ส่งออก
                balance = incoming_balance - outgoing_balance
                print(f"ยอดเงินในกระเป๋าปัจจุบัน: {balance}")
                return balance
        except sqlite3.Error as e:
            print(f"เกิดข้อผิดพลาดในการคำนวณยอดเงิน: {e}")
            return 0
    def create_transactions_table(self):
        """สร้างตารางธุรกรรมในฐานข้อมูลหากยังไม่มี"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                timestamp DATETIME NOT NULL,
                                from_address TEXT NOT NULL,
                                to_address TEXT NOT NULL,
                                amount REAL NOT NULL,
                                coin_name TEXT
                            )''')
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            print(f"Error creating transactions table: {e}")
    def create_table(self):
        """สร้างตารางในฐานข้อมูลหากยังไม่มี"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                # สร้างตาราง blocks ถ้ายังไม่มี
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS blocks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        "index" INTEGER UNIQUE NOT NULL,
                        message TEXT NOT NULL,
                        hash TEXT NOT NULL,
                        timestamp TEXT NOT NULL
                    )
                ''')
                # สร้างตาราง transactions ถ้ายังไม่มี
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        from_address TEXT NOT NULL,
                        to_address TEXT NOT NULL,
                        amount REAL NOT NULL,
                        block_index INTEGER,
                        FOREIGN KEY (block_index) REFERENCES blocks("index")
                    )
                ''')
                # ตรวจสอบและเพิ่มคอลัมน์ที่ขาดในตาราง transactions
                cursor.execute("PRAGMA table_info(transactions)")
                existing_columns = [col[1] for col in cursor.fetchall()]
                required_columns = {
                    "block_index": "INTEGER"
                }
                for column, column_type in required_columns.items():
                    if column not in existing_columns:
                        cursor.execute(f"ALTER TABLE transactions ADD COLUMN {column} {column_type}")
                        print(f"เพิ่มคอลัมน์ {column} ในตาราง transactions สำเร็จ.")
                print("ตรวจสอบและสร้างตารางฐานข้อมูลสำเร็จ.")
        except sqlite3.Error as e:
            print(f"เกิดข้อผิดพลาดในการสร้างตารางฐานข้อมูล: {e}")
    def create_wallet_table(self):
        """Create a wallet table if it doesn't exist."""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS wallets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        wallet_address TEXT UNIQUE NOT NULL,
                        private_key TEXT NOT NULL,
                        balance REAL DEFAULT 0.0
                    )
                ''')
                print("Wallet table checked/created successfully.")
        except sqlite3.Error as e:
            print(f"Error creating wallet table: {e}")
    def create_genesis_block(self):
        """สร้างบล็อกแรก (Genesis Block)"""
        if not self.chain:
            # เนื้อหาข้อความสำหรับ Genesis Block
            genesis_message = (
                "ปฐมกาล "
                "โปรแกรมนี้ถูกพัฒนาขึ้นเพื่อสร้างระบบบันทึกข้อความที่มีความปลอดภัยสูง "
                "โดยอาศัยการจัดเก็บข้อมูลบนบล็อกเชน (Blockchain) ซึ่งเป็นเทคโนโลยีที่เน้นความโปร่งใสและความปลอดภัยของข้อมูล "
                "ระบบนี้ถูกออกแบบมาเพื่อการบันทึกข้อความในรูปแบบที่ไม่สามารถแก้ไขได้ และข้อมูลทุกชิ้นจะถูกจัดเรียงตามลำดับบล็อก (Block) "
                "ที่มีความเชื่อมโยงกันอย่างชัดเจน\n\n"
                "ฟีเจอร์เด่นของโปรแกรม:\n"
                "1. การบันทึกข้อความแบบถาวร: ข้อมูลจะถูกจัดเก็บในบล็อกเชนแบบไม่สามารถแก้ไขได้\n"
                "2. ความปลอดภัยสูง: ข้อมูลถูกเข้ารหัสและป้องกันการแก้ไขโดยไม่ได้รับอนุญาต\n"
                "3. การตรวจสอบที่โปร่งใส: ข้อมูลสามารถตรวจสอบได้ง่ายและโปร่งใส\n"
                "4. จัดเรียงตามลำดับบล็อก: ง่ายต่อการค้นหาและตรวจสอบข้อมูลในภายหลัง\n\n"
                "ประโยชน์ของโปรแกรม:\n"
                "- เหมาะสำหรับการใช้งานที่ต้องการความโปร่งใส เช่น การบันทึกหลักฐานสำคัญหรือเอกสารสำคัญ.\n"
                "- ลดความเสี่ยงจากการแก้ไขหรือปลอมแปลงข้อมูล.\n"
                "- ส่งเสริมความมั่นใจในความถูกต้องของข้อมูล.\n\n"
                "โปรแกรมนี้ผสมผสานระหว่างความเรียบง่ายและความปลอดภัยสูงเพื่อรองรับการใช้งานที่เชื่อถือได้.\n\n"
                "------------------------\n"
                "ผู้พัฒนา #คัมภีร์สายกระบี่คริปโต\n"
                "------------------------\n"
            )
            # สร้าง Genesis Block
            genesis_block = {
                "index": 0,
                "message": genesis_message,
                "transactions": [],  # Genesis Block ไม่มีธุรกรรม
                "hash": "ปฐมกาล"
            }
            # เพิ่ม Genesis Block ลงในบล็อกเชน
            self.chain.append(genesis_block)
            # บันทึก Genesis Block ลงฐานข้อมูล
            self.save_block_to_db(
                index=genesis_block["index"],
                message=genesis_block["message"],
                block_hash=genesis_block["hash"],
                transactions=genesis_block["transactions"]  # ส่งข้อมูลธุรกรรม
            )
            print("Genesis Block ถูกสร้างและบันทึกเรียบร้อยแล้ว!")
    def add_block(self, message, transactions=None):
        """เพิ่มบล็อกใหม่พร้อมธุรกรรม"""
        last_block = self.chain[-1] if self.chain else {"index": -1, "hash": "0"}
        new_index = last_block["index"] + 1
        new_hash = self.create_hash(new_index, message)
        # เพิ่มธุรกรรมเข้าไปในบล็อก
        block_transactions = transactions if transactions else []
        # สร้างบล็อกใหม่
        new_block = {
            "index": new_index,
            "message": message,
            "transactions": block_transactions,
            "hash": new_hash
        }
        # เพิ่มบล็อกใหม่ลงใน chain
        self.chain.append(new_block)
        # บันทึกบล็อกใหม่ลงในฐานข้อมูล
        self.save_block_to_db(new_block["index"], new_block["message"], new_block["hash"], block_transactions)
        # ให้รางวัลเมื่อเพิ่มบล็อกสำเร็จ
        self.give_reward()
    def create_hash(self, index, message):
        """สร้างแฮชจากข้อความและดัชนี"""
        return hashlib.sha256(f"{index}_{message}".encode('utf-8')).hexdigest()
    def save_block_to_db(self, index, message, block_hash, transactions):
        """บันทึกบล็อกพร้อมธุรกรรมลงในฐานข้อมูล"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                # ตรวจสอบว่า index ซ้ำหรือไม่
                cursor.execute('SELECT * FROM blocks WHERE "index" = ?', (index,))
                if cursor.fetchone():
                    print(f"บล็อกที่มี index {index} อยู่แล้วในฐานข้อมูล.")
                else:
                    # เพิ่มการบันทึกบล็อก
                    cursor.execute('''
                        INSERT INTO blocks ("index", message, hash, timestamp)
                        VALUES (?, ?, ?, datetime("now"))
                    ''', (index, message, block_hash))
                    # บันทึกธุรกรรมทั้งหมดของบล็อก
                    for transaction in transactions:
                        cursor.execute('''
                            INSERT INTO transactions (timestamp, from_address, to_address, amount, block_index)
                            VALUES (datetime("now"), ?, ?, ?, ?)
                        ''', (transaction["from_address"], transaction["to_address"], transaction["amount"], index))
                    conn.commit()
                    print(f"บล็อกที่ {index} ถูกบันทึกเรียบร้อยพร้อมธุรกรรม.")
        except sqlite3.Error as e:
            print(f"เกิดข้อผิดพลาดในการบันทึกบล็อกลงฐานข้อมูล: {e}")
    def save_transaction_to_db(self, from_address, to_address, amount, block_index=None, timestamp=None):
        """บันทึกข้อมูลธุรกรรมลงในฐานข้อมูล"""
        try:
            # ตรวจสอบข้อมูลก่อนบันทึก
            if not from_address or not to_address:
                raise ValueError("ที่อยู่ต้นทางและปลายทางไม่ควรว่างเปล่า")
            if not isinstance(amount, (int, float)) or amount <= 0:
                raise ValueError("จำนวนเงินต้องเป็นตัวเลขบวก")
            
            # ใช้ timestamp ปัจจุบันหากไม่มีการระบุ
            if not timestamp:
                timestamp = "datetime('now')"
            else:
                timestamp = f"'{timestamp}'"
            
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    INSERT INTO transactions (timestamp, from_address, to_address, amount, block_index)
                    VALUES ({timestamp}, ?, ?, ?, ?)
                ''', (from_address, to_address, amount, block_index))
                conn.commit()
                print("บันทึกธุรกรรมสำเร็จ")
        except ValueError as ve:
            print(f"Validation Error: {ve}")
        except sqlite3.Error as e:
            print(f"Database Error: {e}")
            # อาจเพิ่มการบันทึกข้อผิดพลาดลงไฟล์ log
        except Exception as e:
            print(f"Unexpected Error: {e}")
    def give_reward(self):
        """Award the block creation reward to the wallet."""
        try:
            # Increment the wallet balance with the reward
            self.wallet_balance += self.reward_amount
            # Record the reward transaction in the database
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO transactions (timestamp, from_address, to_address, amount)
                    VALUES (datetime("now"), ?, ?, ?)
                ''', ("system", self.wallet_address, self.reward_amount))
                conn.commit()
            print(f"Reward of {self.reward_amount} added to wallet.")
        except sqlite3.Error as e:
            print(f"Error awarding reward: {e}")
    def update_wallet_balance_in_db(self):
        """อัพเดตยอดเงินในฐานข้อมูล"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE wallet SET balance = ? WHERE address = ?', (self.wallet_balance, self.wallet_address))
                conn.commit()
                print(f"อัพเดตยอดเงินในฐานข้อมูล: {self.wallet_balance}")
        except sqlite3.Error as e:
            print(f"เกิดข้อผิดพลาดในการอัพเดตยอดเงินในฐานข้อมูล: {e}")
    def load_blocks_from_db(self):
        """โหลดบล็อกจากฐานข้อมูล"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('SELECT "index", message, hash FROM blocks')
            rows = cursor.fetchall()
            for row in rows:
                block = {"index": row[0], "message": row[1], "hash": row[2], "transactions": []}
                # Load transactions for this block
                cursor.execute('SELECT * FROM transactions WHERE block_index = ?', (block["index"],))
                transactions = cursor.fetchall()
                for tx in transactions:
                    block["transactions"].append({
                        "timestamp": tx[1],
                        "from_address": tx[2],
                        "to_address": tx[3],
                        "amount": tx[4]
                    })
                self.chain.append(block)
            conn.close()
            print("บล็อกทั้งหมดถูกโหลดจากฐานข้อมูลแล้ว!")
        except sqlite3.Error as e:
            print(f"เกิดข้อผิดพลาดในการโหลดบล็อกจากฐานข้อมูล: {e}")
    def generate_new_wallet_address(self):
        """สร้างที่อยู่กระเป๋าใหม่โดยใช้ UUID"""
        return str(uuid.uuid4())  # สร้างที่อยู่กระเป๋าใหม่แบบสุ่ม
    def generate_private_key(self):
        """สร้างคีย์ส่วนตัวโดยการแฮชที่อยู่กระเป๋า"""
        return hashlib.sha256(self.wallet_address.encode('utf-8')).hexdigest()
    def view_transactions(self):
        """ดูการทำธุรกรรมทั้งหมดในฐานข้อมูล"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id, timestamp, from_address, to_address, amount FROM transactions')
                transactions = cursor.fetchall()
                return transactions
        except sqlite3.Error as e:
            print(f"เกิดข้อผิดพลาดในการดึงข้อมูลธุรกรรม: {e}")
            return []

class WalletApp:

    def __init__(self, root, db_name="blockchain.db", wallet_address=None, private_key=None):
        self.root = root
        self.root.title("ChainLogger #PUKUMPee V.4.0.2")
        self.root.geometry("650x880")
        self.root.resizable(False, False)  # Disable resizing of the window
        self.db_name = db_name
        self.wallet_address = wallet_address
        self.private_key = private_key
        self.wallets = {}  # Store wallet data (address -> balance)
        self.transactions = []  # Store transactions that occur
        self.blockchain = Blockchain(db_name, wallet_address, private_key)

        self.wallet_info = {"address": wallet_address, "balance": 0, "private_key": private_key}

        # Create the database connection and cursor
        self.conn = sqlite3.connect('blockchain.db')  # Adjust the database name as needed
        self.cursor = self.conn.cursor()
        # Apply modern font and styles
        self.font = ("Helvetica Neue", 14)
        self.button_font = ("Helvetica Neue", 12, 'bold')

        # Modern background color
        self.root.config(bg="#01899e")

        self.create_wallet_table()  # Ensure the table exists
        self.wallet_info = self.load_or_create_wallet()

        if "address" in self.wallet_info and "private_key" in self.wallet_info:
            self.wallet_address = self.wallet_info["address"]
            self.private_key = self.wallet_info["private_key"]
        else:
            print("Error: Wallet information missing.")
            return
        # Load the image to be used as the background
 # URL of the image to use as the background
        image_url = "https://wallpapers.com/images/hd/best-gaming-background-k0k6l23gaua1q821.jpg"  # Replace with your image URL
        self.background_image = self.load_image_from_url(image_url)

        # Game tab
        self.game_tab = tk.Frame(self.root)
        self.game_tab.pack(fill="both", expand=True, padx=10, pady=10)

        # Set the background image for the game_tab
        self.set_game_tab_background()

        self.blockchain = Blockchain(self.db_name, self.wallet_address, self.private_key)
        self.create_ui()  # Initialize UI after setup
    def create_ui(self):
            """Create the user interface for the wallet."""
            self.main_frame = tk.Frame(self.root, bg="#f4f4f9")
            self.main_frame.pack(fill=tk.BOTH, expand=True)      
            
            # Create tabs
            self.tab_control = ttk.Notebook(self.main_frame)
            
            # Tabs for additional functionality
            self.blockchain_tab = ttk.Frame(self.tab_control)
            self.wallet_tab = ttk.Frame(self.tab_control)
            self.message_tab = ttk.Frame(self.tab_control)
            self.transactions_tab = ttk.Frame(self.tab_control)
            self.detail_tab = ttk.Frame(self.tab_control)

            self.tab_control.add(self.blockchain_tab, text="Blockchain Info")
            self.tab_control.add(self.wallet_tab, text="Wallet Details")
            self.tab_control.add(self.message_tab, text="Time Capsule Record Text")
            self.tab_control.add(self.transactions_tab, text="Transactions")
            self.tab_control.add(self.detail_tab, text="Detail")

            self.tab_control.pack(expand=1, fill="both")

            # Create the content for each tab
            self.create_blockchain_tab()
            self.create_wallet_tab()
            self.create_message_tab()
            self.create_transactions_tab()
            self.create_detail_tab()
    def create_blockchain_tab(self):
        # สร้างป้าย "Time Capsule"
        self.time_capsule_label = tk.Label(self.blockchain_tab, text="Time Capsule Feature: Detailed Description", font=("Helvetica", 16, "bold"))
        self.time_capsule_label.pack(pady=10)  # เพิ่มป้ายที่ด้านบน

        # Create a Listbox to display blockchain data
        self.blockchain_listbox = tk.Listbox(self.blockchain_tab, height=10, width=300)
        self.blockchain_listbox.pack(pady=10)

        # Fetch and display the first two lines of blockchain data
        self.update_blockchain_list()


        # Create a frame to contain the buttons and arrange them in a single row
        button_frame = tk.Frame(self.blockchain_tab)
        button_frame.pack(pady=10)

        # Update button
        self.update_button = tk.Button(button_frame, text="อัพเดตข้อมูล", command=self.update_blockchain_list)
        self.update_button.pack(side=tk.LEFT, padx=5)

        # New Time Capsule Upload button
        self.time_capsule_button = tk.Button(button_frame, text="อัพโหลดแคปซูล", command=self.open_time_capsule)
        self.time_capsule_button.pack(side=tk.LEFT, padx=5)

        # Dashboard button
        self.dashboard_button = tk.Button(button_frame, text="เปิดรายงานการตรวจสอบฐานข้อมูล", command=self.create_dashboard)
        self.dashboard_button.pack(side=tk.LEFT, padx=5)
        
        # Bind a click event on the Listbox to show block details
        self.blockchain_listbox.bind("<ButtonRelease-1>", self.show_block_details)
    def open_time_capsule(self):
        # เปิดเว็บที่ 127.0.0.1:3000 ในหน้าต่างใหม่ของโปรแกรม ขนาด 700x800
        webview.create_window('Upload :: Time Capsule', 'http://127.0.0.1', width=450, height=800)  # กำหนดขนาด
        webview.start()  # เริ่มการแสดงผล
    def search_block(self):
            search_query = self.search_entry.get().lower()
            self.blockchain_listbox.delete(0, tk.END)

            try:
                conn = sqlite3.connect(self.blockchain.db_name)
                cursor = conn.cursor()
                cursor.execute('SELECT "index", message, hash, timestamp FROM blocks')
                rows = cursor.fetchall()
                for row in rows:
                    if search_query in row[1].lower():  # Check if search query is in the message
                        message = row[1] if len(row[1]) <= 50 else row[1][:50] + "..."
                        display_text = f"Index: {row[0]} | #: {message} | Time: {row[3]}  | Hash: {row[2]}"
                        self.blockchain_listbox.insert(tk.END, display_text)
                conn.close()
            except sqlite3.Error as e:
                print(f"Error searching block: {e}")
    def create_dashboard(self):
        # ฟังก์ชันตรวจสอบฐานข้อมูล
        def check_block_integrity(db_name):
            result = []
            modified_count = 0
            missing_blocks = []  # สำหรับเก็บบล็อกที่หายไป
            conn = None
            try:
                conn = sqlite3.connect(db_name)
                cursor = conn.cursor()

                cursor.execute('SELECT "index", message, hash FROM blocks')
                rows = cursor.fetchall()

                # ตรวจสอบลำดับของบล็อก (การขาดหายไปของบล็อก)
                existing_indexes = [row[0] for row in rows]
                expected_indexes = range(1, max(existing_indexes) + 1)  # เริ่มจากบล็อกที่ 1
                missing_indexes = set(expected_indexes) - set(existing_indexes)

                if missing_indexes:
                    missing_blocks = [f"บล็อกที่ {index} หายไป" for index in missing_indexes]
                    result.extend(missing_blocks)

                # ตรวจสอบแต่ละบล็อกในฐานข้อมูล
                for row in rows:
                    block_index = row[0]
                    message = row[1]
                    original_hash = row[2]

                    # คำนวณแฮชใหม่จากข้อมูลของบล็อก
                    current_hash = hashlib.sha256(f"{block_index}_{message}".encode('utf-8')).hexdigest()

                    # เปรียบเทียบแฮชเดิมกับแฮชใหม่
                    if current_hash != original_hash:
                        modified_count += 1
                        result.append(f"บล็อกที่ {block_index} ถูกแก้ไข! แฮชเดิม: {original_hash}, แฮชใหม่: {current_hash}")
                    else:
                        result.append(f"บล็อกที่ {block_index} ถูกต้อง")

                if not result and not missing_blocks:
                    result.append("ข้อมูลในบล็อกทั้งหมดถูกต้อง ไม่มีการแก้ไข หรือบล็อกที่หายไป")

            except sqlite3.Error as e:
                result.append(f"เกิดข้อผิดพลาดในการตรวจสอบบล็อก: {e}")
            
            finally:
                if conn:
                    conn.close()  # Ensure connection is closed

            return result, modified_count, len(missing_blocks)

        # ตรวจสอบข้อมูลจากฐานข้อมูล
        integrity_report, modified_count, missing_count = check_block_integrity("blockchain.db")

        # สร้างหน้าต่าง Dashboard ใหม่
        dashboard_window = tk.Toplevel()  # หน้าต่างใหม่
        dashboard_window.title("Blockchain Integrity Dashboard")

        # ข้อความรายงาน
        report_text = "\n".join(integrity_report)

        # สร้าง Text widget เพื่อแสดงผล
        text_widget = tk.Text(dashboard_window, height=20, width=80)
        text_widget.insert(tk.END, report_text)
        text_widget.config(state=tk.DISABLED)  # ป้องกันไม่ให้แก้ไข
        text_widget.pack(pady=20)

        # แสดงจำนวนบล็อกที่แฮชถูกแก้ไข
        modified_label = tk.Label(dashboard_window, text=f"จำนวนบล็อกที่แฮชถูกแก้ไข: {modified_count}")
        modified_label.pack(pady=10)

        # แสดงจำนวนบล็อกที่หายไป
        missing_label = tk.Label(dashboard_window, text=f"จำนวนบล็อกที่หายไป: {missing_count}")
        missing_label.pack(pady=10)

        # เพิ่มปุ่ม Refresh
        def refresh():
            # รีเฟรชข้อมูลโดยการตรวจสอบใหม่
            new_report, new_modified_count, new_missing_count = check_block_integrity("blockchain.db")
            text_widget.config(state=tk.NORMAL)
            text_widget.delete(1.0, tk.END)
            text_widget.insert(tk.END, "\n".join(new_report))
            text_widget.config(state=tk.DISABLED)
            
            # แสดงจำนวนบล็อกที่แฮชถูกแก้ไขและหายไป
            modified_label.config(text=f"จำนวนบล็อกที่แฮชถูกแก้ไข: {new_modified_count}")
            missing_label.config(text=f"จำนวนบล็อกที่หายไป: {new_missing_count}")

        refresh_button = tk.Button(dashboard_window, text="Refresh", command=refresh)
        refresh_button.pack(pady=10)
    def show_block_details(self, event):
        """แสดงข้อความทั้งหมดของบล็อกที่เลือกในหน้าต่างใหม่"""
        selected_index = self.blockchain_listbox.curselection()  # หาว่าคลิกที่รายการไหน
        if selected_index:
            index = selected_index[0]  # ดึง index ของรายการที่เลือก
            try:
                conn = sqlite3.connect(self.blockchain.db_name)  # Use blockchain.db_name
                cursor = conn.cursor()
                cursor.execute('SELECT message, timestamp, hash FROM blocks WHERE "index" = ?', (index,))
                row = cursor.fetchone()
                conn.close()

                if row:
                    block_message, timestamp, block_hash = row
                    self.open_new_window(block_message, timestamp, block_hash)
            except sqlite3.Error as e:
                print(f"Error fetching block details: {e}")
    def open_new_window(self, block_message, timestamp, block_hash):
        """สร้างหน้าต่างใหม่เพื่อแสดงข้อความทั้งหมด พร้อมสีสัน"""
        new_window = tk.Toplevel(self.root)
        new_window.title("รายละเอียดบล็อก")
        new_window.geometry("500x650")

        # เปลี่ยนสีพื้นหลังของหน้าต่าง
        new_window.configure(bg="#2c3e50")  # สีพื้นหลังเข้มเพื่อความสบายตา

        # เพิ่ม Scrollbar
        scrollbar = tk.Scrollbar(new_window, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # เพิ่ม Text Widget
        text_widget = tk.Text(new_window, wrap=tk.WORD, yscrollcommand=scrollbar.set, bg="#ecf0f1", fg="#34495e", font=("Helvetica", 12))
        text_widget.pack(expand=True, fill=tk.BOTH)

        # ตั้ง Scrollbar ให้ควบคุม Text Widget
        scrollbar.config(command=text_widget.yview)

        # เพิ่มเนื้อหาลงใน Text Widget
        text_widget.insert(tk.END, f"Timestamp: {timestamp}\n", "header")
        text_widget.insert(tk.END, f"------------------------------\n", "header")
        text_widget.insert(tk.END, f"Block Hash: {block_hash}\n", "header")
        text_widget.insert(tk.END, f"------------------------------\n", "header")
        text_widget.insert(tk.END, "Message:\n", "header")
        text_widget.insert(tk.END, f"{block_message}\n", "body")
        text_widget.insert(tk.END, f"------------------------------\n", "header")
        text_widget.insert(tk.END, f"Timestamp:  {timestamp}\n")
        text_widget.insert(tk.END, f"If you have any further questions, feel free to ask directly here! \n@way2us@hotmail.com\n")

        # กำหนด Style สำหรับข้อความ
        text_widget.tag_configure("header", font=("Helvetica", 14, "bold"), foreground="#2c3e50")
        text_widget.tag_configure("body", font=("Helvetica", 12), foreground="#34495e")

        # ทำให้ Text Widget เป็นแบบ Read-Only
        text_widget.config(state=tk.DISABLED)
    def update_blockchain_list(self):
        """อัปเดตรายการบล็อกเชนใน Listbox"""
        self.blockchain_listbox.delete(0, tk.END)  # Clear the current listbox

        try:
            # Connect to the database
            conn = sqlite3.connect(self.blockchain.db_name)
            cursor = conn.cursor()

            # Fetch all rows from the blocks table (index, message, hash, timestamp)
            cursor.execute('SELECT "index", message, hash, timestamp FROM blocks')
            rows = cursor.fetchall()

            # Insert each row into the Listbox
            for row in rows:
                # Displaying the block index, hash, timestamp, and message (truncated for readability)
                message = row[1] if len(row[1]) <= 50 else row[1][:50] + "..."  # Truncate the message if it's too long
                display_text = f"Index: {row[0]} | #: {message} | Time: {row[3]}  | Hash: {row[2]} "
                self.blockchain_listbox.insert(tk.END, display_text)

            # Close the database connection
            conn.close()

        except sqlite3.Error as e:
            print(f"Error fetching blockchain data: {e}")
    def create_wallet_table(self):
        """Create the wallet table if it doesn't exist."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Create the wallet table if it doesn't already exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_address TEXT,
            balance REAL,
            private_key TEXT
        );
        ''')

        # Commit the changes and close the connection
        conn.commit()
        conn.close()
    def create_wallet_tab(self):
        """Create the wallet tab in the UI."""
        # Ensure wallet_info has default values if no wallet is selected
        if not hasattr(self, 'wallet_info'):
            self.wallet_info = {"address": "Unknown", "balance": 0, "private_key": "Not Available"}

        # Create wallet UI components
        wallet_label = tk.Label(self.wallet_tab, text="Wallet Address: ", font=("Arial", 12))
        wallet_label.pack(pady=5)

        # Create the wallet address label
        self.wallet_address_label = tk.Label(self.wallet_tab, text=self.wallet_info["address"], font=("Arial", 12))
        self.wallet_address_label.pack(pady=5)

        # Create the wallet balance label
        self.wallet_balance_label = tk.Label(self.wallet_tab, text=f"Balance: {self.wallet_info['balance']} PUK", font=("Arial", 12))
        self.wallet_balance_label.pack(pady=5)

        # Frame for wallet details (private key display)
        self.info_frame = tk.Frame(self.wallet_tab, bg="#ffffff", bd=2, relief="solid")
        self.info_frame.pack(fill="x", padx=20, pady=20)

        # Private key label
        self.private_key_label = tk.Label(
            self.info_frame,
            text=f"Private Key: {self.wallet_info['private_key']}",
            font=("Helvetica", 8),
            bg="#ffffff",
            fg="#555"
        )
        self.private_key_label.pack(pady=5)

        # Buttons Frame
        self.button_frame = tk.Frame(self.wallet_tab, bg="#f4f4f9")
        self.button_frame.pack(fill="x", padx=20, pady=20)

        # Wallet action buttons
        ttk.Button(self.button_frame, text="🔄 Refresh Balance", command=self.refresh_balance).grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        ttk.Button(self.button_frame, text="💸 Copy Address", command=self.copy_wallet_address).grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        ttk.Button(self.button_frame, text="➕ Create New Wallet", command=self.create_new_wallet).grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        # เพิ่มปุ่มโอนเหรียญ
        ttk.Button(self.button_frame, text="💸 Transfer Funds", command=self.transfer_funds).grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        
        ttk.Button(self.button_frame, text="📋 Copy Private Key", command=self.copy_private_key).grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        # New Button to Select Existing Wallet
        ttk.Button(self.button_frame, text="🔑 Select Existing Wallet", command=self.select_existing_wallet).grid(row=2, column=0, padx=10, pady=10, sticky="ew")

        # Grid configuration for buttons
        self.button_frame.grid_columnconfigure(0, weight=1)
        self.button_frame.grid_columnconfigure(1, weight=1)

        # Initial update of wallet info
        self.update_wallet_info()
    def load_image_from_url(self, url):
        """Downloads an image from a URL and returns a Tkinter-compatible image."""
        # Fetch the image from the URL
        response = requests.get(url)
        img_data = response.content

        # Convert the image to a format Tkinter can handle
        img = Image.open(BytesIO(img_data))
        img = img.resize((self.root.winfo_width(), self.root.winfo_height()), Image.Resampling.LANCZOS)  # Resize to window size
        tk_img = ImageTk.PhotoImage(img)
        
        return tk_img
    def update_transaction_table_schema(db_name="blockchain.db"):
        """Ensure the transactions table has the correct schema, including a default timestamp."""
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        # Ensure the transactions table includes timestamp with a default value
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_address TEXT NOT NULL,
            to_address TEXT NOT NULL,
            amount REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        ''')

        conn.commit()
        conn.close()
    # Call the function when initializing the app
    update_transaction_table_schema()
    # ลงทะเบียน adapter สำหรับจัดการ datetime
    sqlite3.register_adapter(datetime.datetime, lambda dt: dt.isoformat())
    def record_transaction(self, from_address, to_address, amount):
        """บันทึกการทำธุรกรรมลงในฐานข้อมูล."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # หามาตรฐานเวลาปัจจุบัน
        timestamp = datetime.datetime.now()

        # บันทึกรายละเอียดธุรกรรมลงในฐานข้อมูล รวมถึง timestamp
        cursor.execute('''
        INSERT INTO transactions (from_address, to_address, amount, timestamp)
        VALUES (?, ?, ?, ?)
        ''', (from_address, to_address, amount, timestamp))

        conn.commit()
        conn.close()

    def set_game_tab_background(self):
        # Set background image for the game_tab
        background_label = tk.Label(self.game_tab, image=self.background_image)
        background_label.place(relwidth=1, relheight=1)  # Set the image to cover the entire frame

        # Additional game UI elements can go here
        self.create_game_tab()

    def create_game_tab(self):
        """Create Minesweeper Game."""
        self.grid_size = 12
        self.num_mines = 50
        self.difficulty = "medium"  # ความยาก (ง่าย, ปานกลาง, ยาก)
        self.buttons = {}
        self.mine_locations = set()
        self.marked_mines = set()  # เซ็ตเก็บตำแหน่งที่มาร์คระเบิด
        self.revealed = set()
        self.score = 0  # คะแนนเริ่มต้น
        
    # ปรับคะแนนตามความยาก
        self.difficulty_multiplier = {"easy": 1, "medium": 2, "hard": 3}
        self.score_label = tk.Label(self.game_tab, text=f"Score: {self.score}", font=("Arial", 20))
        self.score_label.grid(row=self.grid_size + 1, column=0, columnspan=self.grid_size)
        
        self.click_count = 0

        # สร้างกริดของ Minesweeper
        for row in range(self.grid_size):
            for col in range(self.grid_size):
                button = tk.Button(self.game_tab, width=3, height=1, 
                                command=lambda r=row, c=col: self.reveal_cell(r, c))
                button.bind("<Button-3>", lambda event, r=row, c=col: self.mark_mine(r, c))  # คลิกขวา
                button.grid(row=row + 1, column=col, padx=1, pady=1)
                self.buttons[(row, col)] = button
        # Create a button to transfer score to the wallet
        self.transfer_button = tk.Button(self.game_tab, text="Transfer Score to Wallet", command=self.transfer_score_to_wallet)
        self.transfer_button.grid(row=self.grid_size + 2, column=1, columnspan=self.grid_size)
        self.place_mines()

        # ตัวแปรเก็บป้ายเกมโอเวอร์และปุ่มใหม่
        self.game_over_label = None
        self.new_game_button = None
        self.transfer_button = None

    def mark_mine(self, row, col):
        """Mark or unmark a cell as a suspected mine."""
        if (row, col) in self.revealed:
            return  # ไม่อนุญาตให้มาร์คเซลล์ที่เปิดเผยแล้ว

        button = self.buttons[(row, col)]
        if (row, col) in self.marked_mines:
            # ยกเลิกมาร์คระเบิด
            self.marked_mines.remove((row, col))
            button.config(text="", bg="lightgray")
        else:
            # มาร์คเป็นระเบิด
            self.marked_mines.add((row, col))
            button.config(text="🚩", bg="yellow")

    def place_mines(self):
        """Randomly place mines on the grid."""
        while len(self.mine_locations) < self.num_mines:
            row = random.randint(0, self.grid_size - 1)
            col = random.randint(0, self.grid_size - 1)
            self.mine_locations.add((row, col))

    def reveal_cell(self, row, col):
        """Reveal the contents of a cell."""
        if (row, col) in self.revealed:
            return

        self.revealed.add((row, col))

        # If it's a mine, end the game
        if (row, col) in self.mine_locations:
            self.buttons[(row, col)].config(text="💥", bg="red")
            self.game_over("Game Over! Let's play again.")
            return

        adjacent_mines = self.count_adjacent_mines(row, col)
        if adjacent_mines == 0:
            self.buttons[(row, col)].config(text="", bg="lightgreen")
            self.auto_reveal_adjacent(row, col)
        else:
            self.buttons[(row, col)].config(text=str(adjacent_mines), bg="lightblue")
        
        # Update score based on difficulty
        self.update_score()

    def count_adjacent_mines(self, row, col):
        """Count how many mines are adjacent to a given cell."""
        adjacent_cells = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        count = 0
        for dr, dc in adjacent_cells:
            if (row + dr, col + dc) in self.mine_locations:
                count += 1
        return count

    def auto_reveal_adjacent(self, row, col):
        """Automatically reveal adjacent cells if there are no nearby mines."""
        adjacent_cells = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        for dr, dc in adjacent_cells:
            r, c = row + dr, col + dc
            if 0 <= r < self.grid_size and 0 <= c < self.grid_size and (r, c) not in self.revealed:
                self.reveal_cell(r, c)

    def update_score(self):
        """Update the score based on the click count and difficulty level."""
        self.click_count += 1
        points = 0.3 * (1.2 ** (self.click_count - 1)) * self.difficulty_multiplier[self.difficulty]
        self.score += points
        self.score_label.config(text=f"Score: {self.score}")

    def update_countdown(self, count):
            """Update the countdown display."""
            if self.countdown_label:
                self.countdown_label.config(text=f"Begin : {count}")
            if count > 0:
                # ถ้ายังไม่ถึง 0 ให้เรียกฟังก์ชันตัวเองใหม่
                self.game_tab.after(1000, self.update_countdown, count - 1)
            else:
                # เมื่อหมดเวลานับถอยหลัง 0 เริ่มเกมใหม่
                self.restart_game()

    def game_over(self, message):
        """Display game over message and restart the game with countdown."""
        # Hide any existing game over message and buttons
        if self.game_over_label:
            self.game_over_label.grid_forget()
        if self.new_game_button:
            self.new_game_button.grid_forget()
        if self.transfer_button:
            self.transfer_button.grid_forget()

        # Add the "Game Over" message
        self.game_over_label = tk.Label(self.game_tab, text=message, font=("Arial", 14), fg="red")
        self.game_over_label.grid(row=self.grid_size + 1, column=0, columnspan=self.grid_size)

         #Create a button to transfer score to the wallet
        self.transfer_button = tk.Button(self.game_tab, text="Herry Up..!!!", command=self.transfer_score_to_wallet)
        self.transfer_button.grid(row=self.grid_size + 3, column=1, columnspan=self.grid_size)

        # Display countdown
        self.countdown_label = tk.Label(self.game_tab, text="Starting new game in: 3", font=("Arial", 14), fg="blue")
        self.countdown_label.grid(row=self.grid_size + 1, column=9, columnspan=self.grid_size)

        # Start countdown from 3 seconds
        self.update_countdown(3)

    def restart_game(self):
        """Restart the game."""
        # Reset the game state
        self.score = 0
        self.score_label.config(text=f"Score: {self.score}")
        self.click_count = 0
        self.mine_locations.clear()
        self.revealed.clear()
        self.place_mines()

        # Clear the "Game Over" message and buttons
        if self.game_over_label:
            self.game_over_label.grid_forget()
        if self.new_game_button:
            self.new_game_button.grid_forget()
        if self.transfer_button:
            self.transfer_button.grid_forget()

        # Re-enable the game buttons
        for button in self.buttons.values():
            button.config(state="normal")
                # Reset buttons' state and appearance
        for (row, col), button in self.buttons.items():
            button.config(state="normal", text="", bg="lightgray")

    def transfer_score_to_wallet(self):
            """Transfer score to the wallet and record the transaction in the database."""
            if not self.wallet_address:
                messagebox.showerror("Error", "No wallet address found.")
                return

            # Open a new window to input transfer details
            transfer_window = tk.Toplevel(self.root)
            transfer_window.title("Transfer Score to Wallet")
            transfer_window.geometry("300x380")

            # Display current score and wallet address
            tk.Label(transfer_window, text=f"Your Wallet Address: {self.wallet_address}").pack(pady=10)
            tk.Label(transfer_window, text=f"Current Score: {self.score}").pack(pady=10)

            # Input field for transfer amount
            tk.Label(transfer_window, text="Amount to Transfer:").pack(pady=5)
            amount_entry = tk.Entry(transfer_window, font=("Arial", 12))
            amount_entry.pack(pady=10)

            # Button to set amount to the full score
            def set_all_amount():
                amount_entry.delete(0, tk.END)  # Clear current value
                amount_entry.insert(0, str(self.score))  # Set amount to the full score

            all_button = tk.Button(transfer_window, text="All", command=set_all_amount)
            all_button.pack(pady=10)

            # Input field for destination address
            tk.Label(transfer_window, text="Recipient Wallet Address:").pack(pady=5)
            destination_entry = tk.Entry(transfer_window, font=("Arial", 12))
            destination_entry.pack(pady=10)

            # Transfer Button
            def confirm_transfer():
                try:
                    # Validate transfer amount
                    amount = float(amount_entry.get())
                    if amount <= 0:
                        raise ValueError("Amount must be greater than 0.")
                    if amount > self.score:
                        raise ValueError("Insufficient score.")

                    # Get the recipient address
                    to_address = destination_entry.get().strip()
                    if not to_address:
                        raise ValueError("Please provide a recipient wallet address.")

                    # Perform the transfer (Update wallet balances)
                    self.score -= amount
                    self.wallets[self.wallet_address] = self.score

                    # Update recipient's wallet balance (if exists)
                    if to_address in self.wallets:
                        self.wallets[to_address] += amount
                    else:
                        self.wallets[to_address] = amount

                    # Record the transaction in the database
                    self.record_transaction(self.wallet_address, to_address, amount)

                    # Confirm transaction
                    messagebox.showinfo("Success", f"Successfully transferred {amount} points to {to_address}.\nNew Balance: {self.score}")
                    
                    # Close the transfer window
                    transfer_window.destroy()
                    self.score_label.config(text=f"Score: {self.score}")  # Update score display
                except ValueError as e:
                    messagebox.showerror("Error", str(e))

            confirm_button = tk.Button(transfer_window, text="Confirm Transfer", command=confirm_transfer)
            confirm_button.pack(pady=20)

    def record_transaction(self, from_address, to_address, amount):
            """Record the transaction in the database."""
            # Get the current timestamp
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Insert the transaction into the database
        # Insert the transaction details into the database
            self.cursor.execute("""
            INSERT INTO transactions (from_address, to_address, amount, timestamp)
            VALUES (?, ?, ?, ?)""", (from_address, to_address, amount, timestamp))
            
            # Commit the changes
            self.conn.commit()

            # Print the transaction (for debugging purposes)
            print(f"Transaction from {from_address} to {to_address} for {amount} points at {timestamp}")

    def transfer_funds(self):
        """ฟังก์ชันสำหรับโอนเหรียญ PUK จากกระเป๋าหนึ่งไปยังอีกกระเป๋าหนึ่ง"""
        # ตรวจสอบว่าผู้ใช้ได้เลือกกระเป๋าหรือยัง
        if self.wallet_info["address"] == "Unknown":
            messagebox.showerror("ไม่พบกระเป๋า", "กรุณาเลือกกระเป๋าที่มีอยู่ก่อน")
            return

        # เปิดหน้าต่างใหม่เพื่อให้ผู้ใช้กรอกข้อมูล
        transfer_window = tk.Toplevel(self.wallet_tab)
        transfer_window.title("โอนเหรียญ PUK")
        transfer_window.geometry("300x400")

        # แสดงข้อมูลที่อยู่กระเป๋าของผู้โอนและยอดเงิน
        tk.Label(transfer_window, text="กระเป๋าปัจจุบัน: " + self.wallet_info["address"]).pack(pady=10)
        tk.Label(transfer_window, text=f"ยอดเงินในกระเป๋า: {self.wallet_info['balance']} PUK").pack(pady=10)

        # Label และช่องกรอกข้อมูลสำหรับจำนวนเหรียญที่ต้องการโอน
        tk.Label(transfer_window, text="จำนวนเหรียญที่ต้องการโอน:").pack(pady=10)
        amount_entry = tk.Entry(transfer_window, font=("Arial", 12))
        amount_entry.pack(pady=10)

        # Label และช่องกรอกข้อมูลสำหรับที่อยู่กระเป๋าปลายทาง
        tk.Label(transfer_window, text="ที่อยู่กระเป๋าปลายทาง:").pack(pady=10)
        destination_address_entry = tk.Entry(transfer_window, font=("Arial", 12))
        destination_address_entry.pack(pady=10)


        def confirm_transfer():
            """ยืนยันการโอนเหรียญ PUK"""
            # ดึงค่าจากช่องกรอกข้อมูล
            destination_address = destination_address_entry.get().strip()
            try:
                amount = float(amount_entry.get().strip())
            except ValueError:
                amount = -1  # ใช้ค่า -1 เพื่อทำให้ผ่านการตรวจสอบเงื่อนไข
                messagebox.showerror("ข้อผิดพลาด", "กรุณากรอกจำนวนเงินที่ถูกต้อง")
                return

            # ตรวจสอบว่าได้กรอกข้อมูลหรือไม่
            if not destination_address or amount <= 0:
                messagebox.showerror("ข้อมูลไม่ครบถ้วน", "กรุณากรอกที่อยู่และจำนวนที่ต้องการโอน")
                return

            # สร้างการเชื่อมต่อฐานข้อมูล
            try:
                conn = sqlite3.connect(self.db_name)  # แก้ไข `self.db_name` ตามการใช้งานจริง
                cursor = conn.cursor()

                # ตรวจสอบว่ามียอดเงินในกระเป๋าเพียงพอ
                if self.wallet_info["balance"] < amount:
                    messagebox.showerror("ยอดเงินไม่เพียงพอ", "ยอดเงินในกระเป๋าของคุณไม่เพียงพอสำหรับการโอน")
                    return

                # อัปเดตยอดเงินในกระเป๋าของผู้โอนและผู้รับ
                cursor.execute("""
                    UPDATE wallets
                    SET balance = balance - ?
                    WHERE wallet_address = ?
                """, (amount, self.wallet_info["address"]))

                cursor.execute("""
                    UPDATE wallets
                    SET balance = balance + ?
                    WHERE wallet_address = ?
                """, (amount, destination_address))

                # บันทึกการทำธุรกรรมใน table transactions
                from datetime import datetime  # นำเข้า datetime อย่างถูกต้อง

                # ใช้ datetime.now() เพื่อดึงวันที่และเวลาปัจจุบัน
                cursor.execute('''
                INSERT INTO transactions (from_address, to_address, amount, timestamp)
                VALUES (?, ?, ?, ?)
                ''', (self.wallet_info["address"], destination_address, amount, datetime.now()))

                conn.commit()

                # อัปเดตยอดเงินใน UI
                self.wallet_info["balance"] -= amount
                self.update_wallet_info()

                messagebox.showinfo("โอนเหรียญสำเร็จ", f"โอนเหรียญ {amount} PuCoin ไปยัง {destination_address} สำเร็จ")

            except sqlite3.Error as e:
                if conn:
                    conn.rollback()  # ยกเลิกการเปลี่ยนแปลงในกรณีเกิดข้อผิดพลาด
                messagebox.showerror("ข้อผิดพลาดฐานข้อมูล", f"ไม่สามารถทำการโอนได้: {e}")
            finally:
                if conn:
                    conn.close()


            # ปิดหน้าต่างโอนเหรียญ
            transfer_window.destroy()

            # ปุ่มยืนยันการโอน
        ttk.Button(transfer_window, text="ยืนยันการโอน", command=confirm_transfer).pack(pady=10)
            # ปุ่มยกเลิก
        ttk.Button(transfer_window, text="ยกเลิก", command=transfer_window.destroy).pack(pady=10)
    def select_existing_wallet(self):
        """ให้ผู้ใช้เลือกกระเป๋าที่มีอยู่แล้ว"""
        # ดึงรายการที่อยู่กระเป๋าจากฐานข้อมูล
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT wallet_address FROM wallets")
            wallet_addresses = cursor.fetchall()

            if wallet_addresses:
                # สร้างหน้าต่าง Toplevel เพื่อแสดงรายการกระเป๋า
                select_window = tk.Toplevel(self.wallet_tab)
                select_window.title("เลือกกระเป๋าที่มีอยู่แล้ว")
                select_window.geometry("300x600")
                
                label = tk.Label(select_window, text="เลือกที่อยู่กระเป๋า", font=("Arial", 12))
                label.pack(pady=10)
                
                # สร้าง Listbox แสดงที่อยู่กระเป๋าทั้งหมด
                wallet_listbox = tk.Listbox(select_window, font=("Arial", 12), selectmode=tk.SINGLE)
                for address in wallet_addresses:
                    wallet_listbox.insert(tk.END, address[0])
                wallet_listbox.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
                
                def on_select():
                    selected_address = wallet_listbox.get(tk.ACTIVE)
                    if selected_address:
                        # โหลดรายละเอียดกระเป๋าที่เลือก
                        self.wallet_info = self.load_wallet_info(selected_address)
                        self.update_wallet_info()
                        select_window.destroy()  # ปิดหน้าต่างเลือก
                    else:
                        messagebox.showerror("การเลือกไม่ถูกต้อง", "ไม่ได้เลือกกระเป๋า")
                
                # ปุ่มสำหรับยืนยันการเลือกกระเป๋า
                select_button = ttk.Button(select_window, text="เลือกกระเป๋า", command=on_select)
                select_button.pack(pady=10)
                
                # ปุ่มยกเลิกการเลือก
                cancel_button = ttk.Button(select_window, text="ยกเลิก", command=select_window.destroy)
                cancel_button.pack(pady=10)
                
                select_window.transient(self.wallet_tab)
                select_window.grab_set()
                self.wallet_tab.wait_window(select_window)
                
            else:
                messagebox.showinfo("ไม่มีข้อมูลกระเป๋า", "ไม่พบกระเป๋าในฐานข้อมูล กรุณาสร้างกระเป๋าใหม่")
        except sqlite3.Error as e:
            print(f"Error loading wallets: {e}")
            messagebox.showerror("ข้อผิดพลาดฐานข้อมูล", "ไม่สามารถโหลดข้อมูลกระเป๋าจากฐานข้อมูลได้")
        finally:
            conn.close()
    def load_wallet_info(self, address):
        """Load wallet details for a given address."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT wallet_address, balance, private_key FROM wallets WHERE wallet_address = ?", (address,))
            result = cursor.fetchone()

            if result:
                wallet_info = {
                    "address": result[0],
                    "balance": result[1],
                    "private_key": result[2]
                }

                # Create a label for the wallet address
                address_label = tk.Label(self.root, text=f"Wallet Address: {wallet_info['address']}")
                address_label.pack()

                # Function to copy the wallet address to the clipboard
                def copy_to_clipboard():
                    self.root.clipboard_clear()  # Clear the clipboard
                    self.root.clipboard_append(wallet_info["address"])  # Append the address to the clipboard
                    self.root.update()  # Ensure the clipboard is updated
                    messagebox.showinfo("Copied", "Wallet address copied to clipboard!")

                # Create a button to copy the wallet address
                copy_button = tk.Button(self.root, text="Copy Address", command=copy_to_clipboard)
                copy_button.pack()

                # Optionally, you can return the wallet_info if you need it elsewhere in your application
                return wallet_info

            else:
                messagebox.showerror("Wallet Not Found", "No wallet found with the provided address.")
                return None
        except sqlite3.Error as e:
            print(f"Error fetching wallet info: {e}")
            return None
        finally:
            conn.close()
    def get_wallet_info(self):
        # Assuming you're using SQLite, modify this query to fetch the wallet address and balance
        try:
            connection = sqlite3.connect("blockchain.db")  # Replace with your actual DB path
            cursor = connection.cursor()
            cursor.execute("SELECT wallet_address, balance, private_key FROM wallets WHERE id = 1")  # Adjust the WHERE clause as necessary
            result = cursor.fetchone()

            if result:
                wallet_info = {
                    "address": result[0],  # wallet_address
                    "balance": result[1],  # balance
                    "private_key": result[2]  # private_key
                }
                return wallet_info
            else:
                # Default values if no wallet info found
                return {"address": "Unknown", "balance": 0, "private_key": "Not Available"}

        except Exception as e:
            print(f"Error fetching wallet info: {e}")
            return {"address": "Unknown", "balance": 0, "private_key": "Not Available"}
    def get_wallet_balance(self, address):
        """คำนวณยอดเงินของกระเป๋าจากข้อมูลใน blockchain.db"""
        balance = 0
        try:
            conn = sqlite3.connect("blockchain.db")  # เชื่อมต่อกับฐานข้อมูล blockchain.db
            cursor = conn.cursor()

            # คำนวณยอดเงินโดยการรวมยอดที่โอนเข้ากระเป๋า (positive) และลบยอดที่โอนออกจากกระเป๋า (negative)
            cursor.execute("""
                SELECT SUM(CASE 
                            WHEN to_address = ? THEN amount  -- เงินที่โอนเข้ากระเป๋า
                            WHEN from_address = ? THEN -amount  -- เงินที่โอนออกจากกระเป๋า
                            ELSE 0
                          END) AS balance
                FROM transactions
            """, (address, address))

            row = cursor.fetchone()
            if row:
                balance = row[0] if row[0] else 0  # ใช้ค่า 0 ถ้าผลลัพธ์เป็น None

            conn.close()
        except sqlite3.Error as e:
            print(f"Error calculating wallet balance: {e}")
        
        return balance
    def refresh_balance(self):
        """Refresh wallet balance and update the UI."""
        self.wallet_info["balance"] = self.get_wallet_balance(self.wallet_info["address"])
        self.update_wallet_info()
    def create_new_wallet(self):
        """Create a new wallet and update the UI with encrypted private key."""
        # Generate wallet data
        raw_private_key = self.generate_private_key()
        encrypted_private_key = self.encrypt_private_key(raw_private_key)
        new_wallet = {
            "address": self.generate_wallet_address(),
            "balance": 0,
            "private_key": encrypted_private_key
        }

        # Save to database
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO wallets (wallet_address, balance, private_key) VALUES (?, ?, ?)",
            (new_wallet["address"], new_wallet["balance"], new_wallet["private_key"])
        )
        conn.commit()
        conn.close()

        # Update wallet info and UI
        self.wallet_info = {
            "address": new_wallet["address"],
            "balance": new_wallet["balance"],
            "private_key": raw_private_key  # Show raw key for user only
        }
        self.update_wallet_info()
    def copy_private_key(self):
            """คัดลอกคีย์ส่วนตัวไปยัง clipboard"""
            private_key = self.wallet_info['private_key']
            pyperclip.copy(private_key)  # คัดลอกคีย์ส่วนตัวไปที่ clipboard
            messagebox.showinfo("Copied", "คีย์ส่วนตัวถูกคัดลอกไปยังคลิปบอร์ดแล้ว.")  # แสดงข้อความแจ้งเตือน
    def update_wallet_info(self):
        """Update the wallet information in the UI."""
        # Example placeholder for UI update logic
        print("Wallet Address:", self.wallet_info["address"])
        print("Balance:", self.wallet_info["balance"])
        print("Private Key (Decrypted):", self.wallet_info["private_key"])

        # อัปเดตที่อยู่กระเป๋า
        self.wallet_address_label.config(text=self.wallet_info["address"])

        # อัปเดตยอดเงิน
        self.wallet_balance_label.config(text=f"Balance: {self.wallet_info['balance']} PUK")
    def copy_wallet_address(self):
        """คัดลอกที่อยู่กระเป๋าไปยัง clipboard"""
        wallet_address = self.wallet_info['address']
        pyperclip.copy(wallet_address)  # คัดลอกที่อยู่กระเป๋าไปที่ clipboard
        messagebox.showinfo("Copied", "ที่อยู่กระเป๋าถูกคัดลอกไปยังคลิปบอร์ดแล้ว.")  # แสดงข้อความแจ้งเตือน
    def load_or_create_wallet(self):
        """Load wallet information or create a new wallet."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM wallets LIMIT 1")
            wallet = cursor.fetchone()

            if wallet is None:
                # สร้างกระเป๋าเงินใหม่
                wallet_address = self.generate_wallet_address()  # สร้างที่อยู่
                private_key = self.generate_private_key()  # สร้างคีย์ส่วนตัว
                balance = 0.0

                # บันทึกข้อมูลกระเป๋าเงินใหม่
                cursor.execute("INSERT INTO wallets (wallet_address, balance, private_key) VALUES (?, ?, ?)",
                               (wallet_address, balance, private_key))
                conn.commit()

                self.wallet_info = {
                    "address": wallet_address,
                    "balance": balance,
                    "private_key": private_key
                }
            else:
                # ถ้ามีกระเป๋าเงินในฐานข้อมูล
                if len(wallet) < 3:
                    print("ข้อมูลไม่ครบถ้วนในฐานข้อมูล!")
                    self.wallet_info = {
                        "address": "new_wallet_address",
                        "balance": 0.0,
                        "private_key": "private_key_example"
                    }
                else:
                    self.wallet_info = {
                        "address": wallet[0],  # wallet_address
                        "balance": wallet[1],   # balance
                        "private_key": wallet[2]  # private_key
                    }
        except sqlite3.Error as e:
            print(f"เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล: {e}")
            self.wallet_info = None  # หากเกิดข้อผิดพลาดให้ตั้งเป็น None
        finally:
            conn.close()

        return self.wallet_info 
    def generate_wallet_address(self):
        """Generate a unique wallet address (for demonstration)."""
        return secrets.token_hex(16)
    def generate_private_key(self):
        """Generate a new private key for the wallet."""
        return secrets.token_hex(32)  # Generate a 64-character hexadecimal private key
    def generate_wallet_address(self):
        """Generate a unique wallet address (for demonstration)."""
        return secrets.token_hex(16)
    def generate_encryption_key(self):
        """Generate a Fernet encryption key and store it in a file."""
        key = Fernet.generate_key()
        with open("encryption_key.key", "wb") as key_file:
            key_file.write(key)
    def load_encryption_key(self):
        """Load the Fernet encryption key from the file."""
        try:
            with open("encryption_key.key", "rb") as key_file:
                return key_file.read()  # Return the encryption key as bytes
        except FileNotFoundError:
            print("Key file not found. Generating a new one.")
            self.generate_encryption_key()
            return self.load_encryption_key()
    def encrypt_private_key(self, private_key):
        """Encrypt the private key using a generated encryption key."""
        encryption_key = self.load_encryption_key()  # Load the encryption key
        fernet = Fernet(encryption_key)
        encrypted_private_key = fernet.encrypt(private_key.encode())
        return encrypted_private_key.decode()
    def decrypt_private_key(encrypted_key, encryption_key):
        """Decrypt the private key using the provided encryption key."""
        try:
            fernet = Fernet(encryption_key)
            decrypted_private_key = fernet.decrypt(encrypted_key.encode())
            return decrypted_private_key.decode()
        except Exception as e:
            print(f"Error decrypting key: {e}")
            return None
    def load_or_create_wallet(self):
        """Load wallet information or create a new wallet if none exists."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            # ตรวจสอบกระเป๋าในฐานข้อมูล
            cursor.execute("SELECT * FROM wallets LIMIT 1")
            wallet = cursor.fetchone()

            if wallet is None:
                # ถ้าไม่พบกระเป๋า ให้สร้างกระเป๋าใหม่
                wallet_address = self.generate_wallet_address()  # สร้างที่อยู่
                private_key = self.generate_private_key()  # สร้างคีย์ส่วนตัว
                balance = 0.0

                # บันทึกข้อมูลกระเป๋าใหม่
                cursor.execute("INSERT INTO wallets (wallet_address, balance, private_key) VALUES (?, ?, ?)",
                            (wallet_address, balance, private_key))
                conn.commit()

                self.wallet_info = {
                    "address": wallet_address,
                    "balance": balance,
                    "private_key": private_key
                }
                print("Created new wallet")
            else:
                # ถ้ามีกระเป๋าเงินในฐานข้อมูล
                self.wallet_info = {
                    "address": wallet[1],  # wallet_address
                    "balance": wallet[2],  # balance
                    "private_key": wallet[3]  # private_key
                }
                print("Loaded existing wallet")

        except sqlite3.Error as e:
            print(f"Error connecting to the database: {e}")
            self.wallet_info = None  # หากเกิดข้อผิดพลาดให้ตั้งเป็น None

        finally:
            conn.close()

        return self.wallet_info
    def add_wallet(self, address, balance=0):
            """เพิ่มกระเป๋าเงินใหม่"""
            self.wallets[address] = balance
    def transfer(self, sender_address, recipient_address, amount):
        """ฟังก์ชันสำหรับโอนเงิน"""
        if sender_address not in self.wallets:
            raise ValueError("ที่อยู่ผู้ส่งไม่ถูกต้อง")
        
        if recipient_address not in self.wallets:
            raise ValueError("ที่อยู่ผู้รับไม่ถูกต้อง")

        if self.wallets[sender_address] < amount:
            raise ValueError("ยอดเงินไม่เพียงพอในการโอน")

        # ลดจำนวนเงินจากกระเป๋าผู้ส่งและเพิ่มให้กับผู้รับ
        self.wallets[sender_address] -= amount
        self.wallets[recipient_address] += amount

        # สามารถบันทึกการโอนลงใน transactions หรือ blockchain ได้
        self.transactions.append((sender_address, recipient_address, amount))

        return True  # ส่งคืน True เมื่อการโอนเสร็จสมบูรณ์
    def use_existing_wallet(self):
        def validate_private_key():
            entered_key = private_key_entry.get()
            wallet = self.get_wallet_by_private_key(entered_key)
            if wallet:
                self.wallet_info = wallet  # ใช้กระเป๋านี้
                self.update_wallet_info()
                messagebox.showinfo("สำเร็จ", "ใช้กระเป๋าเดิมสำเร็จ!")
                wallet_window.destroy()
            else:
                messagebox.showerror("ผิดพลาด", "ไม่พบกระเป๋าที่มี private key นี้")

        # สร้างหน้าต่างใหม่สำหรับกรอก Private Key
        wallet_window = tk.Toplevel(self.root)
        wallet_window.title("ใช้กระเป๋าเดิม")
        wallet_window.geometry("400x200")

        tk.Label(wallet_window, text="กรอก Private Key:", font=("Helvetica", 12)).pack(pady=10)
        private_key_entry = tk.Entry(wallet_window, show="*", width=40)
        private_key_entry.pack(pady=10)

        tk.Button(wallet_window, text="ยืนยัน", command=validate_private_key).pack(pady=20)
    def calculate_balance(self, address):
        try:
            conn = sqlite3.connect("blockchain.db")
            cursor = conn.cursor()

            # คำนวณยอดเงินที่ได้รับ
            cursor.execute("SELECT amount FROM transactions WHERE to_address = ?", (address,))
            received = sum(row[0] for row in cursor.fetchall())

            # คำนวณยอดเงินที่ส่งออก
            cursor.execute("SELECT amount FROM transactions WHERE from_address = ?", (address,))
            sent = sum(row[0] for row in cursor.fetchall())

            conn.close()
            return received - sent
        except sqlite3.Error as e:
            print(f"เกิดข้อผิดพลาด: {e}")
            return 0.0
    def get_wallet_by_private_key(self, private_key):
        try:
            conn = sqlite3.connect("wallets.db")
            cursor = conn.cursor()
            cursor.execute("SELECT address FROM wallets WHERE private_key = ?", (private_key,))
            row = cursor.fetchone()
            conn.close()

            if row:
                address = row[0]
                balance = self.calculate_balance(address)  # เรียก self สำหรับ method ภายในคลาส
                return {"address": address, "balance": balance, "private_key": private_key}
            return None
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"เกิดข้อผิดพลาดในการเข้าถึงฐานข้อมูล: {e}")
            return None
    def create_message_tab(self): 
        """Create UI for saving messages and transferring funds"""
        # Label for Time Capsule Feature Introduction
        self.message_label = tk.Label(self.message_tab, 
                                    text="To create a Time Capsule feature for messages", 
                                    font=("Helvetica", 14, "bold"),  # Set font to Helvetica, bold, and size 14
                                    bg="#f4f4f9", 
                                    fg="#333333")  # Dark text color for readability
        self.message_label.pack(pady=(20, 10))  # Added more padding at the top for spacing

        # Label for Message Input Feature Explanation
        self.message_label_2 = tk.Label(self.message_tab, 
                                        text="To implement the feature where users can input and save their messages in their preferred language", 
                                        font=("Helvetica", 8),  # Set font to Helvetica, size 12
                                        bg="#f4f4f9", 
                                        fg="#555555")  # Slightly lighter text color
        self.message_label_2.pack(pady=(10, 20))  # Added bottom padding for better spacing

        
        # เปลี่ยนจาก Entry เป็น Text เพื่อให้สามารถเขียนหลายบรรทัด
        self.message_text = tk.Text(self.message_tab, width=100, height=10)  # กำหนดให้มี 20 บรรทัด
        self.message_text.pack(pady=10)

        # Bind right-click to show context menu
        self.message_text.bind("<Button-3>", self.show_context_menu)
        # Frame for buttons
        button_frame = tk.Frame(self.message_tab)
        button_frame.pack(pady=10)
        # Save Message Button
        self.save_button = tk.Button(button_frame, text="Save Message", command=self.save_message)
        self.save_button.pack(side="left", padx=10)

        # Clear Text Button
        self.clear_button = tk.Button(button_frame, text="Clear Text", command=self.clear_message)
        self.clear_button.pack(side="left", padx=10)


        # Context menu for right-click
        self.context_menu = tk.Menu(self.message_tab, tearoff=0)
        self.context_menu.add_command(label="Cut", command=self.cut_text)
        self.context_menu.add_command(label="Copy", command=self.copy_text)
        self.context_menu.add_command(label="Paste", command=self.paste_text)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Clear", command=self.clear_message)
    def show_context_menu(self, event):
        """Show the context menu when right-clicked."""
        self.context_menu.post(event.x_root, event.y_root)
    def cut_text(self):
        """Cut selected text"""
        self.message_text.event_generate("<<Cut>>")
    def copy_text(self):
        """Copy selected text"""
        self.message_text.event_generate("<<Copy>>")
    def paste_text(self):
        """Paste text"""
        self.message_text.event_generate("<<Paste>>")
    def clear_message(self):
        """Clear the message entry"""
        self.message_text.delete(1.0, tk.END)  # ลบข้อความทั้งหมดในช่อง Text  
    def save_message(self):
        """Save the message and transfer funds"""
        # ดึงข้อความจากกล่องข้อความ
        message = self.message_text.get("1.0", tk.END).strip()  # ใช้ self.message_text แทน self.message_entry
        if message:
            # เพิ่มข้อความเป็นบล็อกใหม่ในบล็อกเชน
            self.blockchain.add_block(message)

            # จำนวนเหรียญที่ต้องการโอน (ปรับตามต้องการ)
            amount_to_transfer = 5

            # ตรวจสอบว่ามีข้อมูล wallet details ที่ใช้งานอยู่
            if hasattr(self, 'wallet_details') and self.wallet_details:
                to_address = self.wallet_details.get('address')  # ที่อยู่กระเป๋าที่ใช้งาน
                private_key = self.wallet_details.get('private_key')  # คีย์ส่วนตัวกระเป๋าที่ใช้งาน

                if to_address and private_key:
                    # ตรวจสอบยอดเงินในกระเป๋า
                    if self.wallet_details['balance'] >= amount_to_transfer:
                        # โอนเหรียญ
                        if self.blockchain.transfer_funds(amount_to_transfer, to_address, private_key):
                            # ถ้าโอนเหรียญสำเร็จ แสดงข้อความแจ้งเตือน
                            messagebox.showinfo("Success", f"Message saved and {amount_to_transfer} coins transferred to your active wallet.")
                            
                            # อัปเดตยอดเงินในกระเป๋าหลังจากโอน
                            self.wallet_details['balance'] -= amount_to_transfer  # ลดยอดเงินจากการโอน
                            self.update_wallet_details()  # อัปเดตข้อมูล wallet ใน UI

                            # แสดงที่อยู่กระเป๋าหลังจากโอน
                            self.wallet_address_label.config(text=f"ที่อยู่กระเป๋า: {to_address}")
                        else:
                            # ถ้าโอนเหรียญล้มเหลว แสดงข้อความผิดพลาด
                            messagebox.showerror("Error", "Failed to transfer coins.")
                    else:
                        # ถ้ายอดเงินไม่พอ แสดงข้อความแจ้งเตือน
                        messagebox.showwarning("Insufficient Funds", "You do not have enough funds to transfer.")
                else:
                    # ถ้ากระเป๋าไม่มี address หรือ private_key
                    messagebox.showerror("Error", "Invalid wallet details. Please check your active wallet.")
            else:
                # ถ้าไม่มี wallet details
                messagebox.showerror("Info", "The coin will be sent to the default wallet address that the system generates.")
        else:
            # ถ้าข้อความว่าง แสดงข้อความเตือนให้กรอกข้อความ
            messagebox.showwarning("Input Error", "Please enter a message.")
    def update_wallet_details(self):
        """อัปเดตข้อมูล wallet ใน UI (ยอดคงเหลือ, คีย์ส่วนตัว ฯลฯ)"""
        if self.wallet_details:
            self.wallet_balance_label.config(text=f"ยอดคงเหลือ: {self.wallet_details['balance']} เหรียญ")
            self.wallet_address_label.config(text=f"ที่อยู่กระเป๋า: {self.wallet_details['address']}")
            self.private_key_label.config(text=f"คีย์ส่วนตัว: {self.wallet_details['private_key']}")
    def create_transactions_tab(self):
         # เพิ่มช่องสำหรับค้นหาธุรกรรม
        self.search_entry = tk.Entry(self.transactions_tab, width=30, font=("Arial", 12))
        self.search_entry.pack(pady=10)

        # เพิ่มปุ่มค้นหาธุรกรรม
        self.search_button = tk.Button(
            self.transactions_tab, 
            text="ค้นหา", 
            command=self.search_transactions
        )
        self.search_button.pack(pady=5)

                # เพิ่ม Label เพื่อแสดงข้อมูลธุรกรรมที่เลือก
        self.transaction_details_label = tk.Label(
        self.transactions_tab,
            text="ข้อมูลธุรกรรมจะปรากฏที่นี่",  # ข้อความเริ่มต้น
            width=100,  # ความกว้าง
            height=6,  # ความสูงเพิ่มขึ้นเพื่อให้ข้อความอ่านง่ายขึ้น
            anchor="w",  # จัดแนวข้อความทางซ้าย
            justify="left",  # การจัดแนวข้อความ
            wraplength=600,  # ความยาวสูงสุดของบรรทัดที่ 600 พิกเซล
            font=("Arial", 12),  # ใช้ฟอนต์ Arial ขนาด 12
            bg="black",  # สีพื้นหลังอ่อนเพื่อให้ข้อความเด่น
            fg="white",  # สีข้อความเป็นสีเทาเข้ม
            padx=10,  # ระยะห่างซ้ายจากข้อความ
            pady=10,  # ระยะห่างบน-ล่าง
            relief="sunken"  # สร้างขอบให้ดูน่าสนใจ
        )
        self.transaction_details_label.pack(pady=10)

        # สร้างส่วนแสดงธุรกรรม
        self.transactions_list = tk.Listbox(self.transactions_tab, width=80, height=25)
        self.transactions_list.pack(pady=10)
        self.transactions_list.bind("<ButtonRelease-1>", self.on_transaction_select)

        # ปุ่ม Refresh
        refresh_button = tk.Button(
            self.transactions_tab, 
            text="ALL transactions", 
            command=self.refresh_transactions_list
        )
        refresh_button.pack(pady=5)
    def search_transactions(self):
            """ค้นหาธุรกรรมจากคำค้นหา"""
            search_query = self.search_entry.get().lower()  # ดึงคำค้นหาจากช่องกรอก
            self.transactions_list.delete(0, tk.END)  # ล้างรายการเดิม
            transactions = self.blockchain.view_transactions()  # ดึงธุรกรรมจาก Blockchain

            if transactions:
                for t in transactions:
                    # ตรวจสอบว่า คำค้นหาตรงกับข้อมูลในธุรกรรม
                    transaction_text = f"หมายเลข ID: {t[0]}, ช่วงเวลาที่ทำธุรกรรม Time: {t[1]}, ส่งจาก From: {t[2]}, ไปยัง To: {t[3]}, จำนวน Amount: {t[4]}"
                    if search_query in transaction_text.lower():  # หากคำค้นหาตรง
                        self.transactions_list.insert(tk.END, transaction_text)
                if not any(search_query in f"หมายเลข ID: {t[0]}, ช่วงเวลาที่ทำธุรกรรม Time: {t[1]}, ส่งจาก From: {t[2]}, ไปยัง To: {t[3]}, จำนวน Amount: {t[4]}".lower() for t in transactions):
                    self.transactions_list.insert(tk.END, "ไม่พบธุรกรรมที่ตรงกับคำค้นหา")
            else:
                self.transactions_list.insert(tk.END, "ไม่มีธุรกรรม")
    def refresh_transactions_list(self):
        """รีเฟรชรายการธุรกรรม"""
        self.transactions_list.delete(0, tk.END)  # ล้างรายการเดิม
        transactions = self.blockchain.view_transactions()  # ดึงธุรกรรมจาก Blockchain
        if transactions:
            for t in transactions:
                display_text = f"ID: {t[0]}, Time: {t[1]}, From: {t[2]}, To: {t[3]}, Amount: {t[4]}"
                self.transactions_list.insert(tk.END, display_text)
        else:
            self.transactions_list.insert(tk.END, "ไม่มีธุรกรรม")
    def on_transaction_select(self, event):
        selected_index = self.transactions_list.curselection()
        if selected_index:
            transaction = self.transactions_list.get(selected_index)
            # แสดงข้อมูลธุรกรรมที่เลือกใน Label
            self.transaction_details_label.config(text=f"ข้อมูลธุรกรรมที่เลือก: {transaction}")
    def create_detail_tab(self):
        """สร้างแท็บรายละเอียดและแสดงข้อมูลเกี่ยวกับการทำงานของโปรแกรม"""
        # แสดงข้อความหัวข้อ "ข้อมูลรายละเอียด"
        label = tk.Label(self.detail_tab, text="ข้อมูลรายละเอียดเกี่ยวกับโปรแกรม", font=("Arial", 16, "bold"))
        label.pack(padx=10, pady=10)

        # สร้างเฟรมสำหรับ Text widget และ Scrollbar
        frame = tk.Frame(self.detail_tab)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # สร้าง Scrollbar
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # สร้าง Text widget เพื่อแสดงข้อมูลรายละเอียด
        detail_text = tk.Text(frame, wrap=tk.WORD, height=20, width=80, yscrollcommand=scrollbar.set)
        detail_text.insert(tk.END, """
        ยินดีต้อนรับสู่โปรแกรมบล็อกเชนของเรา! นี่คือคำแนะนำการใช้งานและลักษณะที่โดดเด่นของโปรแกรม:

        1. **เริ่มต้นใช้งาน**
            - เมื่อคุณเริ่มต้นโปรแกรม ระบบจะทำการตรวจสอบฐานข้อมูล หากไม่มีบล็อกใด ๆ ในระบบ ระบบจะสร้าง Genesis Block (บล็อกแรก) ให้โดยอัตโนมัติ

        2. **การบันทึกข้อความในบล็อกเชน**
            - ผู้ใช้สามารถป้อนข้อความใหม่ได้ ซึ่งโปรแกรมจะสร้างบล็อกใหม่พร้อมข้อมูลที่จำเป็น เช่น Index, Message, Timestamp, Previous Hash และ Current Hash

        3. **การแสดงข้อมูลในบล็อกเชน**
            - โปรแกรมจะแสดงรายการบล็อกทั้งหมดในระบบ และคุณสามารถเลือกเพื่อดูรายละเอียดของแต่ละบล็อกได้

        4. **การตรวจสอบความสมบูรณ์ของบล็อกเชน**
            - โปรแกรมจะทำการตรวจสอบการเชื่อมโยงของแต่ละบล็อก โดยจะตรวจสอบ Previous Hash และแจ้งเตือนหากพบปัญหาในข้อมูล

        5. **การออกแบบระบบอินเตอร์เฟซ**
            - โปรแกรมได้รับการออกแบบให้มีอินเตอร์เฟซที่ใช้งานง่าย โดยมีช่องสำหรับกรอกข้อมูลและหน้าต่างสำหรับแสดงรายละเอียดบล็อก

        6. **การจัดการฐานข้อมูล**
            - โปรแกรมใช้ SQLite สำหรับจัดเก็บข้อมูลบล็อก เพื่อให้การเก็บข้อมูลมีความเร็วและเสถียร

        7. **การปิดโปรแกรม**
            - เมื่อปิดโปรแกรม ระบบจะทำการบันทึกสถานะและปิดการเชื่อมต่อฐานข้อมูลอย่างปลอดภัย

        ### ลักษณะที่โดดเด่นของโปรแกรม:
        - **ความปลอดภัย**: ข้อมูลที่บันทึกในบล็อกเชนจะไม่สามารถถูกแก้ไขได้หลังจากที่บล็อกถูกสร้างแล้ว
        - **โปร่งใส**: ผู้ใช้สามารถตรวจสอบข้อมูลในบล็อกเชนได้ตลอดเวลา
        - **ใช้งานง่าย**: อินเตอร์เฟซของโปรแกรมได้รับการออกแบบให้เข้าใจง่ายและสะดวกต่อการใช้งาน
        - **การตรวจสอบได้**: ระบบจะตรวจสอบความสมบูรณ์ของข้อมูลในแต่ละบล็อกเชน เพื่อให้มั่นใจว่าข้อมูลไม่ถูกแก้ไขหรือบิดเบือน
        """)

        # ป้องกันการแก้ไขข้อความใน Text widget
        detail_text.config(state=tk.DISABLED)

        # แสดง Text widget ในแท็บ
        detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # เชื่อมโยง Scrollbar กับ Text widget
        scrollbar.config(command=detail_text.yview)

        print("This's Details!")
if __name__ == "__main__":
    root = tk.Tk()
    app = WalletApp(root)
    root.mainloop()