import swisseph as swe
import json
import os
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 天体の定義
PLANETS = {
    'Sun': swe.SUN,
    'Moon': swe.MOON,
    'Mercury': swe.MERCURY,
    'Venus': swe.VENUS,
    'Mars': swe.MARS,
    'Jupiter': swe.JUPITER,
    'Saturn': swe.SATURN,
    'Uranus': swe.URANUS,
    'Neptune': swe.NEPTUNE,
    'Pluto': swe.PLUTO,
    'NorthNode': swe.MEAN_NODE,
}

# 星座の定義
SIGNS = [
    '牡羊座', '牡牛座', '双子座', '蟹座', '獅子座', '乙女座',
    '天秤座', '蠍座', '射手座', '山羊座', '水瓶座', '魚座'
]

def get_sign(longitude):
    """経度から星座を取得"""
    sign_num = int(longitude / 30)
    degree_in_sign = longitude % 30
    return SIGNS[sign_num], degree_in_sign

def calculate_transit(date):
    """指定日のトランジットデータを計算"""
    swe.set_ephe_path(None)
    
    # Julian Day を計算（UTCの正午）
    jd = swe.julday(date.year, date.month, date.day, 12.0)
    
    transit_data = {
        'date': date.strftime('%Y-%m-%d'),
        'planets': {}
    }
    
    for name, planet_id in PLANETS.items():
        # 天体の位置を計算
        result = swe.calc_ut(jd, planet_id)
        longitude = result[0][0]
        speed = result[0][3]
        
        sign, degree = get_sign(longitude)
        is_retrograde = speed < 0
        
        transit_data['planets'][name] = {
            'longitude': round(longitude, 4),
            'sign': sign,
            'degree': round(degree, 2),
            'retrograde': is_retrograde,
            'speed': round(speed, 4)
        }
    
    # 主要アスペクトを計算
    transit_data['aspects'] = calculate_aspects(transit_data['planets'])
    
    return transit_data

def calculate_aspects(planets):
    """天体間のアスペクトを計算"""
    aspects = []
    aspect_types = {
        'conjunction': (0, 8),
        'sextile': (60, 6),
        'square': (90, 8),
        'trine': (120, 8),
        'opposition': (180, 8)
    }
    
    planet_names = list(planets.keys())
    
    for i, p1 in enumerate(planet_names):
        for p2 in planet_names[i+1:]:
            lon1 = planets[p1]['longitude']
            lon2 = planets[p2]['longitude']
            
            diff = abs(lon1 - lon2)
            if diff > 180:
                diff = 360 - diff
            
            for aspect_name, (angle, orb) in aspect_types.items():
                if abs(diff - angle) <= orb:
                    aspects.append({
                        'planet1': p1,
                        'planet2': p2,
                        'aspect': aspect_name,
                        'orb': round(abs(diff - angle), 2)
                    })
                    break
    
    return aspects

def upload_to_drive(file_path, folder_id):
    """Google Driveにファイルをアップロード"""
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    creds_dict = json.loads(creds_json)
    
    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    
    service = build('drive', 'v3', credentials=creds)
    
    # 古いファイルを削除
    results = service.files().list(
        q=f"'{folder_id}' in parents and name contains 'transit_'",
        fields="files(id, name)"
    ).execute()
    
    for file in results.get('files', []):
        service.files().delete(fileId=file['id']).execute()
        print(f"Deleted: {file['name']}")
    
    # 新しいファイルをアップロード
    file_metadata = {
        'name': os.path.basename(file_path),
        'parents': [folder_id]
    }
    
    media = MediaFileUpload(file_path, mimetype='application/json')
    
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    
    print(f"Uploaded: {os.path.basename(file_path)}")

def main():
    # 今日の日付
    today = datetime.utcnow()
    
    # 今日から7日分のトランジットデータを生成
    all_transits = []
    for i in range(7):
        date = today + timedelta(days=i)
        transit = calculate_transit(date)
        all_transits.append(transit)
    
    # JSONファイルとして保存
    filename = f"transit_{today.strftime('%Y%m%d')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_transits, f, ensure_ascii=False, indent=2)
    
    print(f"Generated: {filename}")
    
    # Google Driveにアップロード
    folder_id = os.environ.get('FOLDER_ID')
    if folder_id:
        upload_to_drive(filename, folder_id)

if __name__ == '__main__':
    main()
