import streamlit as st
from selenium import webdriver
import chromedriver_binary
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome import service as fs
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time


def start_button_clicked(input_email_or_phone, input_password):
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.105 Safari/537.36"
    # ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

    options = webdriver.ChromeOptions()
    options.add_argument('--user-agent=' + ua)
    options.add_argument('--disable-blink-features=AutomationControlled')
    
    # ChromeDriverのパスを取得してServiceオブジェクトを初期化
    chrome_service = ChromeService(executable_path=ChromeDriverManager().install())
    
    # chrome_service = fs.Service(executable_path='chromedriver-117.exe')
    # chrome_service = fs.Service(executable_path='path_to_chromedriver_for_version_119.exe')

    # browser = webdriver.Chrome(options=options, service=chrome_service)
    # browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    # browser = webdriver.Chrome(executable_path=ChromeDriverManager().install(), options=options)
    
    # Serviceオブジェクトとオプションを使用してブラウザを初期化
    browser = webdriver.Chrome(service=chrome_service, options=options)



    
    browser.get('https://www.youtube.com/feed/history')
    
    # driver = webdriver.Chrome()
    # driver.get('https://www.youtube.com/')

    elem_login_btn2 = browser.find_elements(By.TAG_NAME, 'ytd-button-renderer')

    i = 0
    array_i = 0
    for e in elem_login_btn2:
        if e.text == "ログイン":
            array_i = i
        i +=1   
    elem_login_btn3 = elem_login_btn2[array_i].click()

    elem_login_btn4 = browser.find_elements(By.TAG_NAME, 'input')

    i = 0
    array_i = 0
    for e in elem_login_btn4:
        if e.get_attribute('aria-label') == "メールアドレスまたは電話番号":
            array_i = i
        i +=1

    elem_login_btn5 = elem_login_btn4[array_i]
    elem_login_btn5.send_keys(input_email_or_phone)
    
    elem_login_btn6 = browser.find_elements(By.TAG_NAME, 'button')

    i = 0
    array_i = 0
    for e in elem_login_btn6:
        if e.text == "次へ":
            array_i = i
        i +=1

    # elem_login_btn6[array_i].click()
    
    # elem_login_btn7 = browser.find_elements(By.TAG_NAME, 'input')

    # i = 0
    # array_i = 0
    # for e in elem_login_btn7:
    #     if e.get_attribute('aria-label') == "パスワードを入力":
    #         array_i = i
    #     i +=1

    # elem_login_btn8 = elem_login_btn7[array_i]
    # elem_login_btn8.send_keys(input_password)
    
    # elem_login_btn9 = browser.find_elements(By.TAG_NAME, 'button')
    
    elem_login_btn6[array_i].click()

    # "次へ"ボタンをクリックした後、パスワード入力フィールドが表示されるまで待機
    wait = WebDriverWait(browser, 10)  # 最大で10秒待機
    elem_login_btn8 = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[aria-label="パスワードを入力"]')))

    elem_login_btn8.send_keys(input_password)

    elem_login_btn9 = browser.find_elements(By.TAG_NAME, 'button')

    i = 0
    array_i = 0
    for e in elem_login_btn9:
        if e.text == "次へ":
            array_i = i
        i +=1

    elem_login_btn9[array_i].click()
    
    time.sleep(10)
    # idが「contents」の要素配下のすべての要素を取得
    # elements = browser.find_elements_by_css_selector("#contents *")

    elements = browser.find_elements(By.ID, "contents")
    # 要素のテキストなどを表示
    for element in elements:
        print(element.text)

    # ブラウザを閉じる
    browser.quit()
    

# サイドバーに入力フィールドを作成
email_or_phone = st.sidebar.text_input("メールアドレスまたは電話番号")
password = st.sidebar.text_input("パスワード", type="password")  # type="password"でテキストを隠す

# 両方のフィールドに入力がある場合にのみ「スタート」ボタンを表示
if email_or_phone and password:
    if st.sidebar.button("スタート"):
        start_button_clicked(email_or_phone, password)
        st.write("スタートボタンが押されました")


        
        
