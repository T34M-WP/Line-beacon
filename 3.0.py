import re
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

user_sessions = {}

# ตั้งค่าการเชื่อมต่อกับฐานข้อมูล PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:123456@localhost/test_beacon'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# สร้าง instance ของ SQLAlchemy
db = SQLAlchemy(app)

# Token สำหรับดึงข้อมูลโปรไฟล์ LINE และส่งข้อความ
LINE_CHANNEL_ACCESS_TOKEN = "yUkSAFq8OrTXaPA7t7N37c4vZ1widgppiBfOSh9iMwNOHQxus+JZ0SFJkZLDARzy9DyrWj0GEmn6VdULQof2QzJDZgmjgOsa4+E9kKA5EzeAMCTYEjLHdXKnWBsxz5HVxwcn60GU4iMk3Xdk4BRFXAdB04t89/1O/w1cDnyilFU="
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
LINE_PROFILE_URL = "https://api.line.me/v2/bot/profile/"

# ตาราง UserProfile
class UserProfile(db.Model):
    __tablename__ = 'user_profile'  # กำหนดชื่อตารางในฐานข้อมูลให้ชัดเจน
    userId = db.Column(db.String(50), primary_key=True)  # userId เป็น Primary Key
    Student_ID = db.Column(db.String(100), nullable=True)
    
    def __repr__(self):
        return f'<UserProfile {self.userId}>'

# โมเดลฐานข้อมูล BeaconEvent
class BeaconEvent(db.Model):
    __tablename__ = 'beacon_event'
    id = db.Column(db.Integer, primary_key=True)
    hwId = db.Column(db.String(50), nullable=False)
    userId = db.Column(db.String(50), db.ForeignKey('user_profile.userId'), nullable=False)  # เชื่อมโยงกับ UserProfile
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user_profile = db.relationship('UserProfile', backref='beacon_events')  # เชื่อมโยงกับ UserProfile ผ่าน userId

    def __repr__(self):
        return f'<BeaconEvent {self.id}>'

