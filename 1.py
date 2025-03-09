import requests
from bs4 import BeautifulSoup
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from random import uniform

PAGE_URL = "https://thedaddy.to/24-7-channels.php"
BASE_URLS = [
    "https://nfsnew.koskoros.ru/nfs/premium{}/mono.m3u8",
    "https://wikinew.koskoros.ru/wiki/premium{}/mono.m3u8",
    "https://zekonew.koskoros.ru/zeko/premium{}/mono.m3u8",
    "https://zekonew.iosplayer.ru/zeko/premium{}/mono.m3u8",
    "https://ddy6new.koskoros.ru/ddy6/premium{}/mono.m3u8",
    "https://ddy6new.iosplayer.ru/ddy6/premium{}/mono.m3u8",
    "https://ddh2new.iosplayer.ru/ddh2/premium{}/mono.m3u8",
    "https://windnew.koskoros.ru/wind/premium{}/mono.m3u8",
    "https://windnew.iosplayer.ru/wind/premium{}/mono.m3u8",
    "https://dokko1new.koskoros.ru/dokko1/premium{}/mono.m3u8",
    "https://dokko1new.iosplayer.ru/dokko1/premium{}/mono.m3u8",
    "https://top2new.koskoros.ru/top2/premium{}/mono.m3u8",
    "https://top2new.iosplayer.ru/top2/premium{}/mono.m3u8"
]
DEFAULT_LOGO = "https://raw.githubusercontent.com/pixilated730/icons-for-me-/main/icons/oing.jpeg"
M3U8_HEADER = """#EXTM3U url-tvg="https://github.com/dtankdempse/daddylive-m3u/raw/refs/heads/main/epg.xml"\n"""

class RateLimitedSession:
    def __init__(self, base_url):
        self.session = requests.Session()
        self.base_url = base_url
        self.last_request = 0
        self.min_interval = 0.5

    def get(self, url, **kwargs):
        current_time = time.time()
        time_since_last = current_time - self.last_request
        if time_since_last < self.min_interval:
            time.sleep(self.min_interval - time_since_last)
        try:
            response = self.session.get(url, **kwargs)
            self.last_request = time.time()
            return response
        except requests.exceptions.RequestException as e:
            print(f"[{time.strftime('%H:%M:%S')}] Request error for {url}: {e}")
            self.last_request = time.time()
            raise

sessions = {base_url: RateLimitedSession(base_url) for base_url in BASE_URLS}

def check_stream_url(url):
    base_url = next((base for base in BASE_URLS if base.split('/')[2] in url), None)
    session = sessions[base_url] if base_url else requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Origin': 'https://newzar.xyz',
        'Referer': 'https://newzar.xyz/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site',
        'Connection': 'keep-alive'
    }
    try:
        response = session.get(url, timeout=5, headers=headers)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def write_channel_to_m3u8(channel, m3u8_file):
    m3u8_file.write(
        f'#EXTINF:-1 tvg-id="{channel["name"].replace(" ", ".")}" '
        f'tvg-name="{channel["name"]}" tvg-logo="{DEFAULT_LOGO}" '
        f'group-title="eyepapcorn",{channel["number"]} | {channel["name"]}\n'
    )
    m3u8_file.write(f"{channel['url']}\n")
    m3u8_file.flush()
    print(f"[{time.strftime('%H:%M:%S')}] Wrote working channel {channel['number']} to m3u8")

def process_channel(item):
    try:
        a_tag = item.find('a')
        if not a_tag:
            return None
        stream_path = a_tag.get('href', '')
        channel_number = stream_path.split('-')[-1].split('.')[0]
        if not channel_number.isdigit():
            return None
        channel_name = a_tag.find('span').find('strong').text.strip()
        if "18+" in channel_name:
            return None
        working_url = None
        for base_url in BASE_URLS:
            stream_url = base_url.format(channel_number)
            if check_stream_url(stream_url):
                working_url = stream_url
                break
            time.sleep(0.1)
        result = {
            'name': channel_name,
            'number': channel_number,
            'url': working_url,
            'status': 'working' if working_url else '404'
        }
        return result
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Error processing channel {channel_number}: {e}")
        return None

def main():
    start_time = time.time()
    failed_channels = []
    print(f"[{time.strftime('%H:%M:%S')}] Fetching channel list from {PAGE_URL}")
    try:
        response = requests.get(PAGE_URL, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        grid_items = soup.find_all('div', class_='grid-item')
        if not grid_items:
            print("No channels found on the page!")
            return
        total_channels = len(grid_items)
        print(f"[{time.strftime('%H:%M:%S')}] Found {total_channels} channels to process")
        processed = 0
        working_count = 0
        not_working_count = 0
        with open("eyepapcorn.m3u8", "w", encoding="utf-8") as m3u8_file, \
             open("404.json", "w", encoding="utf-8") as json_file:
            m3u8_file.write(M3U8_HEADER)
            m3u8_file.flush()
            print(f"[{time.strftime('%H:%M:%S')}] Initialized m3u8 file")
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(process_channel, item): item for item in grid_items}
                for future in as_completed(futures):
                    processed += 1
                    result = future.result()
                    if result:
                        if result['status'] == 'working':
                            working_count += 1
                            write_channel_to_m3u8(result, m3u8_file)
                        else:
                            not_working_count += 1
                            failed_channels.append(result)
                            json.dump(result, json_file)
                            json_file.write('\n')
                            json_file.flush()
                            print(f"[{time.strftime('%H:%M:%S')}] Wrote 404 channel {result['number']} to json")
                    print(f"[{time.strftime('%H:%M:%S')}] Progress: {processed}/{total_channels} ({(processed/total_channels*100):.1f}%)")
        end_time = time.time()
        print(f"\n[{time.strftime('%H:%M:%S')}] Complete in {end_time - start_time:.2f} seconds:")
        print(f"Working: {working_count}")
        print(f"Not working: {not_working_count}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] An error occurred: {e}")
        raise

if __name__ == "__main__":
    main()