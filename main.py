import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome import service as fs
# from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse, parse_qs
from selenium.common.exceptions import StaleElementReferenceException
from googleapiclient.discovery import build
from isodate import parse_duration
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.lines import Line2D
from streamlit_pills import pills
import pandas as pd
# from webdriver_manager.core.os_manager import ChromeType
import platform
from bs4 import BeautifulSoup
import time

api_key = 'AIzaSyCyyG4wCBnsXtM6BvrNoHGLhvXdvJCg6E0'
rcParams['font.family'] = 'Noto Sans JP'

# 今日を起点にして2日前〜6日前の曜日名をリスト形式で取得（スクレイピングする日付が「今日」「昨日」「n曜日」...となっているため）
today = datetime.now()
weekdays_en = [(today - timedelta(days=i)).strftime('%A') for i in range(2, 7)] # まず英語で曜日を取得
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

# ISO 8601形式の時間を秒数に変換。get_video_details内で使用
def convert_duration_to_sec(iso_duration):
    duration = parse_duration(iso_duration)
    total_seconds = int(duration.total_seconds())
    return total_seconds

# 秒数を「時間」「分」「秒」に変換。基本は秒で受け渡してこの関数で最後に形式変更する
def convert_seconds_to_hrs_min_sec(total_seconds):
    hours = total_seconds // 3600
    remainder = total_seconds % 3600
    minutes = remainder // 60
    seconds = remainder % 60
    return hours, minutes, seconds

# URLからidを取得。fetch_data_for_date内で使用
def extract_video_id(url):
    parsed_url = urlparse(url)
    if 'youtube.com' in parsed_url.netloc:
        query_params = parse_qs(parsed_url.query)
        return query_params.get('v', [None])[0]
    else:
        return None

# URLから視聴秒数を取得。fetch_data_for_date内で使用
def extract_viewing_time(url):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query) # クエリをtをキーに辞書形式で格納。
    t_param = query_params.get('t', [None])[0] # クエリをtをキーに取り出す。なければNone

    if t_param and 's' in t_param:
        return int(t_param.replace('s', '')) # s（秒）を外して数字のみ返す
    else:
        return t_param # Noneを返す

# カテゴリidからカテゴリ名を取得。get_video_details内で使用
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

# 動画idから必要な情報を取得。fetch_data_for_date内で使用
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
        category_name = get_category_name(category_id) # カテゴリidからカテゴリ名を取得
        total_sec = convert_duration_to_sec(duration) # ISO 8601形式の時間を秒数に変換
        return title, category_name, channel_name, total_sec
    else:
        return None, None, None, None

# 特定の曜日の動画URLをスクレイピングし、idを抽出。APIを使用して視聴履歴の必要データを格納。視聴データのない曜日は曜日のみ格納。get_history_data内で使用。
def fetch_data_for_date(date_label, browser):
    data = []
    xpath_query = f"//ytd-item-section-renderer[contains(@class, 'style-scope ytd-section-list-renderer')][.//div[@id='title' and contains(text(), '{date_label}')]]"
    elements = browser.find_elements(By.XPATH, xpath_query)
    
    if not elements: # 要素が見つからなかった場合、空のデータリストを返す
        return data

    # 基本的には1個しか無いはずだが、一応「月曜日」などと書いた要素の1番目をelementに格納。動画情報を格納
    element = elements[0]
    links = element.find_elements(By.XPATH, ".//a[@id='video-title']") # 'id="video-title"'を持つ<a>タグのみを対象とする

    for link in links:
        url = link.get_attribute('href')
        video_id = extract_video_id(url) # URLからidを取得
        if video_id:
            title, category_name, channel_name, total_sec = get_video_details(video_id) # 動画idから必要な情報を取得
            viewing_time = extract_viewing_time(url) or total_sec # URLから視聴秒数を取得。Noneの場合は全部見たということなのでtotal_secが視聴秒数
            data.append({
                'title': title,
                'category_name': category_name,
                'channel_name': channel_name,
                'total_sec': total_sec,
                'viewing_time': viewing_time
            })
    return data # 特定の日付の視聴履歴作成

