import sqlite3
import hashlib
import uuid
import tkinter as tk
from tkinter import messagebox, ttk
import pyperclip  # เพิ่มไลบรารี pyperclip
from tkinter import Menu
from datetime import datetime




class Blockchain:
    def __init__(self, db_name, wallet_address=None, private_key=None):
        self.chain = []
        self.mempool = []  # เก็บธุรกรรมที่รอการยืนยัน
        self.wallet_address = "receiver_wallet_address"  # ที่อยู่กระเป๋าผู้รับ
        self.private_key = "private_key_example"  # ตัวอย่างคีย์ส่วนตัว
        self.db_name = db_name
        self.wallet_balance = 0  # ยอดเงินในกระเป๋า
        self.reward_amount = 10  # รางวัลเมื่อปิดบล็อกสำเร็จ
        self.wallet_address = wallet_address or self.generate_new_wallet_address()  # ถ้าไม่มีที่อยู่เดิม สร้างใหม่
        self.private_key = private_key or self.generate_private_key()  # ถ้าไม่มีคีย์ส่วนตัว สร้างใหม่
        self.create_table()
        self.create_genesis_block()
        self.create_transactions_table()

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




    def create_genesis_block(self):
        """สร้างบล็อกแรก (Genesis Block)"""
        if not self.chain:
            # เนื้อหาข้อความสำหรับ Genesis Block
            genesis_message = (
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
                "โปรแกรมนี้ผสมผสานระหว่างความเรียบง่ายและความปลอดภัยสูงเพื่อรองรับการใช้งานที่เชื่อถือได้."
            )

            # สร้าง Genesis Block
            genesis_block = {
                "index": 0,
                "message": genesis_message,
                "transactions": [],  # Genesis Block ไม่มีธุรกรรม
                "hash": "0"
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

    def save_transaction_to_db(self, from_address, to_address, amount, block_index=None):
        """บันทึกข้อมูลธุรกรรมลงในฐานข้อมูล"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO transactions (timestamp, from_address, to_address, amount, block_index)
                    VALUES (datetime("now"), ?, ?, ?, ?)
                ''', (from_address, to_address, amount, block_index))
                conn.commit()
                print("บันทึกธุรกรรมสำเร็จ")
        except sqlite3.Error as e:
            print(f"Error saving transaction to database: {e}")


    def give_reward(self):
        """ให้รางวัลเมื่อปิดบล็อกสำเร็จ"""
        print("ให้รางวัลแล้ว!")
        self.wallet_balance += self.reward_amount
        print(f"ได้รับรางวัล {self.reward_amount} เหรียญ! ยอดคงเหลือปัจจุบัน: {self.wallet_balance} เหรียญ")

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


class WalletApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ChainLogger #PUKUMPee V.1.0.0")
        self.root.geometry("650x550")
        self.blockchain = Blockchain("blockchain.db", "your_wallet_address_here", "your_private_key_here")

        self.create_ui()


    def create_ui(self):
        self.main_frame = tk.Frame(self.root, bg="#f4f4f9")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        # Text Widget สำหรับข้อความหลายบรรทัด
        self.message_text = tk.Text(self.root, width=50, height=20)  # 50 ตัวอักษรต่อบรรทัด, 20 บรรทัด
        self.message_text.pack(pady=10)

        
        # Create tabs
        self.tab_control = ttk.Notebook(self.main_frame)

        self.blockchain_tab = ttk.Frame(self.tab_control)
        self.wallet_tab = ttk.Frame(self.tab_control)
        self.message_tab = ttk.Frame(self.tab_control)  # Tab for saving message
        self.detail_tab = ttk.Frame(self.tab_control)  # Tab for saving message

        self.tab_control.add(self.blockchain_tab, text="Blockchain Info")
        self.tab_control.add(self.wallet_tab, text="Wallet Details")
        self.tab_control.add(self.message_tab, text="Save Message")  # Add tab for saving messages
        self.tab_control.add(self.detail_tab, text="Detail")  # Add tab for saving messages

        self.tab_control.pack(expand=1, fill="both")

        self.create_blockchain_tab()
        self.create_wallet_tab()
        self.create_message_tab()  # New function to create the "Save Message" UI
        self.create_detail_tab()



    def create_blockchain_tab(self):
        self.blockchain_listbox = tk.Listbox(self.blockchain_tab, height=20, width=100)
        self.blockchain_listbox.pack(pady=10)

        # แสดงข้อมูลบล็อกเชน
        self.update_blockchain_list()

        self.update_button = tk.Button(self.blockchain_tab, text="อัพเดตข้อมูล", command=self.update_blockchain_list)
        self.update_button.pack(pady=10)

        # เพิ่มการคลิกที่รายการใน Listbox
        self.blockchain_listbox.bind("<ButtonRelease-1>", self.show_block_details)

    def show_block_details(self, event):
        """แสดงข้อความทั้งหมดของบล็อกที่เลือกในหน้าต่างใหม่"""
        selected_index = self.blockchain_listbox.curselection()  # หาว่าคลิกที่รายการไหน
        if selected_index:
            index = selected_index[0]  # ดึง index ของรายการที่เลือก
            try:
                conn = sqlite3.connect(self.blockchain.db_name)
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

        # แสดงแฮชของบล็อก
        hash_label = tk.Label(
            new_window,
            text=f"Hash: {block_hash}",
            bg="#2c3e50",  # สีพื้นหลัง
            fg="white",  # สีตัวอักษร
            font=("Helvetica", 10),
            pady=10,
        )
        hash_label.pack(fill=tk.X, padx=10, pady=(10, 0))  # จัดให้ชิดขอบและมีระยะห่าง



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
        # แสดงรายละเอียดกระเป๋า
        self.wallet_balance_label = tk.Label(self.wallet_tab, text=f"ยอดคงเหลือ: {self.blockchain.wallet_balance} เหรียญ",
                                             font=("Helvetica", 12), bg="#f4f4f9")
        self.wallet_balance_label.pack(pady=10)

        self.wallet_address_label = tk.Label(self.wallet_tab, text=f"ที่อยู่กระเป๋า: {self.blockchain.wallet_address}",
                                             font=("Helvetica", 12), bg="#f4f4f9")
        self.wallet_address_label.pack(pady=10)

        self.private_key_label = tk.Label(self.wallet_tab, text=f"คีย์ส่วนตัว: {self.blockchain.private_key}",
                                          font=("Helvetica", 12), bg="#f4f4f9")
        self.private_key_label.pack(pady=10)

        # ปุ่มสำหรับสร้างกระเป๋าใหม่
        self.create_wallet_button = tk.Button(self.wallet_tab, text="สร้างกระเป๋าใหม่", command=self.create_new_wallet)
        self.create_wallet_button.pack(pady=10)

        # ปุ่มสำหรับโอนเหรียญ
        self.transfer_button = tk.Button(self.wallet_tab, text="โอนเหรียญ", command=self.transfer_funds)
        self.transfer_button.pack(pady=10)

        # ปุ่มสำหรับเลือกกระเป๋าเดิม
        self.use_existing_wallet_button = tk.Button(self.wallet_tab, text="ใช้กระเป๋าเดิม", command=self.use_existing_wallet)
        self.use_existing_wallet_button.pack(pady=10)

    def create_new_wallet(self):
        """สร้างกระเป๋าใหม่"""
        self.blockchain = Blockchain("blockchain.db")  # สร้าง Blockchain ใหม่
        self.update_wallet_info()

    def update_wallet_info(self):
        """อัพเดตข้อมูลในหน้าจอ"""
        self.wallet_balance_label.config(text=f"ยอดคงเหลือ: {self.blockchain.wallet_balance} เหรียญ")
        self.wallet_address_label.config(text=f"ที่อยู่กระเป๋า: {self.blockchain.wallet_address}")
        self.private_key_label.config(text=f"คีย์ส่วนตัว: {self.blockchain.private_key}")

    def transfer_funds(self):
        """เปิดหน้าต่างโอนเหรียญ"""
        transfer_window = tk.Toplevel(self.root)
        transfer_window.title("โอนเหรียญ")
        transfer_window.geometry("400x200")

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
        """เลือกกระเป๋าเดิมโดยการใส่คีย์ส่วนตัว"""
        key_input_window = tk.Toplevel(self.root)
        key_input_window.title("ใส่คีย์ส่วนตัว")
        key_input_window.geometry("400x200")

        key_label = tk.Label(key_input_window, text="คีย์ส่วนตัว:")
        key_label.pack(pady=5)
        key_entry = tk.Entry(key_input_window, show="*", width=30)
        key_entry.pack(pady=5)

        def verify_key():
            """ตรวจสอบคีย์ส่วนตัว"""
            input_key = key_entry.get()
            if input_key == self.blockchain.private_key:
                self.update_wallet_info()
                messagebox.showinfo("สำเร็จ", "คีย์ส่วนตัวถูกต้อง")
                key_input_window.destroy()
            else:
                messagebox.showerror("ข้อผิดพลาด", "คีย์ส่วนตัวไม่ถูกต้อง")

        verify_button = tk.Button(key_input_window, text="ยืนยัน", command=verify_key)
        verify_button.pack(pady=10)

    def create_message_tab(self):
        """Create UI for saving messages and transferring funds"""
        self.message_label = tk.Label(self.message_tab, text="Enter your message:", bg="#f4f4f9")
        self.message_label.pack(pady=10)

        # เปลี่ยนจาก Entry เป็น Text เพื่อให้สามารถเขียนหลายบรรทัด
        self.message_text = tk.Text(self.message_tab, width=50, height=20)  # กำหนดให้มี 20 บรรทัด
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


    def create_message_tab(self):
        """Create UI for saving messages and transferring funds"""
        self.message_label = tk.Label(self.message_tab, text="Enter your message:", bg="#f4f4f9")
        self.message_label.pack(pady=10)

        # เปลี่ยนจาก Entry เป็น Text เพื่อให้สามารถเขียนหลายบรรทัด
        self.message_text = tk.Text(self.message_tab, width=50, height=20)  # กำหนดให้มี 20 บรรทัด
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
        message = self.message_text.get("1.0", tk.END).strip()  # ใช้ self.message_text แทน self.message_entry
        if message:
            self.blockchain.add_block(message)  # Add the message as a new block

            # Transfer funds (for example, transferring 5 coins to an address)
            amount_to_transfer = 5
            to_address = self.blockchain.wallet_address  # ใช้ที่อยู่กระเป๋าของระบบเป็นที่อยู่ปลายทาง
            private_key = self.blockchain.private_key  # ใช้คีย์ส่วนตัวของกระเป๋าที่สร้าง

            # Transfer funds
            if self.blockchain.transfer_funds(amount_to_transfer, to_address, private_key):
                messagebox.showinfo("Success", f"Message saved and {amount_to_transfer} coins transferred.")
            else:
                messagebox.showerror("Error", "Failed to transfer coins.")
        else:
            messagebox.showwarning("Input Error", "Please enter a message.")
        

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
