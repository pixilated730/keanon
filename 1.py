import requests
from bs4 import BeautifulSoup
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from random import uniform

# URLs and constants
PAGE_URL = "https://thedaddy.to/24-7-channels.php"
BASE_URLS = [
    "https://zekonew.iosplayer.ru/zeko/premium{}/mono.m3u8",
    "https://ddy6new.iosplayer.ru/ddy6/premium{}/mono.m3u8",
    "https://ddh2new.iosplayer.ru/ddh2/premium{}/mono.m3u8",
    "https://windnew.iosplayer.ru/wind/premium{}/mono.m3u8",
    "https://dokko1new.iosplayer.ru/dokko1/premium{}/mono.m3u8",
    "https://top2new.iosplayer.ru/top2/premium{}/mono.m3u8"
]
DEFAULT_LOGO = "https://raw.githubusercontent.com/pixilated730/icons-for-me-/main/icons/oing.jpeg"
M3U8_HEADER = """#EXTM3U url-tvg="https://github.com/dtankdempse/daddylive-m3u/raw/refs/heads/main/epg.xml"\n"""

# Maintain separate session and rate limit tracking for each base URL
class RateLimitedSession:
    def __init__(self, base_url):
        self.session = requests.Session()
        self.base_url = base_url
        self.last_request = 0
        self.min_interval = 1.0  # Minimum time between requests
        self.backoff_time = 1.0  # Initial backoff time
        self.max_backoff = 30.0  # Maximum backoff time

    def get(self, url, **kwargs):
        current_time = time.time()
        time_since_last = current_time - self.last_request
        
        if time_since_last < self.min_interval:
            time.sleep(self.min_interval - time_since_last)
        
        try:
            response = self.session.get(url, **kwargs)
            
            if response.status_code == 429:
                time.sleep(self.backoff_time)
                self.backoff_time = min(self.backoff_time * 2, self.max_backoff)
                raise requests.exceptions.RequestException("Rate limited")
            
            # Reset backoff on successful request
            self.backoff_time = 1.0
            self.last_request = time.time()
            return response
            
        except requests.exceptions.RequestException:
            self.last_request = time.time()
            raise

sessions = {base_url: RateLimitedSession(base_url) for base_url in BASE_URLS}

def check_stream_url(url, max_retries=5):
    base_url = next(base for base in BASE_URLS if base.split('/')[2] in url)
    session = sessions[base_url]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Connection': 'keep-alive'
    }
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                sleep_time = min(2 ** attempt, 10)  # Exponential backoff
                time.sleep(uniform(sleep_time, sleep_time + 2))
            
            response = session.get(url, timeout=10, stream=True, headers=headers)
            
            if response.status_code == 404:
                continue  # Try other attempts for 404s
                
            if response.status_code != 200:
                time.sleep(uniform(1, 3))
                continue
                
            content_start = next(response.iter_lines(), None)
            if content_start and b'#EXTM3U' in content_start:
                return True
            
        except requests.exceptions.RequestException:
            if attempt == max_retries - 1:
                return False
            continue
        except Exception:
            continue
    
    return False

def verify_404_channels(failed_channels, m3u8_file):
    print("\nVerifying channels marked as 404...")
    working_after_retry = 0
    
    for channel in failed_channels:
        print(f"Retrying channel {channel['number']}: {channel['name']}")
        
        # Try each base URL again with increased patience
        for base_url in BASE_URLS:
            stream_url = base_url.format(channel['number'])
            if check_stream_url(stream_url, max_retries=7):  # More retries for verification
                channel['url'] = stream_url
                channel['status'] = 'working'
                write_channel_to_m3u8(channel, m3u8_file)
                working_after_retry += 1
                print(f"Success! Channel {channel['number']} is working")
                break
            time.sleep(0.5)  # Delay between base URL attempts
    
    return working_after_retry

def write_channel_to_m3u8(channel, m3u8_file):
    m3u8_file.write(
        f'#EXTINF:-1 tvg-id="{channel["name"].replace(" ", ".")}" '
        f'tvg-name="{channel["name"]}" tvg-logo="{DEFAULT_LOGO}" '
        f'group-title="eyepapcorn",{channel["number"]} | {channel["name"]}\n'
    )
    m3u8_file.write(f"{channel['url']}\n")
    m3u8_file.flush()

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
        
        # Try each URL
        working_url = None
        for base_url in BASE_URLS:
            stream_url = base_url.format(channel_number)
            if check_stream_url(stream_url):
                working_url = stream_url
                break
            time.sleep(0.2)  # Small delay between attempts
        
        return {
            'name': channel_name,
            'number': channel_number,
            'url': working_url,
            'status': 'working' if working_url else '404'
        }
        
    except Exception as e:
        print(f"Error processing channel: {str(e)}")
        return None

def main():
    start_time = time.time()
    failed_channels = []
    
    try:
        # Get channel list
        response = requests.get(PAGE_URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        grid_items = soup.find_all('div', class_='grid-item')
        
        total_channels = len(grid_items)
        processed = 0
        working_count = 0
        not_working_count = 0
        
        # Open files for real-time writing
        with open("eyepapcorn.m3u8", "w", encoding="utf-8") as m3u8_file, \
             open("404.json", "w", encoding="utf-8") as json_file:
            
            # Write M3U8 header
            m3u8_file.write(M3U8_HEADER)
            
            # Process channels with limited concurrency
            with ThreadPoolExecutor(max_workers=2) as executor:  # Reduced workers
                futures = []
                for item in grid_items:
                    future = executor.submit(process_channel, item)
                    futures.append(future)
                
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
                    
                    if processed % 5 == 0:
                        print(f"Progress: {processed}/{total_channels} ({(processed/total_channels*100):.1f}%)")
            
            # Verify channels marked as 404
            if failed_channels:
                recovered = verify_404_channels(failed_channels, m3u8_file)
                working_count += recovered
                not_working_count -= recovered
        
        end_time = time.time()
        print(f"\nComplete in {end_time - start_time:.2f} seconds:")
        print(f"Working: {working_count}")
        print(f"Not working: {not_working_count}")
        print(f"Recovered channels: {recovered}")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    main()