# YouTubeの言語設定に基づいて日付ラベルを選択（英語で利用するユーザーがいるため）。get_history_data内で使用
def get_date_labels(browser):

    language = browser.execute_script("return document.documentElement.lang;") # ページの言語設定を取得
    
    if language == 'ja-JP':
        date_labels = ['今日', '昨日'] + weekdays_jp
    else:
        date_labels = ['Today', 'Yesterday'] + weekdays_en # 日本語以外は英語

    return date_labels

# 日付ごとにスクレイピングと情報の格納を実行
def get_history_data(browser):
    history_data = {}
    date_labels = get_date_labels(browser) # YouTubeの言語設定に基づいて日付ラベルを選択
    date_labels.reverse() # 逆にする。使用したいのは古い順なので
    st.session_state['date_labels'] = date_labels  # Streamlitのセッションに日付ラベルを保存。どんな場合もすべての曜日が入る

    for date_label in date_labels:
        history_data[date_label] = fetch_data_for_date(date_label, browser) # 日付ごとに視聴データを格納

    return history_data # 日付ごとに視聴データを格納。各視聴データは動画idごとに必要データが格納。

# 与えられた情報を元にグラフを描画。カテゴリごとに分けられた視聴時間（category_wise_data）を足し合わせてグラフ作成。update_graph（グラフの更新）または更新前のグラフ情報をそのまま描画するときに使用
def draw_graph(days, category_wise_data):
    plt.figure(figsize=(12, 6))
    bottom = [0] * len(days)
    total_per_day = [0] * len(days)  # 各日についての視聴時間の合計を保持するリスト

    custom_colors = ['#B7D957', '#8CD2FF', '#F0D24B', '#D89ACA', '#CBC5A9', 
                    '#5DBAE6', '#FAC363', '#95B9C6'] # グラフのカラーリスト
    if len(category_wise_data) > len(custom_colors):
        custom_colors.extend(['#95B9C6'] * (len(category_wise_data) - len(custom_colors))) # カテゴリの数がカスタムカラーリストより多い場合、残りは '#95B9C6' で埋める

    # カテゴリごとに棒グラフを描画
    for (category, times), color in zip(category_wise_data.items(), custom_colors):
        plt.bar(days, times, bottom=bottom, color=color, width=0.5, label=category)
        bottom = [x + y for x, y in zip(bottom, times)]
        total_per_day = [x + y for x, y in zip(total_per_day, times)]

    plt.title('1週間の視聴時間', fontsize=18, color='#5C5C5C', fontweight='bold', loc='left', pad=24)

    plt.xticks(days, fontsize=14, color='#999999')
    plt.yticks(fontsize=14, color='#999999')
    
    plt.gca().tick_params(axis='x', direction='out', pad=12)
    plt.gca().tick_params(axis='y', direction='out', pad=12)

    plt.tick_params(axis='both', which='both', length=0) # 目盛りの短い線を消す

    for spine in plt.gca().spines.values():
        spine.set_visible(False)
    plt.gca().spines['bottom'].set_visible(True)
    plt.gca().spines['bottom'].set_color('#EBEBEB')  # グラフの外枠を調整

    plt.grid(axis='y', visible=False) # グラフの縦線（Y軸のグリッド）を消す

    # グラフの横線の色を設定
    plt.gca().yaxis.grid(True, linestyle='-', linewidth=1)
    plt.gca().yaxis.grid(True, color='#F2F2F2')
    plt.gca().set_axisbelow(True)

    # グラフ量の作成
    for i, day in enumerate(days):
        yvalue = total_per_day[i]
        hours, minutes, seconds = convert_seconds_to_hrs_min_sec(int(yvalue * 60))

        time_str = ""
        if hours > 0:
            time_str += f"{hours}時間"
        if minutes > 0:
            time_str += f"{minutes}分"
        if seconds > 0:
            time_str += f"{seconds}秒"

        if time_str:
            plt.text(day, yvalue + 4, time_str, ha='center', va='bottom', fontsize=14, color='#5C5C5C')

    # カスタム凡例を作成
    legend_elements = [Line2D([0], [0], marker='o', color='w', label=category,
                            markersize=10, markerfacecolor=color, markeredgewidth=0) for category, color in zip(category_wise_data.keys(), custom_colors)]

    # 凡例を追加・位置調整
    legend = plt.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=len(category_wise_data), frameon=False)
    for text in legend.get_texts():
        text.set_color('#5C5C5C')
        text.set_fontsize(12)

    plt.subplots_adjust(bottom=0.15) 
    st.pyplot(plt)


