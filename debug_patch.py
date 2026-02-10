import requests
import sys

# 配置
BASE_URL = "http://127.0.0.1:9999/api/v1"
LOGIN_DATA = {"userName": "Soybean", "password": "123456"}
# 模拟前端发送的 Payload，包含空密码
PATCH_DATA = {
    "userName": "Soybean",
    "password": "", 
    "id": 1,  # 模拟前端传递的多余字段
    "userGender": "3",
    "nickName": "Soybean8",
    "statusType": "1",
    "userEmail": "admin@admin.com",
    "userPhone": None,
    "byUserRoleCodeList": ["R_SUPER"]
}

def debug_patch():
    # 1. 登录获取 Token
    print(f"[*] Logging in as {LOGIN_DATA['userName']}...")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json=LOGIN_DATA)
    except requests.exceptions.ConnectionError:
        print("[!] Connection refused. Is the server running?")
        return

    if resp.status_code != 200:
        print(f"[!] Login failed: {resp.status_code} - {resp.text}")
        return
    
    token = resp.json()["data"]["token"]
    print(f"[*] Login successful. Token: {token[:10]}...")
    
    # 2. 发送 PATCH 请求
    print(f"[*] Sending PATCH request to /system-manage/users/1 with empty password...")
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.patch(
        f"{BASE_URL}/system-manage/users/1",
        json=PATCH_DATA,
        headers=headers
    )
    
    print(f"[*] Response Status: {resp.status_code}")
    print(f"[*] Response Body: {resp.text}")
    
    if resp.status_code == 200:
        print("[+] Success! The fix is working.")
    elif resp.status_code == 500:
        print("[!] Failed with 500 Internal Server Error. Check server logs for stack trace.")
    elif resp.status_code == 422:
        print("[!] Failed with 422 Validation Error. Schema validation issue.")
    else:
        print(f"[!] Unexpected status code: {resp.status_code}")

if __name__ == "__main__":
    debug_patch()