# ฟังก์ชันส่งข้อความกลับไปยังผู้ใช้
def reply_to_user(reply_token, message):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {"replyToken": reply_token, "messages": [{"type": "text", "text": message}]}

    try:
        response = requests.post(LINE_REPLY_URL, headers=headers, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {e}")

# ฟังก์ชันดึงข้อมูลโปรไฟล์จาก LINE
def get_line_user_profile(user_id):
    headers = {"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"}

    try:
        response = requests.get(f"{LINE_PROFILE_URL}{user_id}", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching LINE profile: {e}")
        return None

# ฟังก์ชันตรวจสอบรหัสนักศึกษา
def validate_student_id(user_message, year_suffix, user_id, reply_token):
    if re.fullmatch(r"\d{8}", user_message):  
        student_prefix = int(user_message[:2])

        if student_prefix <= year_suffix:
            existing_user = UserProfile.query.filter_by(userId=user_id).first()
            if existing_user:
                existing_user.Student_ID = user_message  # อัปเดต displayName ของ UserProfile
                db.session.commit()
                reply_to_user(reply_token, f"อัปเดตชื่อเป็นรหัสนักศึกษา {user_message} สำเร็จ!")
            else:
                reply_to_user(reply_token, "ไม่พบข้อมูลของคุณในระบบ กรุณาเชื่อมต่อ Beacon ก่อนแล้วลองใหม่อีกครั้ง")
        else:
            reply_to_user(reply_token, f"รหัสนักศึกษาของคุณไม่ถูกต้อง กรุณากรอกหมายเลขที่ขึ้นต้นด้วยตัวเลขไม่เกิน {year_suffix}")
    else:
        reply_to_user(reply_token, "กรุณากรอกรหัสนักศึกษาที่ถูกต้อง (ต้องเป็นตัวเลข 8 หลักเท่านั้น)")

    return jsonify({"message": "DisplayName update attempt"}), 200

# Webhook รับข้อมูลจาก LINE
@app.route('/line-webhook', methods=['POST'])
def line_webhook():
    try:
        data = request.json

        if not data or 'events' not in data:
            return jsonify({"message": "Invalid event or missing data"}), 400

        current_year = datetime.now().year + 543
        year_suffix = current_year % 100  # เอา 2 หลักสุดท้ายของปี พ.ศ.

        for event in data['events']:
            event_type = event.get('type')

            # ตรวจจับข้อความจากผู้ใช้
            if event_type == 'message' and event['message']['type'] == 'text':
                user_id = event['source']['userId']
                user_message = event['message']['text'].strip()
                reply_token = event['replyToken']

                # เช็คว่าผู้ใช้ต้องการเปลี่ยนชื่อ
                if user_message.lower() == "เปลี่ยนชื่อผู้ใช้":
                    user_sessions[user_id] = "waiting_for_student_id"  # บันทึกสถานะผู้ใช้
                    reply_to_user(reply_token, "กรุณากรอกรหัสนักศึกษา 8 หลัก เพื่อเปลี่ยนชื่อผู้ใช้")
                    return jsonify({"message": "Waiting for new displayName"}), 200

                # ถ้าผู้ใช้ยังอยู่ในโหมด "waiting_for_student_id"
                if user_sessions.get(user_id) == "waiting_for_student_id":
                    if user_message.isnumeric() and len(user_message) == 8 and int(user_message[:2]) <= 68:
                        del user_sessions[user_id]  # ลบสถานะผู้ใช้หลังจากได้รับรหัสที่ถูกต้อง
                        return validate_student_id(user_message, year_suffix, user_id, reply_token)
                    else:
                        reply_to_user(reply_token, 
                            f"รหัสนักศึกษาของคุณไม่ถูกต้อง\n"
                            f"รหัสนักศึกษาต้องเป็นตัวเลข 8 หลัก\n"
                            f"ตัวอย่างที่ถูกต้อง: {year_suffix}12345, {year_suffix}56789\n"
                            f"โดย 2 หลักแรกต้องไม่เกิน {year_suffix}\n"
                            f"\nกรุณาลองใหม่อีกครั้ง!")
                        
                        # **ไม่ลบ user_sessions[user_id] เพื่อให้ยังอยู่ในโหมดรอรหัส**
                        return jsonify({"message": "Invalid student ID"}), 400


                    
            # ตรวจจับอีเวนต์จาก Beacon
            elif event_type == 'beacon':
                hwId = event['beacon'].get('hwid')
                userId = event['source'].get('userId')
                timestamp = event.get('timestamp')
                reply_token = event['replyToken']

                if not hwId or not userId or timestamp is None:
                    return jsonify({"message": "Missing beacon data"}), 400

                event_time = datetime.fromtimestamp(timestamp / 1000, timezone.utc)
                print(f"Received timestamp: {timestamp}, Converted datetime: {event_time = }")

                existing_event = BeaconEvent.query.filter_by(hwId=hwId, userId=userId).order_by(BeaconEvent.timestamp.desc()).first()

                utc_plus_7 = timezone(timedelta(hours=7))
                if existing_event and (event_time - existing_event.timestamp.replace(tzinfo=utc_plus_7)) < timedelta(minutes=1):
                    return jsonify({"message": "Duplicate event, ignored"}), 200  # ใช้ return แทน continue

                profile = get_line_user_profile(userId)
                Student_ID = profile.get("displayName", "Unknown User") if profile else "Unknown User"

                pattern = r"(\d{8})"# หาเลข 8 หลักที่เป็นคำสมบูรณ์
                match = re.search(pattern, Student_ID)
                
                if match:
                    student_id = match.group()  # ดึงเลข 8 หลักจากข้อความ
                    student_prefix = int(student_id[:2])

                    if student_prefix <= year_suffix:
                        # ฟังก์ชันตรวจสอบและเพิ่มข้อมูลใน UserProfile
                        def add_or_update_user_profile(user_id, student_id):
                            user_profile = UserProfile.query.filter_by(userId=user_id).first()

                            if user_profile:
                                if user_profile.Student_ID == student_id:
                                    print(f"ผู้ใช้ {user_id} มีรหัสนักศึกษา {student_id} อยู่แล้ว ไม่ต้องอัปเดต")
                                    return None  # ไม่ต้องอัปเดตข้อมูล
                                else:
                                    user_profile.Student_ID = student_id
                                    db.session.commit()
                                    print(f"อัปเดตข้อมูลผู้ใช้ {user_id} ให้มีรหัสนักศึกษา {student_id}")
                                    return False  # False = อัปเดตข้อมูล
                            else:
                                # ถ้ายังไม่มี ให้เพิ่มข้อมูลใหม่
                                user_profile = UserProfile(userId=user_id, Student_ID=student_id)
                                db.session.add(user_profile)
                                db.session.commit()
                                print(f"เพิ่มข้อมูลผู้ใช้ {user_id} ลงฐานข้อมูลสำเร็จ")
                                return True  # True = ผู้ใช้ใหม่

                        is_new_user = add_or_update_user_profile(userId, student_id)

                        if is_new_user is None:
                            reply_to_user(reply_token, f"เช็คชื่อเข้าเรียนสำเร็จ!\nคุณ {student_id}")
                        elif is_new_user:
                            reply_to_user(reply_token, f"เช็คชื่อเข้าเรียนสำเร็จ!\nยินดีต้อนรับคุณ {student_id} เข้าสู่ระบบ ")
                        else:
                            reply_to_user(reply_token, f"เช็คชื่อเข้าเรียนสำเร็จ!\nข้อมูลของคุณถูกเปลี่ยนเป็น {student_id} แล้ว ")

                    else:
                        reply_to_user(reply_token, 
                                    f"เช็คชื่อเข้าเรียนสำเร็จ! คุณ {Student_ID}\n"
                                    f"รหัสนักศึกษาของคุณไม่ถูกต้อง กรุณากรอกรหัสที่ขึ้นต้นด้วยตัวเลขไม่เกิน {year_suffix}")

                else:
                    reply_to_user(reply_token, 
                                f"เช็คชื่อเข้าเรียนสำเร็จ! คุณ {Student_ID}\n"
                                f"กรุณากรอกรหัสนักศึกษา 8 หลัก เพื่ออัปเดตข้อมูลของคุณ")

                # บันทึก BeaconEvent เฉพาะเมื่อไม่ใช่เหตุการณ์ซ้ำ
                new_event = BeaconEvent(hwId=hwId, userId=userId, timestamp=event_time)
                db.session.add(new_event)
                db.session.commit()


        return jsonify({"message": "Event processed"}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"message": "An error occurred", "error": str(e)}), 500

# เริ่มเซิร์ฟเวอร์ Flask
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)