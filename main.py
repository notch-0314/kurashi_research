import streamlit as st
from selenium import webdriver
import chromedriver_binary
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome import service as fs
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse, parse_qs
from selenium.common.exceptions import StaleElementReferenceException
from googleapiclient.discovery import build
from isodate import parse_duration
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib import rcParams
import matplotlib.animation as animation

api_key = 'AIzaSyCyyG4wCBnsXtM6BvrNoHGLhvXdvJCg6E0'
rcParams['font.family'] = 'Noto Sans JP'

# 今日を起点にして2日前〜6日前の曜日名をリスト形式で取得（Youtubeの日付が「今日」「昨日」「n曜日」...となっているため）
today = datetime.now()
weekdays_en = [(today - timedelta(days=i)).strftime('%A') for i in range(2, 7)]
weekdays_jp_mapping = {
    'Monday': '月曜日',
    'Tuesday': '火曜日',
    'Wednesday': '水曜日',
    'Thursday': '木曜日',
    'Friday': '金曜日',
    'Saturday': '土曜日',
    'Sunday': '日曜日'
}
weekdays_jp = [weekdays_jp_mapping[day] for day in weekdays_en]

# ISO 8601形式の時間を秒数に変換
def convert_duration_to_sec(iso_duration):
    duration = parse_duration(iso_duration)
    total_seconds = int(duration.total_seconds())
    return total_seconds

# 秒数を「時間」「分」「秒」に変換
def convert_seconds_to_hrs_min_sec(total_seconds):
    hours = total_seconds // 3600
    remainder = total_seconds % 3600
    minutes = remainder // 60
    seconds = remainder % 60
    return hours, minutes, seconds

# URLからidを取得
def extract_video_id(url):
    parsed_url = urlparse(url)
    if 'youtube.com' in parsed_url.netloc:
        query_params = parse_qs(parsed_url.query)
        return query_params.get('v', [None])[0]
    else:
        return None

# URLから視聴秒数を取得
def extract_viewing_time(url):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    t_param = query_params.get('t', [None])[0]

    if t_param and 's' in t_param:
        return int(t_param.replace('s', ''))
    else:
        return t_param

# 動画idから必要な情報を取得
def get_video_details(video_id):
    youtube = build('youtube', 'v3', developerKey=api_key)
    request = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        id=video_id
    )
    response = request.execute()
    if response['items']:
        item = response['items'][0]
        title = item['snippet']['title']
        category_id = item['snippet']['categoryId']
        channel_name = item['snippet']['channelTitle']
        duration = response['items'][0]['contentDetails']['duration']
        category_name = get_category_name(category_id)
        total_sec = convert_duration_to_sec(duration)
        return title, category_name, channel_name, total_sec
    else:
        return None, None, None, None

# カテゴリidからカテゴリ名を取得
def get_category_name(category_id):
    youtube = build('youtube', 'v3', developerKey=api_key)
    request = youtube.videoCategories().list(
        part="snippet",
        id=category_id,
        hl="ja"
    )
    response = request.execute()
    if response['items']:
        category_name = response['items'][0]['snippet']['title']
        return category_name
    else:
        return None

# 動画URLをスクレイピングし、idを抽出。APIを使用して視聴履歴の必要データを格納。視聴データのない曜日は曜日のみ格納
def fetch_data_for_date(date_label, browser):
    data = []
    xpath_query = f"//ytd-item-section-renderer[contains(@class, 'style-scope ytd-section-list-renderer')][descendant::*[contains(text(), '{date_label}')]]"
    elements = browser.find_elements(By.XPATH, xpath_query)
    
    if not elements: # 要素が見つからなかった場合、空のデータリストを返す
        return data

    element = elements[0]
    links = element.find_elements(By.XPATH, ".//a[contains(@class, 'yt-simple-endpoint')]")

    for link in links:
        url = link.get_attribute('href')
        video_id = extract_video_id(url)
        if video_id:
            title, category_name, channel_name, total_sec = get_video_details(video_id)
            viewing_time = extract_viewing_time(url) or total_sec
            data.append({
                'title': title,
                'category_name': category_name,
                'channel_name': channel_name,
                'total_sec': total_sec,
                'viewing_time': viewing_time
            })
    return data

# YouTubeの言語設定に基づいて日付ラベルを選択
def get_date_labels(browser):
    # ページの言語設定を取得
    language = browser.execute_script("return document.documentElement.lang;")
    
    # デバッグ情報を出力
    print("Detected language:", language)
    
    # 言語設定に基づいて日付ラベルを選択
    if language == 'ja-JP':
        date_labels = ['今日', '昨日'] + weekdays_jp
    else:
        date_labels = ['Today', 'Yesterday'] + weekdays_en

    # 戻り値をコンソールに出力
    print("Returning date labels:", date_labels)

    return date_labels

# 日付ごとにスクレイピングと情報の格納を実行
def get_history_data(browser):
    history_data = {}
    date_labels = get_date_labels(browser)
    date_labels.reverse() #逆にする
    st.session_state['date_labels'] = date_labels  # Streamlitのセッション状態に保存

    for date_label in date_labels:
        history_data[date_label] = fetch_data_for_date(date_label, browser)

    return history_data

