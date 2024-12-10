import sqlite3
import hashlib
import uuid
import tkinter as tk
from tkinter import messagebox, ttk
import pyperclip  # เพิ่มไลบรารี pyperclip
from tkinter import Menu
from datetime import datetime
import secrets

class Blockchain:
    def __init__(self, db_name, wallet_address, private_key):
        self.chain = []
        self.mempool = []  # เก็บธุรกรรมที่รอการยืนยัน
        self.wallet_address = wallet_address
        self.private_key = private_key
        self.db_name = db_name
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
                                timestamp TEXT,
                                from_address TEXT,
                                to_address TEXT,
                                amount REAL
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
                        timestamp TEXT NOT NULL,
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
                block = {"index": row[0], "message": row[1], "hash": row[2]}
                self.chain.append(block)
            conn.close()
        except sqlite3.Error as e:
            print(f"Error loading blocks from database: {e}")

    def transfer_funds(self, amount, to_address, key):
        """ฟังก์ชันการโอนเหรียญไปยังที่อยู่อื่น"""
        if key == self.private_key:
            if amount <= self.wallet_balance:
                self.wallet_balance -= amount
                print(f"โอน {amount} เหรียญ ไปยัง {to_address}")
                
                # บันทึกธุรกรรม
                self.save_transaction_to_db(self.wallet_address, to_address, amount)
                return True
            else:
                print("ยอดเงินไม่เพียงพอในการโอน")
                return False
        else:
            print("คีย์ไม่ตรงกัน")
            return False

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

    def __init__(self, root, db_name="blockchain.db"):
            self.root = root
            self.root.title("ChainLogger #PUKUMPee V.1.0.0")
            self.root.geometry("650x800")
            self.db_name = db_name  # Assign db_name here
            
            self.create_wallet_table()  # Ensure the table exists
            
            # Load or create wallet and store its info
            self.wallet_info = self.load_or_create_wallet()

            # Ensure that wallet_info contains necessary values
            if "address" in self.wallet_info and "private_key" in self.wallet_info:
                self.wallet_address = self.wallet_info["address"]
                self.private_key = self.wallet_info["private_key"]
            else:
                # If wallet info is missing, handle it accordingly (maybe raise an error or create a wallet)
                print("Error: Wallet information missing.")
                return

            # Create blockchain instance using wallet address and private key
            self.blockchain = Blockchain(self.db_name, self.wallet_address, self.private_key)
            
            # Initialize the UI after everything is set up
            self.create_ui()  # Call UI creation here

    def create_ui(self):
            """Create the user interface for the wallet."""
            self.main_frame = tk.Frame(self.root, bg="#f4f4f9")
            self.main_frame.pack(fill=tk.BOTH, expand=True)      
            
            # Create tabs
            self.tab_control = ttk.Notebook(self.main_frame)

            # Display wallet address
            wallet_label = tk.Label(self.root, text="Wallet Address: ", font=("Arial", 12))
            wallet_label.pack(pady=5)
            wallet_address_label = tk.Label(self.root, text=self.blockchain.wallet_address, font=("Arial", 12))
            wallet_address_label.pack(pady=5)

            # Display private key
            private_key_label = tk.Label(self.root, text="Private Key: ", font=("Arial", 12))
            private_key_label.pack(pady=5)
            private_key_value_label = tk.Label(self.root, text=self.blockchain.private_key, font=("Arial", 12))
            private_key_value_label.pack(pady=5)

            # Tabs for additional functionality
            self.blockchain_tab = ttk.Frame(self.tab_control)
            self.wallet_tab = ttk.Frame(self.tab_control)
            self.message_tab = ttk.Frame(self.tab_control)
            self.transactions_tab = ttk.Frame(self.tab_control)
            self.detail_tab = ttk.Frame(self.tab_control)

            self.tab_control.add(self.blockchain_tab, text="Blockchain Info")
            self.tab_control.add(self.wallet_tab, text="Wallet Details")
            self.tab_control.add(self.message_tab, text="Save Message")
            self.tab_control.add(self.transactions_tab, text="Transactions")
            self.tab_control.add(self.detail_tab, text="Detail")

            self.tab_control.pack(expand=1, fill="both")

            # Create the content for each tab
            self.create_blockchain_tab()
            self.create_wallet_tab()
            self.create_message_tab()
            self.create_transactions_tab()
            self.create_detail_tab()

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
        """Generate a private key (for demonstration)."""
        return secrets.token_hex(32)

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

    def create_blockchain_tab(self):
        self.blockchain_listbox = tk.Listbox(self.blockchain_tab, height=20, width=100)
        self.blockchain_listbox.pack(pady=10)

        # แสดงข้อมูลบล็อกเชน
        self.update_blockchain_list()

        self.update_button = tk.Button(self.blockchain_tab, text="อัพเดตข้อมูล", command=self.update_blockchain_list)
        self.update_button.pack(pady=10)

        # สร้างปุ่มให้เปิดหน้าต่าง Dashboard
        self.dashboard_button = tk.Button(self.blockchain_tab, text="เปิดรายงานการตรวจสอบฐานข้อมูล", command=self.create_dashboard)
        self.dashboard_button.pack(pady=20)
        # เพิ่มการคลิกที่รายการใน Listbox
        self.blockchain_listbox.bind("<ButtonRelease-1>", self.show_block_details)

    def create_dashboard(self):
        # ฟังก์ชันตรวจสอบฐานข้อมูล
        def check_block_integrity(db_name):
            result = []
            modified_count = 0
            conn = None
            try:
                conn = sqlite3.connect(db_name)
                cursor = conn.cursor()

                cursor.execute('SELECT "index", message, hash FROM blocks')
                rows = cursor.fetchall()

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

                if not result:
                    result.append("ข้อมูลในบล็อกทั้งหมดถูกต้อง ไม่มีการแก้ไข")

            except sqlite3.Error as e:
                result.append(f"เกิดข้อผิดพลาดในการตรวจสอบบล็อก: {e}")
            
            finally:
                if conn:
                    conn.close()  # Ensure connection is closed

            return result, modified_count

        # ตรวจสอบข้อมูลจากฐานข้อมูล
        integrity_report, modified_count = check_block_integrity("blockchain.db")

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

        # เพิ่มปุ่ม Refresh
        def refresh():
            # รีเฟรชข้อมูลโดยการตรวจสอบใหม่
            new_report, new_modified_count = check_block_integrity("blockchain.db")
            text_widget.config(state=tk.NORMAL)
            text_widget.delete(1.0, tk.END)
            text_widget.insert(tk.END, "\n".join(new_report))
            text_widget.config(state=tk.DISABLED)
            
            # แสดงจำนวนบล็อกที่แฮชถูกแก้ไข
            modified_label.config(text=f"จำนวนบล็อกที่แฮชถูกแก้ไข: {new_modified_count}")

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

        # เปลี่ยนสีพื้นหลังและตัวอักษร
        new_window.configure(bg="#2c3e50")  # สีพื้นหลังของหน้าต่าง

        # เพิ่ม Scrollbar
        scrollbar = tk.Scrollbar(new_window, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # เพิ่ม Text Widget
        text_widget = tk.Text(
            new_window,
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set,
            bg="#ecf0f1",  # สีพื้นหลังของข้อความ
            fg="#2c3e50",  # สีตัวอักษร
            font=("Helvetica", 12),  # กำหนดฟอนต์และขนาด
            padx=10,
            pady=10,
        )

        # แสดงข้อความบล็อกและ timestamp
        full_message = f"Timestamp: {timestamp}\n\n{block_message}"
        text_widget.insert(tk.END, full_message)
        text_widget.config(state=tk.DISABLED)  # ปิดการแก้ไขข้อความ
        text_widget.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # กำหนด Scrollbar ให้เลื่อน Text Widget
        scrollbar.config(command=text_widget.yview)

        # เพิ่ม Label หัวข้อที่สวยงาม
        header_label = tk.Label(
            new_window,
            text="รายละเอียดของบล็อก",
            bg="#34495e",  # สีพื้นหลังหัวข้อ
            fg="#ecf0f1",  # สีตัวอักษรหัวข้อ
            font=("Helvetica", 14, "bold"),  # กำหนดฟอนต์ตัวหนา
            pady=10,
        )
        header_label.pack(fill=tk.X, padx=10, pady=(10, 0))  # จัดให้ชิดขอบและมีระยะห่าง

    def update_blockchain_list(self):
        """อัปเดตรายการบล็อกเชนใน Listbox"""
        self.blockchain_listbox.delete(0, tk.END)
        try:
            conn = sqlite3.connect(self.blockchain.db_name)
            cursor = conn.cursor()
            cursor.execute('SELECT "index", message, hash, timestamp FROM blocks')
            rows = cursor.fetchall()
            for row in rows:
                display_text = f"Index: {row[0]} | Hash: {row[2]} | Time: {row[3]}"
                self.blockchain_listbox.insert(tk.END, display_text)
            conn.close()
        except sqlite3.Error as e:
            print(f"Error fetching blockchain data: {e}")

    def create_wallet_tab(self):
        """Create the wallet tab in the UI."""
        # Ensure that wallet_info has been loaded with default values if not already set
        if not hasattr(self, 'wallet_info'):
            self.wallet_info = {"address": "Unknown", "balance": 0, "private_key": "Not Available"}  # Default to prevent errors

        # Create the wallet UI components
        wallet_label = tk.Label(self.wallet_tab, text="Wallet Address: ", font=("Arial", 12))
        wallet_label.pack(pady=5)

        wallet_address_label = tk.Label(self.wallet_tab, text=self.wallet_info["address"], font=("Arial", 12))
        wallet_address_label.pack(pady=5)

        balance_label = tk.Label(self.wallet_tab, text=f"Balance: {self.wallet_info['balance']} PUK", font=("Arial", 12))
        balance_label.pack(pady=5)

        # Create frame for displaying wallet info
        self.info_frame = tk.Frame(self.wallet_tab, bg="#ffffff", bd=2, relief="solid")
        self.info_frame.pack(fill="x", padx=20, pady=20)

        # Fetch wallet info from the database and update the UI accordingly
        self.wallet_info = self.get_wallet_info()  # Assuming this method fetches data and updates self.wallet_info

        # Display updated wallet info
        self.wallet_balance_label = tk.Label(
            self.info_frame,
            text=f"ยอดคงเหลือ: {self.wallet_info['balance']} เหรียญ",
            font=("Helvetica", 14, "bold"),
            bg="#ffffff",
            fg="#333"
        )
        self.wallet_balance_label.pack(pady=10)

        self.wallet_address_label = tk.Label(
            self.info_frame,
            text=f"ที่อยู่กระเป๋า: {self.wallet_info['address']}",
            font=("Helvetica", 12),
            bg="#ffffff",
            fg="#555"
        )
        self.wallet_address_label.pack(pady=5)

        self.private_key_label = tk.Label(
            self.info_frame,
            text=f"คีย์ส่วนตัว: {self.wallet_info['private_key']}",
            font=("Helvetica", 8),
            bg="#ffffff",
            fg="#555"
        )
        self.private_key_label.pack(pady=5)

        # Create frame for buttons
        self.button_frame = tk.Frame(self.wallet_tab, bg="#f4f4f9")
        self.button_frame.pack(fill="x", padx=20, pady=20)

        # Create the button widgets
        self.refresh_button = ttk.Button(
            self.button_frame,
            text="🔄 รีเฟรชยอดเงิน",
            command=self.refresh_balance
        )
        self.refresh_button.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.copy_private_key_button = ttk.Button(
            self.button_frame,
            text="📋 คัดลอกคีย์ส่วนตัว",
            command=self.copy_private_key
        )
        self.copy_private_key_button.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.create_wallet_button = ttk.Button(
            self.button_frame,
            text="➕ สร้างกระเป๋าใหม่",
            command=self.create_new_wallet
        )
        self.create_wallet_button.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        self.transfer_button = ttk.Button(
            self.button_frame,
            text="💸 โอนเหรียญ",
            command=self.transfer_funds
        )
        self.transfer_button.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        self.use_existing_wallet_button = ttk.Button(
            self.button_frame,
            text="🔑 ใช้กระเป๋าเดิม",
            command=self.use_existing_wallet
        )
        self.use_existing_wallet_button.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # Make the grid columns expand evenly
        self.button_frame.grid_columnconfigure(0, weight=1)
        self.button_frame.grid_columnconfigure(1, weight=1)

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
            """อัปเดตยอดเงินในกระเป๋าเมื่อคลิกปุ่มรีเฟรส"""
            new_balance = self.blockchain.check_balance()  # สมมติว่า blockchain มีฟังก์ชัน check_balance()
            self.wallet_balance_label.config(text=f"ยอดคงเหลือ: {new_balance} เหรียญ")  # อัปเดตข้อความแสดงยอดเงิน

    def create_new_wallet(self):
            """สร้างกระเป๋าใหม่และอัพเดตข้อมูลในฐานข้อมูล"""
            wallet_address = self.generate_wallet_address()  # สร้างที่อยู่กระเป๋าใหม่
            private_key = self.generate_private_key()  # สร้างคีย์ส่วนตัวใหม่
            
            # บันทึกข้อมูลกระเป๋าใหม่ในฐานข้อมูล
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO wallets (wallet_address, balance, private_key) VALUES (?, ?, ?)",
                        (wallet_address, 0.0, private_key))  # บันทึกด้วยยอดเงิน 0
            conn.commit()
            conn.close()

            # อัพเดตข้อมูลกระเป๋าใหม่ใน UI
            self.wallet_info = {
                "wallet_address": wallet_address,
                "balance": 0.0,
                "private_key": private_key
            }
            self.wallet_address_label.config(text=wallet_address)  # อัพเดตแสดงที่อยู่
            self.private_key_value_label.config(text=private_key)  # อัพเดตแสดงคีย์ส่วนตัว

            # แสดงข้อความแจ้งเตือน
            messagebox.showinfo("Wallet Created", "New wallet created successfully!")

    def copy_private_key(self):
            """Copies the private key to the clipboard"""
            pyperclip.copy(self.blockchain.private_key)
            print("คีย์ส่วนตัวถูกคัดลอกแล้ว!")  # Inform the user that the key has been copied

    def update_wallet_info(self):
        """Update wallet information on the UI"""
        self.wallet_balance_label.config(text=f"ยอดคงเหลือ: {self.wallet_info['balance']} เหรียญ")
        self.wallet_address_label.config(text=f"ที่อยู่กระเป๋า: {self.wallet_info['address']}")
        self.private_key_label.config(text=f"คีย์ส่วนตัว: {self.wallet_info['private_key']}")

    def transfer_funds(self):
        """เปิดหน้าต่างโอนเหรียญ"""
        transfer_window = tk.Toplevel(self.root)
        transfer_window.title("โอนเหรียญ")
        transfer_window.geometry("400x300")

        to_address_label = tk.Label(transfer_window, text="ที่อยู่ปลายทาง:")
        to_address_label.pack(pady=5)
        to_address_entry = tk.Entry(transfer_window, width=30)
        to_address_entry.pack(pady=5)

        amount_label = tk.Label(transfer_window, text="จำนวนเหรียญ:")
        amount_label.pack(pady=5)
        amount_entry = tk.Entry(transfer_window, width=30)
        amount_entry.pack(pady=5)

        key_label = tk.Label(transfer_window, text="คีย์ส่วนตัว:")
        key_label.pack(pady=5)
        key_entry = tk.Entry(transfer_window, show="*", width=30)
        key_entry.pack(pady=5)

        def execute_transfer():
            """ฟังก์ชันสำหรับดำเนินการโอนเหรียญ"""
            to_address = to_address_entry.get()
            amount = float(amount_entry.get())
            key = key_entry.get()
            if self.blockchain.transfer_funds(amount, to_address, key):
                messagebox.showinfo("สำเร็จ", "โอนเหรียญสำเร็จ")
                transfer_window.destroy()
            else:
                messagebox.showerror("ข้อผิดพลาด", "การโอนเหรียญไม่สำเร็จ")

        transfer_button = tk.Button(transfer_window, text="โอน", command=execute_transfer)
        transfer_button.pack(pady=10)

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
        self.message_label = tk.Label(self.message_tab, text="Enter your message:", bg="#f4f4f9")
        self.message_label.pack(pady=10)

        # เปลี่ยนจาก Entry เป็น Text เพื่อให้สามารถเขียนหลายบรรทัด
        self.message_text = tk.Text(self.message_tab, width=100, height=35)  # กำหนดให้มี 20 บรรทัด
        self.message_text.pack(pady=10)

        # ปุ่มสำหรับบันทึกข้อความ
        self.save_button = tk.Button(self.message_tab, text="Save Message", command=self.save_message)
        self.save_button.pack(pady=10)

        # ปุ่มสำหรับล้างข้อความ
        self.clear_button = tk.Button(self.message_tab, text="Clear Text", command=self.clear_message)
        self.clear_button.pack(pady=10)

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

            # จำนวนเหรียญที่ต้องการโอน (เช่น โอน 5 เหรียญ)
            amount_to_transfer = 5
            
            # ใช้ที่อยู่และคีย์ส่วนตัวจากกระเป๋าที่สร้างไว้แล้ว
            to_address = self.blockchain.wallet_address  # ใช้ที่อยู่กระเป๋าของระบบเป็นที่อยู่ปลายทาง
            private_key = self.blockchain.private_key  # ใช้คีย์ส่วนตัวของกระเป๋าที่สร้าง

            # โอนเหรียญ
            if self.blockchain.transfer_funds(amount_to_transfer, to_address, private_key):
                # ถ้าโอนเหรียญสำเร็จ แสดงข้อความแจ้งเตือน
                messagebox.showinfo("Success", f"Message saved and {amount_to_transfer} coins transferred.")
            else:
                # ถ้าโอนเหรียญล้มเหลว แสดงข้อความผิดพลาด
                messagebox.showerror("Error", "Failed to transfer coins.")
        else:
            # ถ้าข้อความว่าง แสดงข้อความเตือนให้กรอกข้อความ
            messagebox.showwarning("Input Error", "Please enter a message.")
        
    def create_transactions_tab(self):
        # สร้างส่วนแสดงธุรกรรม
        self.transactions_list = tk.Listbox(self.transactions_tab, width=80, height=20)
        self.transactions_list.pack(pady=10)

        # ปุ่ม Refresh
        refresh_button = tk.Button(
            self.transactions_tab, 
            text="รีเฟรช", 
            command=self.refresh_transactions_list
        )
        refresh_button.pack(pady=5)

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

    def create_detail_tab(self):
        """สร้างแท็บรายละเอียดและแสดงข้อมูลเกี่ยวกับการทำงานของโปรแกรม"""
        # แสดงข้อความหัวข้อ "Detail Information"
        label = tk.Label(self.detail_tab, text="Detail Information", font=("Arial", 16, "bold"))
        label.pack(padx=10, pady=10)

        # สร้างเฟรมสำหรับ Text widget และ Scrollbar
        frame = tk.Frame(self.detail_tab)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # สร้าง Scrollbar
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # สร้าง Text widget เพื่อแสดงข้อมูลรายละเอียด
        detail_text = tk.Text(frame, wrap=tk.WORD, height=20, width=80, yscrollcommand=scrollbar.set)
        detail_text.insert(tk.END, """ขั้นตอนการทำงานของโปรแกรมบันทึกข้อความบนบล็อกเชน:
    1. การเริ่มต้นระบบ
        - ตรวจสอบฐานข้อมูลและสร้าง Genesis Block หากไม่มีบล็อกในระบบ
    2. การบันทึกข้อความ
        - ผู้ใช้ป้อนข้อความ ระบบสร้างบล็อกใหม่พร้อมข้อมูลที่จำเป็น (Index, Message, Timestamp, Previous Hash, Current Hash)
    3. การแสดงข้อมูลในบล็อกเชน
        - แสดงรายการบล็อกทั้งหมด พร้อมรายละเอียดเมื่อเลือกดู
    4. การตรวจสอบความถูกต้องของบล็อกเชน
        - ตรวจสอบการเชื่อมโยงของ Previous Hash และแจ้งเตือนหากพบปัญหา
    5. การออกแบบระบบอินเตอร์เฟซ
        - ช่องอินพุต ข้อมูลบล็อก และหน้าต่างแสดงรายละเอียด
    6. การจัดการฐานข้อมูล
        - ใช้ SQLite ในการจัดเก็บข้อมูลบล็อก
    7. การปิดโปรแกรม
        - บันทึกสถานะและปิดการเชื่อมต่อฐานข้อมูล

    ภาพรวมการทำงาน:
    - ปลอดภัย: ข้อมูลไม่สามารถแก้ไขได้
    - โปร่งใส: ตรวจสอบได้ทุกเมื่อ
    - เรียบง่าย: ใช้งานง่าย
    - ตรวจสอบได้: มีระบบตรวจสอบความสมบูรณ์ของข้อมูล
    """)
        detail_text.config(state=tk.DISABLED)  # ป้องกันการแก้ไขข้อความใน Text widget
        detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # เชื่อม Scrollbar กับ Text widget
        scrollbar.config(command=detail_text.yview)

        # เพิ่มปุ่มเพื่อแสดงรายละเอียด
        button = tk.Button(self.detail_tab, text="Show Details", command=self.save_details)
        button.pack(pady=5)

    def save_details(self):
        print("This's Details!")

if __name__ == "__main__":
    root = tk.Tk()
    app = WalletApp(root)
    root.mainloop()
