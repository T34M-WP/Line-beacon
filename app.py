import re
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

user_sessions = {}

LINE_CHANNEL_ACCESS_TOKEN = "yUkSAFq8OrTXaPA7t7N37c4vZ1widgppiBfOSh9iMwNOHQxus+JZ0SFJkZLDARzy9DyrWj0GEmn6VdULQof2QzJDZgmjgOsa4+E9kKA5EzeAMCTYEjLHdXKnWBsxz5HVxwcn60GU4iMk3Xdk4BRFXAdB04t89/1O/w1cDnyilFU="
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
LINE_PROFILE_URL = "https://api.line.me/v2/bot/profile/"
BASE_URL = "http://192.168.70.6:3000/api" 
API_ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImJlYWNvbiIsInJvbGUiOiJ1c2VyIiwiaWF0IjoxNzQwNjUyMTkzLCJleHAiOjE3NzIyMDk3OTN9.eQJWpm0OlJq01XOT2nPxatlXCDeydapufgTXWboEUjQ"

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
    url = f"{BASE_URL}/beacon-log/findUserProfileBuUserId/{user_id}"
    headers = {"Authorization": f"Bearer {API_ACCESS_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user profile: {e}")
        return None

def update_user_profile_from_api(user_id, new_displayname):
    url = f"{BASE_URL}/beacon-log/update-profile/{user_id}/{new_displayname}"
    headers = {"Authorization": f"Bearer {API_ACCESS_TOKEN}"}
    response = requests.patch(url, headers=headers)
    return response
    
def get_last_beacon_event(hwid, userid):
    url = f"{BASE_URL}/beacon-log/findLastedTimeStampByUserIdAndHWid/{userid}/{hwid}"
    headers = {"Authorization": f"Bearer {API_ACCESS_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching beacon event: {e}")
        return None
    
def post_beacon_event(hwid, userid, event_time, student_id):
    url = f"{BASE_URL}/beacon-log/addBeaconEvent"
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
    response = requests.post(url, json=data, headers=headers)
    return response.json()
    
def post_beacon_log(hwid, userid, event_time):
    url = f"{BASE_URL}/beacon-log/addBeaconLog"
    headers = {"Authorization": f"Bearer {API_ACCESS_TOKEN}"}
    data = {
        "hwId": hwid,
        "userId": userid,
        "timestamp": event_time.isoformat()
    }
    response = requests.post(url, json=data, headers=headers)
    return response.json()

def validate_student_id(user_message, year_suffix, user_id, reply_token):
    if re.fullmatch(r"\d{8}", user_message):  
        student_prefix = int(user_message[:2])

        if student_prefix <= year_suffix:
            user_profile = get_user_profile_from_api(user_id)
            if user_profile:
                displayname = user_profile.get("displayname")
                if displayname != user_message:
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
    existing_user = get_user_profile_from_api(userid)    
    if not existing_user:
        print(f"User {userid} not found, creating new user...")
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
            return None
    else:
        print(f"User {userid} found, updating displayname...")
        post_beacon_log(hwid, userid, event_time)
        update_user_profile_from_api(userid, student_id)
                    
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

            if event_type == 'message' and event['message']['type'] == 'text':
                user_id = event['source']['userId']
                user_message = event['message']['text'].strip()
                reply_token = event['replyToken']

                if user_message.lower() == "เปลี่ยนชื่อผู้ใช้":
                    user_sessions[user_id] = "waiting_for_student_id"
                    reply_to_user(reply_token, "กรุณากรอกรหัสนักศึกษา 8 หลัก เพื่อเปลี่ยนชื่อผู้ใช้")
                    return jsonify({"message": "Waiting for new displayname"}), 200

                if user_sessions.get(user_id) == "waiting_for_student_id":
                    if user_message.isnumeric() and len(user_message) == 8 and int(user_message[:2]) <= 68:
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
                userid = event['source'].get('userId')
                timestamp = event.get('timestamp')
                reply_token = event['replyToken']
                event_time = datetime.fromtimestamp(timestamp / 1000, timezone.utc)

                if not hwid or not userid or timestamp is None:
                    return jsonify({"message": "Missing beacon data"}), 400

                profile = get_line_user_profile(userid)
                displayname = profile.get("displayName", "Unknown User") if profile else "Unknown User"

                utc_plus_7 = timezone(timedelta(hours=7))
                existing_event = get_last_beacon_event(hwid, userid)
                existing_event_timestamp = existing_event.get("timestamp") if existing_event else None

                if existing_event and existing_event_timestamp:
                    if isinstance(existing_event_timestamp, str):
                        existing_event_timestamp = datetime.fromisoformat(existing_event_timestamp)

                    existing_event_timestamp = existing_event_timestamp.replace(tzinfo=utc_plus_7)
                    event_time = event_time.replace(tzinfo=utc_plus_7)

                    if (event_time - existing_event_timestamp) < timedelta(minutes=1):
                        print("Duplicate event, ignored")
                        return jsonify({"message": "Duplicate event, ignored"}), 200
                else:
                    print("No existing event found or missing timestamp")

                existing_user = get_user_profile_from_api(userid)
                print(f"Existing user: {existing_user}")
                existing_user_displayname = existing_user.get("displayname") if existing_user else None

                pattern = r"(\d{8})"
                match = re.search(pattern, displayname)
                if match:
                    student_id = match.group()
                    student_prefix = int(student_id[:2])
                    if student_prefix <= year_suffix:
                        reply_to_user(reply_token, f"เช็คชื่อเข้าเรียนสำเร็จ! คุณ {student_id}")
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
                    if existing_user and existing_user_displayname.isdigit() and len(existing_user_displayname) == 8:
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

if __name__ == '__main__':
    with app.app_context():
        app.run(port=5000, debug=True)