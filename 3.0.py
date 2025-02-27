import re
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

user_sessions = {}

# ตั้งค่าการเชื่อมต่อกับฐานข้อมูล PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:123456@localhost/test_beacon'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False



# Token สำหรับดึงข้อมูลโปรไฟล์ LINE และส่งข้อความ
LINE_CHANNEL_ACCESS_TOKEN = "yUkSAFq8OrTXaPA7t7N37c4vZ1widgppiBfOSh9iMwNOHQxus+JZ0SFJkZLDARzy9DyrWj0GEmn6VdULQof2QzJDZgmjgOsa4+E9kKA5EzeAMCTYEjLHdXKnWBsxz5HVxwcn60GU4iMk3Xdk4BRFXAdB04t89/1O/w1cDnyilFU="
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
LINE_PROFILE_URL = "https://api.line.me/v2/bot/profile/"
BASE_URL = "http://192.168.70.6:3000/api"  # URL ของ API ที่ใช้ในการดึงข้อมูลโปรไฟล์และอัพเดทข้อมูล
API_ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImJlYWNvbiIsInJvbGUiOiJ1c2VyIiwiaWF0IjoxNzQwNjUyMTkzLCJleHAiOjE3NzIyMDk3OTN9.eQJWpm0OlJq01XOT2nPxatlXCDeydapufgTXWboEUjQ"

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

