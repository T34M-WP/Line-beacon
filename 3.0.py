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
    displayName = db.Column(db.String(100), nullable=True)
    
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
                if existing_user.displayName != user_message:  # เช็คว่า displayName ไม่ตรงกับ student_id เดิม
                    existing_user.displayName = user_message  # อัปเดต displayName ของ UserProfile
                    db.session.commit()
                    reply_to_user(reply_token, f"อัปเดตชื่อเป็นรหัสนักศึกษา {user_message} สำเร็จ!")
                else:
                    reply_to_user(reply_token, "รหัสนักศึกษาของคุณตรงกับข้อมูลในระบบแล้ว ไม่มีการบันทึกใหม่!")
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

                if user_message.lower() == "เปลี่ยนชื่อผู้ใช้":
                    user_sessions[user_id] = "waiting_for_student_id"  # บันทึกสถานะผู้ใช้
                    reply_to_user(reply_token, "กรุณากรอกรหัสนักศึกษา 8 หลัก เพื่อเปลี่ยนชื่อผู้ใช้")
                    return jsonify({"message": "Waiting for new displayName"}), 200

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
                displayName = profile.get("displayName", "Unknown User") if profile else "Unknown User"


                def save_beacon_event(hwId, userId, event_time, test):
                    existing_user = UserProfile.query.filter_by(userId=userId).first()
                    if not existing_user:
                        new_user = UserProfile(userId=userId, displayName=test)
                        db.session.add(new_user)
                        db.session.commit()
                    else:
                        existing_user.displayName = test
                    
                    # บันทึก BeaconEvent
                    new_event = BeaconEvent(hwId=hwId, userId=userId, timestamp=event_time)
                    db.session.add(new_event)
                    db.session.commit()

                existing_user = UserProfile.query.filter_by(userId=userId).first()
                pattern = r"(\d{8})"# หาเลข 8 หลักที่เป็นคำสมบูรณ์
                match = re.search(pattern, displayName)

                if match:
                    student_id = match.group()  # ดึงเลข 8 หลักจากข้อความ
                    student_prefix = int(student_id[:2])

                    if student_prefix <= year_suffix:
                        reply_to_user(reply_token, f"✅ เช็คชื่อเข้าเรียนสำเร็จ! 👤 คุณ {student_id}")
                        print(f"student_prefix <= year_suffix")
                    
                        save_beacon_event(hwId, userId, event_time, student_id)
                    else:
                        if existing_user and existing_user.displayName.isdigit() and len(existing_user.displayName) == 8:
                            reply_to_user(reply_token, 
                                    f"✅ เช็คชื่อเข้าเรียนสำเร็จ! 👤 คุณ {existing_user.displayName}")
                        else:
                            reply_to_user(reply_token, 
                                        f"✅ เช็คชื่อเข้าเรียนสำเร็จ! 👤 คุณ {displayName}\n"
                                        f"⚠️ รหัสนักศึกษาของคุณไม่ถูกต้อง กรุณากรอกรหัสที่ขึ้นต้นด้วยตัวเลขไม่เกิน {year_suffix}")
                        if existing_user :
                            new_event = BeaconEvent(hwId=hwId, userId=userId, timestamp=event_time)
                            db.session.add(new_event)
                            db.session.commit()
                        else:
                            save_beacon_event(hwId, userId, event_time, student_id)
                        
                else:
                    # ตรวจสอบว่า displayName ในฐานข้อมูลคือ student_id หรือไม่
                    if existing_user and existing_user.displayName.isdigit() and len(existing_user.displayName) == 8:
                        # ถ้า displayName เป็นรหัสนักศึกษา 8 หลักแล้ว จะไม่ส่งข้อความขอรหัส
                        print(f"User {userId} has student ID as displayName")
                        save_beacon_event(hwId, userId, event_time, existing_user.displayName)
                        reply_to_user(reply_token, 
                                    f"✅ เช็คชื่อเข้าเรียนสำเร็จ! 👤 คุณ {existing_user.displayName}")
                    else:
                        save_beacon_event(hwId, userId, event_time, displayName)
                        reply_to_user(reply_token, 
                                    f"✅ เช็คชื่อเข้าเรียนสำเร็จ! 👤 คุณ {displayName}\n"
                                    f"⚠️ กรุณากรอกรหัสนักศึกษา 8 หลัก เพื่ออัปเดตข้อมูลของคุณ")


              
        return jsonify({"message": "Event processed"}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"message": "An error occurred", "error": str(e)}), 500

# เริ่มเซิร์ฟเวอร์ Flask
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