# チェックされたカテゴリの動画の視聴時間を合計し、グラフ化
def update_graph(selected_categories, history_data, graph_placeholder):
    viewing_times_in_min = []  # 分単位での視聴時間を格納するリスト
    days = st.session_state['date_labels']  # セッション状態から日付ラベルを取得
    # days.reverse()

    for day in days:
        videos = history_data.get(day, [])  # キーが存在しない場合は空のリストを返す
        day_total_sec = sum(video['viewing_time'] for video in videos if video['category_name'] in selected_categories)
        day_total_min = day_total_sec / 60  # 秒数を分に変換
        viewing_times_in_min.append(day_total_min)

    # グラフを描画
    plt.figure(figsize=(10, 6))
    bars = plt.bar(days, viewing_times_in_min, color='#1340F2', width=0.3)
    plt.xlabel('日付')
    plt.ylabel('視聴時間 (分)')
    plt.title('過去1週間のYouTube視聴時間')
    plt.xticks(days)

    # 各棒に「時間:分:秒」形式のラベルを追加
    for bar in bars:
        yvalue = bar.get_height()
        hours, minutes, seconds = convert_seconds_to_hrs_min_sec(int(yvalue * 60))  # yvalueを再び秒に変換
        plt.text(bar.get_x() + bar.get_width()/2, yvalue, f"{hours}時間{minutes}分{seconds}秒", ha='center', va='bottom')

    graph_placeholder.pyplot(plt)

def wait_for_element_clickable(browser, by, value, timeout=10):
    return WebDriverWait(browser, timeout).until(EC.element_to_be_clickable((by, value)))

def wait_for_element_visible(browser, by, value, timeout=20):
    return WebDriverWait(browser, timeout).until(EC.visibility_of_element_located((by, value)))

def find_element_by_text(elements, text):
    return next((element for element in elements if element.text == text), None)

def start_button_clicked(input_email_or_phone, input_password):
    
    graph_placeholder = st.empty() # グラフを表示する場所に空のグラフを配置
    
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.105 Safari/537.36"

    options = webdriver.ChromeOptions()
    options.add_argument('--user-agent=' + ua)
    options.add_argument('--disable-blink-features=AutomationControlled')
    
    chrome_service = ChromeService(executable_path=ChromeDriverManager().install())
    
    browser = webdriver.Chrome(service=chrome_service, options=options)
    
    browser.get('https://www.youtube.com/feed/history')

    wait_for_element_clickable(browser, By.XPATH, "//ytd-button-renderer[contains(., 'ログイン')]").click()
    wait_for_element_clickable(browser, By.CSS_SELECTOR, 'input[aria-label="メールアドレスまたは電話番号"]').send_keys(input_email_or_phone) # メールアドレス入力
    wait_for_element_clickable(browser, By.XPATH, "//button[contains(., '次へ')]").click()  # 次へボタンをクリック
    wait_for_element_clickable(browser, By.CSS_SELECTOR, 'input[aria-label="パスワードを入力"]').send_keys(input_password)    # パスワード入力

    try: # 次へボタンをクリック（失敗しやすいのでエラーハンドリング）
        next_button = wait_for_element_clickable(browser, By.XPATH, "//button[contains(., '次へ')]")
        next_button.click()
    except StaleElementReferenceException: # エラーが発生した場合、要素を再取得して操作を試みる
        next_button = wait_for_element_clickable(browser, By.XPATH, "//button[contains(., '次へ')]")
        next_button.click()
    
    # ヘッダーが操作可能になるまで待つ（スクレイピングを適切に行うため）
    wait_for_element_clickable(browser, By.ID, "masthead-container")
    
    print('こんにちは')
    
    try:
        # 視聴履歴を取得
        history_data = get_history_data(browser)
        # 視聴履歴に含まれるカテゴリ一覧をunique_category_namesに格納
        unique_category_names = set()
        for day_data in history_data.values():
            for video in day_data:
                unique_category_names.add(video['category_name'])
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        
    return history_data, list(unique_category_names), graph_placeholder



# サイドバーに入力フィールドを作成
email_or_phone = st.sidebar.text_input("メールアドレスまたは電話番号")
password = st.sidebar.text_input("パスワード", type="password")  # type="password"でテキストを隠す

if email_or_phone and password and st.sidebar.button("スタート"):
    history_data, unique_category_names, graph_placeholder = start_button_clicked(email_or_phone, password)
    st.session_state['history_data'] = history_data
    st.session_state['unique_category_names'] = unique_category_names
    st.session_state['graph_placeholder'] = graph_placeholder

# カテゴリ選択用のチェックボックス
# if 'unique_category_names' in st.session_state:
#     selected_categories = st.sidebar.multiselect("カテゴリを選択", st.session_state['unique_category_names'], default=st.session_state['unique_category_names'])

if 'unique_category_names' in st.session_state:
    unique_category_names = st.session_state['unique_category_names']
    
    # デフォルトの選択を外すためのリストを作成
    default_selection = unique_category_names
    
    # 特定のカテゴリがunique_category_namesに存在する場合、そのカテゴリのデフォルト選択を外す
    if 'ニュースと政治' in default_selection:
        default_selection.remove('ニュースと政治')
    if '科学と技術' in default_selection:
        default_selection.remove('科学と技術')
    if '教育' in default_selection:
        default_selection.remove('教育')
    
    selected_categories = st.sidebar.multiselect("カテゴリを選択", unique_category_names, default=default_selection)




# グラフを更新するための条件付き呼び出し
if 'history_data' in st.session_state and 'unique_category_names' in st.session_state:
    update_graph(selected_categories, st.session_state['history_data'], st.session_state['graph_placeholder'])

        