# selected_categories視聴時間をカテゴリごとに合計し、グラフ化。selected_categoriesに更新があったときのみ実行
def update_graph(selected_categories, history_data):
    days = st.session_state['date_labels']
    category_wise_data = {category: [0] * len(days) for category in selected_categories}

    for i, day in enumerate(days):
        videos = history_data.get(day, [])
        for video in videos:
            if video['category_name'] in selected_categories:
                category_wise_data[video['category_name']][i] += video['viewing_time'] / 60  # 秒を分に変換

    # セッションに「graph_data」を格納。カテゴリの変更がない場合はグラフの変更がないため、再計算せずこの値を使用して再描画する
    st.session_state['graph_data'] = {
        'days': days,
        'category_wise_data': category_wise_data
    }

    draw_graph(days, category_wise_data)

# 選択した日付の視聴時間、評価、最も見たカテゴリというサマリーを表示。
def display_summary(history_data, selected_date, selected_categories):
    # 選択された日のデータ
    selected_day_data = history_data.get(selected_date, [])
    selected_day_seconds = sum(video['viewing_time'] for video in selected_day_data if video['category_name'] in selected_categories)

    # 前日のデータ
    selected_index = st.session_state['date_labels'].index(selected_date)
    if selected_index > 0:
        prev_date = st.session_state['date_labels'][selected_index - 1]
    else:
        prev_date = None  # selected_dateがリストの最初の要素であれば、Noneを返す
    
    # 前日のデータ
    if prev_date != None:
        prev_day_data = history_data.get(prev_date, [])
        prev_day_seconds = sum(video['viewing_time'] for video in prev_day_data if video['category_name'] in selected_categories)
    else:
        prev_day_seconds = 0  # Noneであれば（selected_dateがリストの最初の要素であれば）0とする（前日の視聴時間0）
    
    time_diff = selected_day_seconds - prev_day_seconds # 視聴時間の差分計算
    # 時間差の絶対値を取得
    abs_time_diff = abs(time_diff)

    # 評価の決定
    if selected_day_seconds < 1800:
        rating, subtext = "Great", "素晴らしい！"
    elif 1800 <= selected_day_seconds < 3600:
        rating, subtext = "Good", "悪くない！"
    elif 3600 <= selected_day_seconds < 7200:
        rating, subtext = "Fine", "頑張ろう！"
    elif 7200 <= selected_day_seconds < 14400:
        rating, subtext = "Bad", "注意しよう！"
    else:
        rating, subtext = "Terrible", "生活を見直そう！"

    # 視聴時間の長いカテゴリの決定
    category_times = {}
    for video in selected_day_data:
        if video['category_name'] in selected_categories:
            category_times[video['category_name']] = category_times.get(video['category_name'], 0) + video['viewing_time']
    
    sorted_categories = sorted(category_times.items(), key=lambda x: x[1], reverse=True)
    top_category = sorted_categories[0][0] if sorted_categories else "なし"
    second_category = sorted_categories[1][0] if len(sorted_categories) > 1 else "なし"

    # Metrics UIを使って表示
    col1, col2, col3 = st.columns(3)
    
    # 「視聴時間」の表示
    with col1:
        # 時間と分のフォーマットを別々に処理
        hours = selected_day_seconds // 3600
        minutes = (selected_day_seconds % 3600) // 60
        viewing_time_formatted = f"{hours}時間 {minutes}分" if hours > 0 else f"{minutes}分"

        # 時間差のフォーマットも同様に処理
        time_diff_hours = abs_time_diff // 3600
        time_diff_minutes = (abs_time_diff % 3600) // 60
        time_diff_formatted = f"{time_diff_hours}時間 {time_diff_minutes}分" if time_diff_hours > 0 else f"{time_diff_minutes}分"
        time_diff_color = "red" if time_diff > 0 else "green"
        arrow = "↑" if time_diff > 0 else "↓" if time_diff < 0 else ""

        st.markdown(
            f"<div style='text-align: center; background-color: #F8F9FB; padding: 16px 24px; border-radius: 8px; margin: 16px 0;'>"
            f"<span style='font-size: 14px; color: #5C5C5C;'>視聴時間</span><br>"
            f"<span style='font-size: 32px; font-weight: medium;'>{viewing_time_formatted}</span><br>"
            f"<span style='color: {time_diff_color}; font-size: 14px;'>前日比：{arrow} {time_diff_formatted}</span>"
            f"</div>", unsafe_allow_html=True
        )
        
    # 「評価」の表示
    with col2:
        rating_color = "red" if rating in ["Bad", "Terrible"] else ("black" if rating == "Fine" else "green")
        st.markdown(
            f"<div style='text-align: center; background-color: #F8F9FB; padding: 16px 24px; border-radius: 8px; margin: 16px 0;'>"
            f"<span style='font-size: 14px; color: #5C5C5C;'>評価</span><br>"
            f"<span style='font-size: 32px; font-weight: medium; color: {rating_color};'>{rating}</span><br>"
            f"<span style='color: {rating_color}; font-size: 14px;'>{subtext}</span>"
            f"</div>", unsafe_allow_html=True
        )


    # 「視聴時間の長いカテゴリ」の表示
    with col3:
        st.markdown(
            f"<div style='text-align: center; background-color: #F8F9FB; padding: 16px 24px; border-radius: 8px; margin: 16px 0;'>"
            f"<span style='font-size: 14px; color: #5C5C5C;'>視聴時間の長いカテゴリ</span><br>"
            f"<span style='font-size: 32px; font-weight: medium;'>{top_category}</span><br>"
            f"<span style='font-size: 14px;'>2番目に長い： {second_category}</span>"
            f"</div>", unsafe_allow_html=True
        )
        
