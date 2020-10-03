import sys
import os
import json
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
options = Options()
options.add_argument("--headless")
# ref : https://chromedriver.chromium.org/downloads
driver = webdriver.Chrome('chromedriver', options=options)
driver.implicitly_wait(3)
#import selenium

BASE_URL = 'https://m.skbroadband.com/content/realtime/Realtime_List.do'
# Example : https://m.skbroadband.com/content/realtime/Channel_List.do?key_depth1=5100&key_depth2=14&key_depth4=PM50305785
sid_pattern = re.compile('.*key_depth2=([0-9]+)')

if __name__ == '__main__':
    channel_data = []
    driver.get(BASE_URL)
    categories = driver.find_elements_by_xpath('//*[@id="channel-list"]/div')
    index = 1
    for category in categories:
        channels = category.find_elements_by_xpath('.//div[2]/table/tbody/tr')
        for channel in channels:
            chnum = channel.find_element_by_xpath('.//th')
            chname = channel.find_element_by_xpath('.//td/a')
            group = sid_pattern.match(chname.get_attribute('href'))
            if group:
                ch_num = int(chnum.text.strip('[]'))
                ch_name = chname.text
                service_id = group[1]
                channel_info = {
                    'Id': index,
                    'Name': ch_name,
                    'SKB Name': ch_name,
                    'SKBCh': ch_num,
                    'Icon_url': f'http://mapp.btvplus.co.kr/data/btvplus/admobd/channelLogo/nsepg_{service_id}.png',
                    'Source': 'SKB',
                    'ServiceId': service_id
                }
                channel_data.append(channel_info)
                index += 1
    with open('AllChannel.json', 'wt') as f:
        f.write(json.dumps(channel_data, indent=2))
    print('Done.')
