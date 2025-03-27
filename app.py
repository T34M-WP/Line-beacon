import os
import re
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify
from dataclasses import dataclass
from dotenv import load_dotenv

# อ่านค่าจาก Environment Variables
load_dotenv()
@dataclass
class Config:
    LINE_CHANNEL_ACCESS_TOKEN: str = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    API_ACCESS_TOKEN: str = os.environ.get("API_ACCESS_TOKEN")
    BASE_URL: str = os.environ.get("BASE_URL")
    LINE_REPLY_URL: str = "https://api.line.me/v2/bot/message/reply"
    LINE_PROFILE_URL: str = "https://api.line.me/v2/bot/profile/"

# ตรวจสอบค่า Config หากไม่มีให้หยุดทำงาน
if not all([Config.LINE_CHANNEL_ACCESS_TOKEN, Config.API_ACCESS_TOKEN, Config.BASE_URL]):
    raise ValueError("Missing required environment variables")

app = Flask(__name__)
user_sessions = {}

# ฟังก์ชันสำหรับเรียก API
def send_request(method, url, headers=None, json=None):
    try:
        response = requests.request(method, url, headers=headers, json=json)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}")
        return None

# ฟังก์ชันส่งข้อความกลับไปที่ LINE
def reply_to_user(reply_token, message):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {Config.LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {"replyToken": reply_token, "messages": [{"type": "text", "text": message}]}
    send_request("POST", Config.LINE_REPLY_URL, headers=headers, json=payload)

# ดึงข้อมูลโปรไฟล์จาก LINE
def get_line_user_profile(user_id):
    headers = {"Authorization": f"Bearer {Config.LINE_CHANNEL_ACCESS_TOKEN}"}
    return send_request("GET", f"{Config.LINE_PROFILE_URL}{user_id}", headers=headers)

# ดึงข้อมูลผู้ใช้จาก API
def get_user_profile_from_api(user_id):
    url = f"{Config.BASE_URL}/beacon-log/findUserProfileBuUserId/{user_id}"
    headers = {"Authorization": f"Bearer {Config.API_ACCESS_TOKEN}"}
    return send_request("GET", url, headers=headers)

def get_user_event_from_api(user_id, hwid):
    url = f"{Config.BASE_URL}/beacon-log/findLastedTimeStampByUserIdAndHWid/{user_id}/{hwid}"
    headers = {"Authorization": f"Bearer {Config.API_ACCESS_TOKEN}"}
    return send_request("GET", url, headers=headers)

# อัปเดตโปรไฟล์ผู้ใช้ใน API
def update_user_profile_from_api(user_id, new_displayname):
    url = f"{Config.BASE_URL}/beacon-log/update-profile/{user_id}/{new_displayname}"
    headers = {"Authorization": f"Bearer {Config.API_ACCESS_TOKEN}"}
    return send_request("PATCH", url, headers=headers)

def post_beacon_log(hwid, userid):
    url = f"{Config.BASE_URL}/beacon-log/addBeaconLog"
    headers = {"Authorization": f"Bearer {Config.API_ACCESS_TOKEN}"}
    data = {
        "hwId": hwid,
        "userId": userid,
    }
    return send_request("POST", url, headers=headers, json=data)

# บันทึก event beacon
def save_beacon_event(hwid, userid, student_id):
    existing_user = get_user_profile_from_api(userid) 
    if not existing_user:
        url = f"{Config.BASE_URL}/beacon-log/addBeaconEvent"
        headers = {"Authorization": f"Bearer {Config.API_ACCESS_TOKEN}"}
        data = {
            "user_profile": {"userId": userid, "displayname": student_id},
            "beacon_log": {"hwId": hwid, "userId": userid}
        }
        return send_request("POST", url, headers=headers, json=data)
    
    post_beacon_log(hwid, userid)
    update_user_profile_from_api(userid, student_id)
    

# ตรวจสอบรหัสนักศึกษา
def validate_student_id(user_message, year_suffix, user_id, reply_token):
    if re.fullmatch(r"\d{8}", user_message) and int(user_message[:2]) <= year_suffix:
        user_profile = get_user_profile_from_api(user_id)
        if user_profile:
            if user_profile.get("displayname") != user_message:
                if update_user_profile_from_api(user_id, user_message):
                    reply_to_user(reply_token, f"อัปเดตชื่อเป็นรหัสนักศึกษา {user_message} สำเร็จ!")
                else:
                    reply_to_user(reply_token, "ไม่สามารถอัปเดตชื่อได้ในขณะนี้")
            else:
                reply_to_user(reply_token, "รหัสนักศึกษาของคุณตรงกับข้อมูลในระบบแล้ว")
        else:
            reply_to_user(reply_token, "ไม่พบข้อมูลของคุณในระบบ กรุณาเชื่อมต่อ Beacon ก่อนแล้วลองใหม่อีกครั้ง")
    else:
        reply_to_user(reply_token, f"รหัสนักศึกษาของคุณไม่ถูกต้อง กรุณากรอกหมายเลขที่ขึ้นต้นด้วยตัวเลขไม่เกิน {year_suffix}")

# LINE Webhook
@app.route('/line-webhook', methods=['POST'])
def line_webhook():
    try:
        data = request.json
        if not data or 'events' not in data:
            return jsonify({"message": "Invalid event or missing data"}), 400
        
        current_year = datetime.now().year + 543
        year_suffix = current_year % 100

        for event in data['events']:
            event_type = event.get('type')
            user_id = event['source']['userId']
            reply_token = event['replyToken']

            if event_type == 'message' and event['message']['type'] == 'text':
                user_message = event['message']['text'].strip()

                if user_message.lower() == "เปลี่ยนชื่อผู้ใช้":
                    user_sessions[user_id] = "waiting_for_student_id"
                    reply_to_user(reply_token, "กรุณากรอกรหัสนักศึกษา 8 หลัก เพื่อเปลี่ยนชื่อผู้ใช้")
                    return jsonify({"message": "Waiting for new displayname"}), 200

                if user_sessions.get(user_id) == "waiting_for_student_id":
                    if user_message.isnumeric() and len(user_message) == 8 and int(user_message[:2]) <= year_suffix:
                        del user_sessions[user_id]
                        return validate_student_id(user_message, year_suffix, user_id, reply_token)
                    else:
                        reply_to_user(reply_token, 
                            f"รหัสนักศึกษาของคุณไม่ถูกต้อง\n"
                            f"รหัสนักศึกษาต้องเป็นตัวเลข 8 หลัก\n"
                            f"ตัวอย่างที่ถูกต้อง: {year_suffix}12345, {year_suffix}56789\n"
                            f"โดย 2 หลักแรกต้องไม่เกิน {year_suffix}\n"
                            f"\nกรุณาลองใหม่อีกครั้ง!")
                        return jsonify({"message": "Invalid student ID"}), 400

            elif event_type == 'beacon':
                hwid = event['beacon'].get('hwid')
                timestamp = event.get('timestamp')

                if not hwid or not user_id or timestamp is None:
                    return jsonify({"message": "Missing beacon data"}), 400

                event_time = datetime.fromtimestamp(timestamp / 1000, timezone.utc)
                existing_event = get_user_event_from_api(user_id, hwid)
                user_time_str = existing_event.get("timestamp") if existing_event else None
                user_time = datetime.fromisoformat(user_time_str.replace("Z", "+00:00")) if user_time_str else None
            
                if user_time is not None:
                    time_diff = event_time - user_time
                    if time_diff < timedelta(minutes=2):
                        print(f"User {user_id} already checked in")
                        return jsonify({"message": "User already checked in"}), 200
                
                profile = get_line_user_profile(user_id)
                displayname = profile.get("displayName", "Unknown User") if profile else "Unknown User"

                existing_user = get_user_profile_from_api(user_id)
                existing_user_displayname = existing_user.get("displayname") if existing_user else None

                pattern = r"(\d{8})"
                match = re.search(pattern, displayname)
                if match:
                    student_id = match.group()
                    student_prefix = int(student_id[:2])
                    if student_prefix <= year_suffix:
                        message = f"เช็คชื่อเข้าเรียนสำเร็จ! คุณ {student_id}"
                    else:
                        message = (f"เช็คชื่อเข้าเรียนสำเร็จ! คุณ {displayname}\n"
                                f"รหัสนักศึกษาของคุณไม่ถูกต้อง กรุณากรอกรหัสที่ขึ้นต้นด้วยตัวเลขไม่เกิน {year_suffix}")
                elif existing_user_displayname and re.match(r"\d{8}", existing_user_displayname):
                    student_id = existing_user_displayname
                    message = f"เช็คชื่อเข้าเรียนสำเร็จ! คุณ {student_id}"
                else:
                    student_id = None
                    message = (f"เช็คชื่อเข้าเรียนสำเร็จ! คุณ {displayname}\n"
                            f"กรุณากรอกรหัสนักศึกษา 8 หลัก เพื่ออัปเดตข้อมูลของคุณ")

                save_beacon_event(hwid, user_id, student_id or displayname)
                reply_to_user(reply_token, message)

        return jsonify({"message": "Event processed"}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"message": "An error occurred", "error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)