# 視聴履歴データを表示
def show_history_data(history_data, selected_date, selected_categories):
    data = history_data.get(selected_date, [])
    
    # 見出し表示
    st.markdown(f"""
        <style>
            .subtitle {{
                font-size:20px !important;
                font-weight: 500;
                color: #5C5C5C;
                text-align: center;
            }}
        </style>
        <p class='subtitle'>視聴データ</p>
        """, unsafe_allow_html=True)
    
    if data:
        rows = []
        for video in data:
            if video['category_name'] in selected_categories:
                hours, minutes, seconds = convert_seconds_to_hrs_min_sec(video['viewing_time'])
                rows.append({
                    "タイトル": video['title'],
                    "視聴時間": f"{hours}時間{minutes}分{seconds}秒",
                    "カテゴリ": video['category_name'],
                    "チャンネル": video['channel_name']
                })
        df = pd.DataFrame(rows) # 動画ごとに必要情報をまとめ

        # 視聴時間の秒数でソート
        df['視聴時間_秒'] = [
            convert_seconds_to_hrs_min_sec(video['viewing_time'])[0] * 3600 +
            convert_seconds_to_hrs_min_sec(video['viewing_time'])[1] * 60 +
            convert_seconds_to_hrs_min_sec(video['viewing_time'])[2]
            for video in data if video['category_name'] in selected_categories
        ]
        df.sort_values(by="視聴時間_秒", ascending=False, inplace=True)
        df.drop(columns=["視聴時間_秒"], inplace=True)
        
        st.dataframe(df) # データの表示
    else:
        st.write(f"視聴履歴はありません。")