def get_user_profile_from_api(user_id):
    url = f"{BASE_URL}/beacon-log/findUserProfileBuUserId/{user_id}"  # URL สำหรับดึงข้อมูลโปรไฟล์
    headers = {"Authorization": f"Bearer {API_ACCESS_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # หากเกิดข้อผิดพลาด จะหยุดและโยนข้อผิดพลาด
        return response.json()  # คืนค่าผลลัพธ์เป็น JSON
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user profile: {e}")
        return None

# ฟังก์ชันที่ใช้ในการอัพเดทข้อมูลโปรไฟล์จาก API
def update_user_profile_from_api(user_id, new_displayname):
    url = f"{BASE_URL}/beacon-log/update-profile/{user_id}/{new_displayname}"  # ปรับ URL ให้ตรงกับ API
    headers = {"Authorization": f"Bearer {API_ACCESS_TOKEN}"}  # การตั้งค่า headers
    response = requests.patch(url, headers=headers)  # ไม่ต้องส่งข้อมูลใน body เพราะข้อมูลอยู่ใน URL
    # print(f"Response: {response.text}")
    # try:
    #     response.raise_for_status()  # หากเกิดข้อผิดพลาด จะหยุดและโยนข้อผิดพลาด
    #     return response.text()  # คืนค่าผลลัพธ์เป็น JSON
    # except requests.exceptions.RequestException as e:
    #     print(f"Error updating user profile: {e}")
        # return None
    return response
    
def get_last_beacon_event(hwid, userid):
    url = f"{BASE_URL}/beacon-log/findLastedTimeStampByUserIdAndHWid/{userid}/{hwid}"  # URL สำหรับดึง Beacon Event ล่าสุด
    headers = {"Authorization": f"Bearer {API_ACCESS_TOKEN}"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # หากเกิดข้อผิดพลาด จะหยุดและโยนข้อผิดพลาด
        
        data = response.json()
        print(f"Last event data: {data}")
        # # เช็คว่า data เป็นค่าว่างหรือไม่
        # if not data:  # ถ้า data เป็นค่าว่าง หรือเป็น None
        #     print("Received empty response, returning None.")
        #     return None
        
        return data  # คืนค่าผลลัพธ์เป็น JSON
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching beacon event: {e}")
        return None
    
def post_beacon_event(hwid, userid, event_time, student_id):
    url = f"{BASE_URL}/beacon-log/addBeaconEvent"  # เปลี่ยนเป็น URL สำหรับบันทึก Beacon Event
    headers = {"Authorization": f"Bearer {API_ACCESS_TOKEN}"}
    data = {
        "user_profile": {
            "userId": userid,
            "displayname": student_id
        },
        "beacon_log": {
            "hwId": hwid,
            "userId": userid,
            "timestamp": event_time.isoformat()
        }
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()  # หากเกิดข้อผิดพลาดจะหยุดและโยนข้อผิดพลาด
        print(f"Beacon event saved successfully for {userid}")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error saving beacon event: {e}")
        return None
    
def post_beacon_log(hwid, userid, event_time):
    url = f"{BASE_URL}/beacon-log/addBeaconLog"  # เปลี่ยนเป็น URL สำหรับบันทึก Beacon Event
    headers = {"Authorization": f"Bearer {API_ACCESS_TOKEN}"}
    data = {
        "hwId": hwid,
        "userId": userid,
        "timestamp": event_time.isoformat()
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        print(f"Beacon event saved successfully for {userid}")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error saving beacon event: {e}")
        return None

# ฟังก์ชันตรวจสอบรหัสนักศึกษาและเรียก API
def validate_student_id(user_message, year_suffix, user_id, reply_token):
    if re.fullmatch(r"\d{8}", user_message):  
        student_prefix = int(user_message[:2])

        if student_prefix <= year_suffix:
            # ดึงข้อมูลโปรไฟล์จาก API แทนการ query ข้อมูลในฐานข้อมูล
            user_profile = get_user_profile_from_api(user_id)
            if user_profile:
                displayname = user_profile.get("displayname")
                if displayname != user_message:  # เช็คว่า displayname ไม่ตรงกับ student_id เดิม
                    print(f"Updating displayname to student ID: {user_message}")
                    updated_profile = update_user_profile_from_api(user_id, user_message)
                    if updated_profile:
                        reply_to_user(reply_token, f"อัปเดตชื่อเป็นรหัสนักศึกษา {user_message} สำเร็จ!")
                    else:
                        reply_to_user(reply_token, "ไม่สามารถอัปเดตชื่อได้ในขณะนี้")
                else:
                    reply_to_user(reply_token, "รหัสนักศึกษาของคุณตรงกับข้อมูลในระบบแล้ว ไม่มีการบันทึกใหม่!")
            else:
                reply_to_user(reply_token, "ไม่พบข้อมูลของคุณในระบบ กรุณาเชื่อมต่อ Beacon ก่อนแล้วลองใหม่อีกครั้ง")
        else:
            reply_to_user(reply_token, f"รหัสนักศึกษาของคุณไม่ถูกต้อง กรุณากรอกหมายเลขที่ขึ้นต้นด้วยตัวเลขไม่เกิน {year_suffix}")
    else:
        reply_to_user(reply_token, "กรุณากรอกรหัสนักศึกษาที่ถูกต้อง (ต้องเป็นตัวเลข 8 หลักเท่านั้น)")

    return jsonify({"message": "displayname update attempt"}), 200

def save_beacon_event(hwid, userid, event_time, student_id):
    # ตรวจสอบว่าเรามีข้อมูลผู้ใช้หรือไม่ (อาจจะจาก API หรือ DB)
    existing_user = get_user_profile_from_api(userid)
    print(f"Existing user: {existing_user}")
    
    if not existing_user:
        print(f"User {userid} not found, creating new user...")
        # หากไม่พบผู้ใช้ ให้สร้างผู้ใช้ใหม่ผ่าน API
        headers = {"Authorization": f"Bearer {API_ACCESS_TOKEN}"}
        url = f"{BASE_URL}/beacon-log/addBeaconEvent"
        data = {
            "user_profile": {
                "userId": userid,
                "displayname": student_id
            },
            "beacon_log": {
                "hwId": hwid,
                "userId": userid,
                "timestamp": event_time.isoformat()
            }
        }
        try:
            response = requests.post(url, json=data , headers=headers)
            response.raise_for_status()
            print(f"New user created for {userid}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to create user: {e}")
            return None  # หรือจะส่งคืนค่าอื่น ๆ ตามต้องการ
    else:
        print(f"User {userid} found, updating displayname...")
        post_beacon_log(hwid, userid, event_time)
        update_user_profile_from_api(userid, student_id)

    # บันทึก Beacon Event ผ่าน API
    # result = post_beacon_event(hwid, userid, event_time, student_id)
    # if result is None:
    #     print("Failed to save beacon event.")
    #     return None
    # else:
    #     print("Beacon event saved successfully!")
    #     return result
                    
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
                    return jsonify({"message": "Waiting for new displayname"}), 200

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
                hwid = event['beacon'].get('hwid')
                userid = event['source'].get('userId')
                timestamp = event.get('timestamp')
                reply_token = event['replyToken']

                event_time = datetime.fromtimestamp(timestamp / 1000, timezone.utc)

                if not hwid or not userid or timestamp is None:
                    return jsonify({"message": "Missing beacon data"}), 400

                # print(f"Received timestamp: {timestamp}, Converted datetime: {event_time = }")

                profile = get_line_user_profile(userid)
                displayname = profile.get("displayName", "Unknown User") if profile else "Unknown User"
                # save_beacon_event(hwid, userid, event_time, displayname)
                # ============================================================
                existing_event = get_last_beacon_event(hwid, userid)
                # print(f"Existing event: {existing_event}")

                utc_plus_7 = timezone(timedelta(hours=7))
                existing_event_timestamp = existing_event.get("timestamp") if existing_event else None

                if existing_event and existing_event_timestamp:
                    # Convert existing_event_timestamp to datetime if it's a string
                    if isinstance(existing_event_timestamp, str):
                        existing_event_timestamp = datetime.fromisoformat(existing_event_timestamp)
                        # print(f"Existing event timestamp converted to datetime: {existing_event_timestamp}")
                    
                    # Add timezone information to the existing timestamp
                    existing_event_timestamp = existing_event_timestamp.replace(tzinfo=utc_plus_7)
                    event_time = event_time.replace(tzinfo=utc_plus_7)
                    # print(f"Existing event timestamp with timezone: {existing_event_timestamp}")
                    # print(f"event_time: {event_time}")
                    # print(f"Time difference: {event_time - existing_event_timestamp}")

                    # Compare event_time with the existing event timestamp
                    if (event_time - existing_event_timestamp) < timedelta(minutes=1):
                        print("Duplicate event, ignored")
                        return jsonify({"message": "Duplicate event, ignored"}), 200  # ใช้ return แทน continue
                else:
                    print("No existing event found or missing timestamp")


                # save_beacon_event(hwid, userid, event_time, displayname)
                # reply_to_user(reply_token, 
                #                     f"เช็คชื่อเข้าเรียนสำเร็จ! คุณ {displayname}\n"
                #                     f"กรุณากรอกรหัสนักศึกษา 8 หลัก เพื่ออัปเดตข้อมูลของคุณ")


                existing_user = get_user_profile_from_api(userid)
                print(f"Existing user: {existing_user}")
                existing_user_displayname = existing_user.get("displayname") if existing_user else None


                pattern = r"(\d{8})"# หาเลข 8 หลักที่เป็นคำสมบูรณ์
                match = re.search(pattern, displayname)

                if match:
                    student_id = match.group()  # ดึงเลข 8 หลักจากข้อความ
                    student_prefix = int(student_id[:2])

                    if student_prefix <= year_suffix:
                        reply_to_user(reply_token, f"เช็คชื่อเข้าเรียนสำเร็จ! คุณ {student_id}")
                        print(f"student_prefix <= year_suffix")
                    
                        save_beacon_event(hwid, userid, event_time, student_id)
                    else:
                        if existing_user and existing_user_displayname.isdigit() and len(existing_user_displayname) == 8:
                            reply_to_user(reply_token, 
                                    f"เช็คชื่อเข้าเรียนสำเร็จ! คุณ {existing_user_displayname}")
                        else:
                            reply_to_user(reply_token, 
                                        f"เช็คชื่อเข้าเรียนสำเร็จ! คุณ {displayname}\n"
                                        f"รหัสนักศึกษาของคุณไม่ถูกต้อง กรุณากรอกรหัสที่ขึ้นต้นด้วยตัวเลขไม่เกิน {year_suffix}")
                        if existing_user :

                            post_beacon_event(hwid, userid, event_time, existing_user_displayname)
                        else:
                            save_beacon_event(hwid, userid, event_time, student_id)
                        
                else:
                    # ตรวจสอบว่า displayname ในฐานข้อมูลคือ student_id หรือไม่
                    if existing_user and existing_user_displayname.isdigit() and len(existing_user_displayname) == 8:
                        # ถ้า displayname เป็นรหัสนักศึกษา 8 หลักแล้ว จะไม่ส่งข้อความขอรหัส
                        print(f"User {userid} has student ID as displayname")
                        save_beacon_event(hwid, userid, event_time, existing_user_displayname)
                        reply_to_user(reply_token, 
                                    f"เช็คชื่อเข้าเรียนสำเร็จ! คุณ {existing_user_displayname}")
                    else:
                        save_beacon_event(hwid, userid, event_time, displayname)
                        reply_to_user(reply_token, 
                                    f"เช็คชื่อเข้าเรียนสำเร็จ! คุณ {displayname}\n"
                                    f"กรุณากรอกรหัสนักศึกษา 8 หลัก เพื่ออัปเดตข้อมูลของคุณ")


              
        return jsonify({"message": "Event processed"}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"message": "An error occurred", "error": str(e)}), 500

# เริ่มเซิร์ฟเวอร์ Flask
if __name__ == '__main__':
    with app.app_context():
        app.run(port=5000, debug=True)
    app.run(debug=True)