# 日付ごとにボタンを表示して、選択された日付の視聴履歴を表示
def display_history_buttons(history_data, selected_categories):
    date_labels = st.session_state['date_labels']
    
    # pills コンポーネントを使用して日付を選択
    selected_date = pills(
        "Select a date",
        options=date_labels,
        format_func=lambda x: x,
        index=len(date_labels) - 1,
        label_visibility="collapsed",
    )
    
    # 大見出し表示
    st.markdown(f"""
        <style>
            .maintitle {{
                font-size: 32px !important;
                font-weight: 600;
                color: #262626;
                text-align: center;
                
            }}
        </style>
        <p class='maintitle'>{selected_date}</p>
        """, unsafe_allow_html=True)

    display_summary(history_data, selected_date, selected_categories) # 視聴時間と評価のサマリーを表示

    show_history_data(history_data, selected_date, selected_categories) # 選択された日付の視聴履歴を表示

# 要素がクリック可能になるまでWebDriverを待機。スクレイピング失敗防止。start_button_clicked内で使用
def wait_for_element_clickable(browser, by, value, timeout=300):
    return WebDriverWait(browser, timeout).until(EC.element_to_be_clickable((by, value)))

# スクレイピングの開始。「スタート」ボタンをクリックしたら実行
def start_button_clicked(input_email_or_phone, input_password):
    options = Options()
    # options = webdriver.ChromeOptions()
    if platform.system() == "Linux":
        options.add_argument("--headless=new")
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        browser = webdriver.Chrome(options=options)
        # driver = webdriver.Chrome(service=ChromiumService(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()))
        
    else:
        # ここにLinux以外（例えばmacOS）のコードを記述
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.105 Safari/537.36"
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--user-agent=' + ua)
        chrome_service = Service(executable_path=ChromeDriverManager().install())
        browser = webdriver.Chrome(service=chrome_service, options=options)
    
    
    browser.get('https://www.youtube.com/feed/history')
    st.write("ブラウザゲット直後")
    # 各要素クリック可能になってから実行
    # JavaScriptがロードされるのを待つ
    # time.sleep(10)  # 10秒待機
    
    # ページのHTMLを取得
    #html_content = browser.page_source
    # BeautifulSoupでHTMLを解析
    #soup = BeautifulSoup(html_content, 'html.parser')

    # スクリプトとスタイルを除去
    #for script_or_style in soup(["script", "style"]):
    #    script_or_style.extract()  # スクリプトとスタイルタグを取り除く

    # HTMLテキストのみを取得
    #text = soup.get_text()
    
    # StreamlitでHTMLを表示
    #st.write(text)
    language = browser.execute_script("return document.documentElement.lang;") # ページの言語設定を取得
    st.write(language)
    wait_for_element_clickable(browser, By.XPATH, "//ytd-button-renderer[contains(., 'Sign in')]").click()
    # wait_for_element_clickable(browser, By.XPATH, "//ytd-button-renderer[contains(., 'ログイン')]").click()
    st.write("1つ目完了")
    time.sleep(10)
    
    # ページのHTMLを取得
    html_content = browser.page_source
    # BeautifulSoupでHTMLを解析
    soup = BeautifulSoup(html_content, 'html.parser')

    # スクリプトとスタイルを除去
    for script_or_style in soup(["script", "style"]):
        script_or_style.extract()  # スクリプトとスタイルタグを取り除く

    # HTMLテキストのみを取得
    text = soup.get_text()
    
    # StreamlitでHTMLを表示
    st.write(text)
    
    wait_for_element_clickable(browser, By.CSS_SELECTOR, 'input[aria-label="Email or phone"]').send_keys(input_email_or_phone) # メールアドレス入力
    # wait_for_element_clickable(browser, By.CSS_SELECTOR, 'input[aria-label="メールアドレスまたは電話番号"]').send_keys(input_email_or_phone) # メールアドレス入力
    st.write("2つ目完了")
    wait_for_element_clickable(browser, By.XPATH, "//button[contains(., 'Next')]").click()  # 次へボタンをクリック
    # wait_for_element_clickable(browser, By.XPATH, "//button[contains(., '次へ')]").click()  # 次へボタンをクリック
    
    st.write("3つ目完了")
    wait_for_element_clickable(browser, By.CSS_SELECTOR, 'input[aria-label="Enter your password"]').send_keys(input_password)    # パスワード入力
    # wait_for_element_clickable(browser, By.CSS_SELECTOR, 'input[aria-label="パスワードを入力"]').send_keys(input_password)    # パスワード入力
    st.write("4つ目完了")

    try: # 次へボタンをクリック（失敗しやすいのでエラーハンドリング）
        next_button = wait_for_element_clickable(browser, By.XPATH, "//button[contains(., 'Next')]")
        # next_button = wait_for_element_clickable(browser, By.XPATH, "//button[contains(., '次へ')]")
        next_button.click()
    except StaleElementReferenceException: # エラーが発生した場合、要素を再取得して操作を試みる
        next_button = wait_for_element_clickable(browser, By.XPATH, "//button[contains(., 'Next')]")
        # next_button = wait_for_element_clickable(browser, By.XPATH, "//button[contains(., '次へ')]")
        next_button.click()
    st.write("これで開ける！")
    
    # ヘッダーが操作可能になるまで待つ（スクレイピング失敗防止）
    wait_for_element_clickable(browser, By.ID, "masthead-container")
    st.write("ヘッダー操作可能")
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
        
    return history_data, list(unique_category_names)  

# サイドバーに入力フィールドを作成
email_or_phone = st.sidebar.text_input("メールアドレスまたは電話番号")
password = st.sidebar.text_input("パスワード", type="password")  # type="password"でテキストを隠す

# start_button_clicked実行。その後セッションにhistory_data（視聴履歴）・unique_category_names（ユニークなカテゴリ一覧）を入れて保存。カテゴリの変更を検知するためst.session_state['prev_selected_categories']作成
if email_or_phone and password and st.sidebar.button("スタート"):
    history_data, unique_category_names = start_button_clicked(email_or_phone, password) 
    st.session_state['history_data'] = history_data
    st.session_state['unique_category_names'] = unique_category_names
    st.session_state['prev_selected_categories'] = []

# カテゴリ選択の作成。デフォルトで「科学と技術」「教育」をカテゴリから外して視聴時間を算出する（無駄な時間のみを算出するため）
if 'unique_category_names' in st.session_state:
    
    default_selection = list(st.session_state['unique_category_names'])
    
    # 特定のカテゴリがst.session_state['unique_category_names']に存在する場合、そのカテゴリのデフォルト選択を外す
    if '科学と技術' in default_selection:
        default_selection.remove('科学と技術')
    if '教育' in default_selection:
        default_selection.remove('教育')
    
    selected_categories = st.sidebar.multiselect("カテゴリを選択", st.session_state['unique_category_names'], default=default_selection) # 選択肢はカテゴリ全て、デフォルトで選択状態なのは特定のカテゴリ以外


# 選択されているカテゴリ（selected_categories）と直前に選択されていたカテゴリ（prev_selected_categories）が異なるときのみグラフを更新。同じ場合は保存されたグラフデータを使用して再描画する（毎回描画するとグラフが毎回消えて使いづらいため）
if 'history_data' in st.session_state and 'unique_category_names' in st.session_state:
    
    if selected_categories != st.session_state.get('prev_selected_categories', []): # 選択されているカテゴリ（selected_categories）と直前に選択されていたカテゴリ（prev_selected_categories）が異なるとき
        update_graph(selected_categories, st.session_state['history_data']) 
        # 現在のselected_categoriesを保存
        st.session_state['prev_selected_categories'] = selected_categories # selected_categoriesをprev_selected_categories に代入する

    elif 'graph_data' in st.session_state:
        # グラフデータがセッション状態に存在する場合、そのデータを使用してグラフを再描画
        days = st.session_state['graph_data']['days']
        category_wise_data = st.session_state['graph_data']['category_wise_data']
        draw_graph(days, category_wise_data)

# スクレイピングが完了した後は更新のたびに視聴データ・ボタンを更新
if 'history_data' in st.session_state and 'unique_category_names' in st.session_state:
    display_history_buttons(st.session_state['history_data'], selected_categories)

